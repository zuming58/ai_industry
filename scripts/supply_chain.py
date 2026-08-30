from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote


SCHEMA_VERSION = 1
CYCLONEDX_SPEC_VERSION = "1.5"
PYTHON_LOCK_PATH = Path("requirements-lock-win-py312.json")
PYTHON_INSTALL_LOCK_PATH = Path("requirements-lock-win-py312.txt")
OUTPUT_PATHS = (
    Path("docs/supply-chain/sbom.cdx.json"),
    Path("docs/supply-chain/dependency-audit.json"),
    Path("docs/supply-chain/THIRD_PARTY_LICENSES.md"),
    PYTHON_INSTALL_LOCK_PATH,
)


@dataclass(frozen=True)
class PythonDependencyPolicy:
    license_id: str
    purpose: str
    scope: str
    source_url: str
    license_evidence: str


PYTHON_DEPENDENCY_POLICY: dict[str, PythonDependencyPolicy] = {
    "fastapi": PythonDependencyPolicy(
        "MIT",
        "HTTP API framework",
        "runtime",
        "https://github.com/fastapi/fastapi",
        "PyPI distribution classifier: License :: OSI Approved :: MIT License",
    ),
    "uvicorn": PythonDependencyPolicy(
        "BSD-3-Clause",
        "Local ASGI server",
        "runtime",
        "https://github.com/encode/uvicorn",
        "PyPI distribution metadata: License-Expression BSD-3-Clause",
    ),
    "sqlalchemy": PythonDependencyPolicy(
        "MIT",
        "Relational persistence layer",
        "runtime",
        "https://github.com/sqlalchemy/sqlalchemy",
        "PyPI distribution metadata: License MIT",
    ),
    "alembic": PythonDependencyPolicy(
        "MIT",
        "Database schema migrations",
        "runtime",
        "https://github.com/sqlalchemy/alembic",
        "PyPI distribution metadata: License-Expression MIT",
    ),
    "pydantic": PythonDependencyPolicy(
        "MIT",
        "API and domain validation",
        "runtime",
        "https://github.com/pydantic/pydantic",
        "PyPI distribution metadata: License-Expression MIT",
    ),
    "pydantic-settings": PythonDependencyPolicy(
        "MIT",
        "Typed local configuration",
        "runtime",
        "https://github.com/pydantic/pydantic-settings",
        "PyPI distribution metadata: License-Expression MIT",
    ),
    "openpyxl": PythonDependencyPolicy(
        "MIT",
        "XLSX template and import processing",
        "runtime",
        "https://foss.heptapod.net/openpyxl/openpyxl",
        "PyPI distribution metadata: License MIT",
    ),
    "python-multipart": PythonDependencyPolicy(
        "Apache-2.0",
        "Bounded multipart upload parsing",
        "runtime",
        "https://github.com/Kludex/python-multipart",
        "PyPI distribution metadata: License-Expression Apache-2.0",
    ),
    "pytest": PythonDependencyPolicy(
        "MIT",
        "Backend automated tests",
        "development",
        "https://github.com/pytest-dev/pytest",
        "PyPI distribution metadata: License MIT",
    ),
    "httpx": PythonDependencyPolicy(
        "BSD-3-Clause",
        "API integration test client",
        "development",
        "https://github.com/encode/httpx",
        "PyPI distribution metadata: License BSD-3-Clause",
    ),
}

REQUIREMENT_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?:\[(?P<extras>[^]]+)\])?==(?P<version>[^;\s]+)$"
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PYTHON_LICENSE_OVERRIDES = {
    "colorama": (
        "BSD-3-Clause",
        "reviewed upstream LICENSE.txt at https://github.com/tartley/colorama",
    ),
}
LICENSE_CLASSIFIER_MAP = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
}


class SupplyChainError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalized_python_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _read_inputs(root: Path) -> tuple[bytes, bytes, dict[str, Any], bytes, dict[str, Any]]:
    requirements_bytes = (root / "requirements.txt").read_bytes()
    lock_bytes = (root / "kongpu-demo/package-lock.json").read_bytes()
    python_lock_bytes = (root / PYTHON_LOCK_PATH).read_bytes()
    try:
        lock = json.loads(lock_bytes)
        python_lock = json.loads(python_lock_bytes)
    except json.JSONDecodeError as exc:
        raise SupplyChainError(f"dependency lock is not valid JSON: {exc}") from exc
    return requirements_bytes, lock_bytes, lock, python_lock_bytes, python_lock


def _parse_python_requirements(raw: bytes) -> list[dict[str, str]]:
    dependencies: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(raw.decode("utf-8-sig").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = REQUIREMENT_PATTERN.fullmatch(line)
        if not match:
            raise SupplyChainError(
                f"requirements.txt line {line_number} must use an exact == pin: {line!r}"
            )
        name = _normalized_python_name(match.group("name"))
        if name in seen:
            raise SupplyChainError(f"duplicate Python dependency: {name}")
        seen.add(name)
        policy = PYTHON_DEPENDENCY_POLICY.get(name)
        if policy is None:
            raise SupplyChainError(
                f"Python dependency {name!r} has no reviewed license/purpose policy"
            )
        dependencies.append(
            {
                "name": name,
                "version": match.group("version"),
                "license": policy.license_id,
                "purpose": policy.purpose,
                "scope": policy.scope,
                "source_url": policy.source_url,
                "license_evidence": policy.license_evidence,
                "extras": sorted(
                    item.strip()
                    for item in (match.group("extras") or "").split(",")
                    if item.strip()
                ),
            }
        )
    missing = sorted(set(PYTHON_DEPENDENCY_POLICY) - seen)
    if missing:
        raise SupplyChainError(
            "reviewed Python dependencies missing from requirements.txt: " + ", ".join(missing)
        )
    return sorted(dependencies, key=lambda item: item["name"])


def _select_project_url(values: list[str]) -> str:
    parsed: list[tuple[str, str]] = []
    for value in values:
        label, separator, url = value.partition(",")
        parsed.append((label.strip().lower(), url.strip() if separator else value.strip()))
    for preferred in ("source", "repository", "source code", "homepage", "documentation"):
        match = next((url for label, url in parsed if label == preferred and url.startswith("https://")), None)
        if match:
            return match
    return next((url for _, url in parsed if url.startswith("https://")), "")


def _resolve_python_license(metadata: dict[str, Any], name: str) -> tuple[str, str]:
    override = PYTHON_LICENSE_OVERRIDES.get(name)
    if override:
        return override
    expression = str(metadata.get("license_expression") or "").strip()
    if expression:
        return expression, "PyPI distribution metadata License-Expression"
    license_value = str(metadata.get("license") or "").strip()
    if license_value:
        return license_value, "PyPI distribution metadata License"
    classifiers = metadata.get("classifier") or []
    matched = [LICENSE_CLASSIFIER_MAP[item] for item in classifiers if item in LICENSE_CLASSIFIER_MAP]
    if len(set(matched)) == 1:
        return matched[0], "PyPI distribution metadata license classifier"
    raise SupplyChainError(f"Python package {name!r} has no unambiguous reviewed license")


def build_python_lock_from_pip_report(root: Path, report_path: Path) -> bytes:
    try:
        from packaging.requirements import Requirement
    except ImportError as exc:
        raise SupplyChainError("packaging is required to normalize a pip report") from exc

    requirements_bytes = (root / "requirements.txt").read_bytes()
    direct = _parse_python_requirements(requirements_bytes)
    direct_by_name = {item["name"]: item for item in direct}
    try:
        report = json.loads(report_path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise SupplyChainError(f"cannot read pip report: {exc}") from exc
    environment = report.get("environment")
    installs = report.get("install")
    if not isinstance(environment, dict) or not isinstance(installs, list):
        raise SupplyChainError("pip report is missing environment/install data")
    if environment.get("implementation_name") != "cpython" or environment.get("python_version") != "3.12":
        raise SupplyChainError("Python lock must be resolved with CPython 3.12")
    if environment.get("sys_platform") != "win32" or str(environment.get("platform_machine", "")).lower() not in {"amd64", "x86_64"}:
        raise SupplyChainError("Python lock must target Windows amd64")

    raw_by_name: dict[str, dict[str, Any]] = {}
    for install in installs:
        metadata = install.get("metadata") or {}
        name = _normalized_python_name(str(metadata.get("name", "")))
        if not name or name in raw_by_name:
            raise SupplyChainError(f"invalid or duplicate Python package in pip report: {name!r}")
        raw_by_name[name] = install
    if set(direct_by_name) - set(raw_by_name):
        raise SupplyChainError("pip report does not contain every direct Python dependency")

    dependencies: dict[str, set[str]] = defaultdict(set)
    packages: list[dict[str, Any]] = []
    marker_environment = {key: str(value) for key, value in environment.items()}
    for name, install in sorted(raw_by_name.items()):
        metadata = install["metadata"]
        extras = direct_by_name.get(name, {}).get("extras", [])
        marker_extras = ["", *extras]
        for requirement_text in metadata.get("requires_dist") or []:
            requirement = Requirement(requirement_text)
            active = requirement.marker is None or any(
                requirement.marker.evaluate({**marker_environment, "extra": extra})
                for extra in marker_extras
            )
            if not active:
                continue
            dependency_name = _normalized_python_name(requirement.name)
            if dependency_name not in raw_by_name:
                raise SupplyChainError(f"active Python dependency edge is unresolved: {name} -> {dependency_name}")
            dependencies[name].add(dependency_name)

        archive_info = (install.get("download_info") or {}).get("archive_info") or {}
        sha256 = str((archive_info.get("hashes") or {}).get("sha256", "")).lower()
        if not SHA256_PATTERN.fullmatch(sha256):
            raise SupplyChainError(f"Python package {name!r} has no valid SHA-256 distribution hash")
        license_id, license_evidence = _resolve_python_license(metadata, name)
        packages.append(
            {
                "dependencies": [],
                "direct": name in direct_by_name,
                "distribution_sha256": sha256,
                "distribution_url": str((install.get("download_info") or {}).get("url", "")),
                "license": license_id,
                "license_evidence": license_evidence,
                "name": name,
                "scope": "development",
                "source_url": _select_project_url(metadata.get("project_url") or []),
                "version": str(metadata.get("version", "")),
            }
        )

    runtime_roots = {item["name"] for item in direct if item["scope"] == "runtime"}
    runtime_closure = set(runtime_roots)
    queue = list(runtime_roots)
    while queue:
        current = queue.pop()
        for dependency in dependencies[current]:
            if dependency not in runtime_closure:
                runtime_closure.add(dependency)
                queue.append(dependency)
    for package in packages:
        package["dependencies"] = sorted(dependencies[package["name"]])
        package["scope"] = "runtime" if package["name"] in runtime_closure else "development"
        if not package["version"] or not package["distribution_url"].startswith("https://files.pythonhosted.org/"):
            raise SupplyChainError(f"Python package {package['name']!r} has incomplete distribution metadata")

    lock = {
        "environment": {
            "implementation": "CPython",
            "platform_machine": "AMD64",
            "python_version": "3.12",
            "sys_platform": "win32",
        },
        "packages": packages,
        "requirements_sha256": _sha256(requirements_bytes),
        "resolver": {"name": "pip", "version": str(report.get("pip_version", ""))},
        "schema_version": 1,
    }
    return _json_document(lock)


def _parse_python_lock(
    lock: dict[str, Any], requirements_bytes: bytes, direct: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if lock.get("schema_version") != 1:
        raise SupplyChainError("Python dependency lock schema_version must be 1")
    if lock.get("requirements_sha256") != _sha256(requirements_bytes):
        raise SupplyChainError("Python dependency lock is stale for requirements.txt")
    expected_environment = {
        "implementation": "CPython",
        "platform_machine": "AMD64",
        "python_version": "3.12",
        "sys_platform": "win32",
    }
    if lock.get("environment") != expected_environment:
        raise SupplyChainError("Python dependency lock has an unsupported target environment")
    raw_packages = lock.get("packages")
    if not isinstance(raw_packages, list):
        raise SupplyChainError("Python dependency lock packages must be a list")
    packages: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw in raw_packages:
        name = _normalized_python_name(str(raw.get("name", "")))
        if not name or name in names:
            raise SupplyChainError(f"invalid or duplicate Python lock package: {name!r}")
        names.add(name)
        version = str(raw.get("version", ""))
        license_id = str(raw.get("license", ""))
        sha256 = str(raw.get("distribution_sha256", ""))
        dependencies = raw.get("dependencies")
        if not version or not license_id or not SHA256_PATTERN.fullmatch(sha256):
            raise SupplyChainError(f"Python lock package {name!r} lacks version, license, or SHA-256")
        if raw.get("scope") not in {"runtime", "development"} or not isinstance(dependencies, list):
            raise SupplyChainError(f"Python lock package {name!r} has invalid scope/dependencies")
        packages.append({**raw, "name": name, "dependencies": sorted(set(dependencies))})
    by_name = {item["name"]: item for item in packages}
    direct_by_name = {item["name"]: item for item in direct}
    if {name for name, item in by_name.items() if item.get("direct")} != set(direct_by_name):
        raise SupplyChainError("Python lock direct dependency set differs from requirements.txt")
    for name, direct_item in direct_by_name.items():
        locked = by_name[name]
        if locked["version"] != direct_item["version"] or locked["license"] != direct_item["license"]:
            raise SupplyChainError(f"Python lock direct dependency {name!r} differs from reviewed policy")
    graph: list[dict[str, Any]] = []
    for package in packages:
        unknown = set(package["dependencies"]) - names
        if unknown:
            raise SupplyChainError(f"Python lock package {package['name']!r} has unknown dependencies: {sorted(unknown)}")
        graph.append(
            {
                "ref": f"pypi:{package['name']}@{package['version']}",
                "depends_on": [f"pypi:{name}@{by_name[name]['version']}" for name in package["dependencies"]],
            }
        )
    return sorted(packages, key=lambda item: item["name"]), sorted(graph, key=lambda item: item["ref"])


def _npm_name_from_install_path(install_path: str) -> str:
    marker = "node_modules/"
    if marker not in install_path:
        raise SupplyChainError(f"unsupported npm install path: {install_path!r}")
    tail = install_path.rsplit(marker, 1)[1]
    if not tail or "/node_modules/" in tail:
        raise SupplyChainError(f"cannot derive npm package name from {install_path!r}")
    return tail


def _npm_bom_ref(install_path: str, name: str, version: str) -> str:
    path_digest = _sha256(install_path.encode("utf-8"))[:16]
    return f"npm:{name}@{version}:{path_digest}"


def _npm_resolution_candidates(parent_path: str, dependency_name: str) -> list[str]:
    if not parent_path:
        return [f"node_modules/{dependency_name}"]
    candidates: list[str] = []
    current = parent_path
    while True:
        candidates.append(f"{current}/node_modules/{dependency_name}")
        marker_index = current.rfind("/node_modules/")
        if marker_index < 0:
            break
        current = current[:marker_index]
    candidates.append(f"node_modules/{dependency_name}")
    return list(dict.fromkeys(candidates))


def _parse_npm_lock(lock: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    if lock.get("lockfileVersion") != 3:
        raise SupplyChainError("package-lock.json must use lockfileVersion 3")
    packages = lock.get("packages")
    if not isinstance(packages, dict) or not isinstance(packages.get(""), dict):
        raise SupplyChainError("package-lock.json packages/root entry is missing")

    components: list[dict[str, Any]] = []
    component_by_path: dict[str, dict[str, Any]] = {}
    unresolved_licenses: list[dict[str, str]] = []
    for install_path, package in sorted(packages.items()):
        if not install_path:
            continue
        if not isinstance(package, dict):
            raise SupplyChainError(f"npm package entry {install_path!r} must be an object")
        version = str(package.get("version", "")).strip()
        license_id = str(package.get("license", "")).strip()
        if not version:
            raise SupplyChainError(f"npm package {install_path!r} has no locked version")
        name = _npm_name_from_install_path(install_path)
        if not license_id:
            unresolved_licenses.append({"ecosystem": "npm", "name": name, "path": install_path})
        component = {
            "bom_ref": _npm_bom_ref(install_path, name, version),
            "dev": bool(package.get("dev", False)),
            "install_path": install_path,
            "integrity": str(package.get("integrity", "")),
            "license": license_id or "UNRESOLVED",
            "name": name,
            "resolved": str(package.get("resolved", "")),
            "version": version,
        }
        components.append(component)
        component_by_path[install_path] = component

    root_package = packages[""]
    unresolved_edges: list[dict[str, str]] = []
    dependency_edges: dict[str, set[str]] = defaultdict(set)
    root_ref = "application:kongpu"
    for parent_path, package in sorted(packages.items()):
        if not isinstance(package, dict):
            continue
        parent_ref = root_ref if not parent_path else component_by_path[parent_path]["bom_ref"]
        required_names = dict(package.get("dependencies") or {})
        optional_names = dict(package.get("optionalDependencies") or {})
        for dependency_name in sorted(set(required_names) | set(optional_names)):
            resolved_component = next(
                (
                    component_by_path[candidate]
                    for candidate in _npm_resolution_candidates(parent_path, dependency_name)
                    if candidate in component_by_path
                ),
                None,
            )
            if resolved_component is None:
                if dependency_name not in optional_names:
                    unresolved_edges.append(
                        {
                            "dependency": dependency_name,
                            "parent": parent_path or "<root>",
                        }
                    )
                continue
            dependency_edges[parent_ref].add(resolved_component["bom_ref"])

    direct: list[dict[str, str | bool]] = []
    for scope, field in (("runtime", "dependencies"), ("development", "devDependencies")):
        for name, requested in sorted((root_package.get(field) or {}).items()):
            install_path = f"node_modules/{name}"
            component = component_by_path.get(install_path)
            if component is None:
                unresolved_edges.append({"dependency": name, "parent": "<root>"})
                continue
            direct.append(
                {
                    "bom_ref": component["bom_ref"],
                    "license": component["license"],
                    "name": name,
                    "requested": str(requested),
                    "scope": scope,
                    "version": component["version"],
                }
            )

    if unresolved_licenses:
        names = ", ".join(item["name"] for item in unresolved_licenses)
        raise SupplyChainError(f"npm packages with unresolved licenses: {names}")
    if unresolved_edges:
        details = ", ".join(
            f"{item['parent']} -> {item['dependency']}" for item in unresolved_edges
        )
        raise SupplyChainError(f"unresolved npm dependency edges: {details}")

    graph = [
        {"ref": ref, "depends_on": sorted(depends_on)}
        for ref, depends_on in sorted(dependency_edges.items())
    ]
    all_refs = {component["bom_ref"] for component in components} | {root_ref}
    represented_refs = {entry["ref"] for entry in graph}
    graph.extend(
        {"ref": ref, "depends_on": []}
        for ref in sorted(all_refs - represented_refs)
    )
    return components, {"direct": direct, "graph": sorted(graph, key=lambda item: item["ref"])}, []


def _property(name: str, value: str) -> dict[str, str]:
    return {"name": name, "value": value}


def _python_component(dependency: dict[str, Any]) -> dict[str, Any]:
    name = dependency["name"]
    version = dependency["version"]
    external_references = [
        {"type": "distribution", "url": dependency["distribution_url"]}
    ]
    if dependency.get("source_url"):
        external_references.append({"type": "vcs", "url": dependency["source_url"]})
    result = {
        "bom-ref": f"pypi:{name}@{version}",
        "externalReferences": external_references,
        "hashes": [{"alg": "SHA-256", "content": dependency["distribution_sha256"]}],
        "licenses": [{"expression": dependency["license"]}],
        "name": name,
        "properties": [
            _property("kongpu:dependencyScope", dependency["scope"]),
            _property("kongpu:licenseEvidence", dependency["license_evidence"]),
            _property("kongpu:inventoryCoverage", "windows-cpython-3.12-locked"),
            _property("kongpu:directDependency", str(bool(dependency["direct"])).lower()),
        ],
        "purl": f"pkg:pypi/{quote(name, safe='')}@{quote(version, safe='')}",
        "scope": "required" if dependency["scope"] == "runtime" else "optional",
        "type": "library",
        "version": version,
    }
    if dependency.get("purpose"):
        result["properties"].append(_property("kongpu:purpose", dependency["purpose"]))
    return result


def _npm_component(component: dict[str, Any]) -> dict[str, Any]:
    properties = [
        _property("kongpu:installPath", component["install_path"]),
        _property("kongpu:dependencyScope", "development" if component["dev"] else "runtime"),
    ]
    if component["integrity"]:
        properties.append(_property("kongpu:npmIntegrity", component["integrity"]))
    external_references = []
    if component["resolved"]:
        external_references.append({"type": "distribution", "url": component["resolved"]})
    result: dict[str, Any] = {
        "bom-ref": component["bom_ref"],
        "licenses": [{"expression": component["license"]}],
        "name": component["name"],
        "properties": properties,
        "purl": f"pkg:npm/{quote(component['name'], safe='/')}@{quote(component['version'], safe='')}",
        "scope": "optional" if component["dev"] else "required",
        "type": "library",
        "version": component["version"],
    }
    if external_references:
        result["externalReferences"] = external_references
    return result


def _json_document(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _build_license_markdown(
    input_hashes: dict[str, str],
    python_packages: list[dict[str, Any]],
    npm_components: list[dict[str, Any]],
    npm_direct: list[dict[str, Any]],
) -> bytes:
    license_counts = Counter(
        [dependency["license"] for dependency in python_packages]
        + [component["license"] for component in npm_components]
    )
    direct_npm_by_name = {item["name"]: item for item in npm_direct}
    lines = [
        "# Third-party dependency and license inventory",
        "",
        "This file is generated by `scripts/generate-supply-chain.py`; do not edit it manually.",
        "The inventory is an automatic source audit, not legal advice or vendor-tool validation.",
        "",
        "## Reproducibility inputs",
        "",
        f"- `requirements.txt`: `{input_hashes['requirements.txt']}`",
        f"- `requirements-lock-win-py312.json`: `{input_hashes['requirements-lock-win-py312.json']}`",
        f"- `kongpu-demo/package-lock.json`: `{input_hashes['kongpu-demo/package-lock.json']}`",
        f"- Aggregate input SHA-256: `{input_hashes['aggregate']}`",
        "- Python coverage: complete pip-resolved wheel closure for CPython 3.12 on Windows AMD64; every selected distribution has a SHA-256.",
        "- npm coverage: every installed package entry and dependency edge in package-lock v3.",
        "",
        "## License summary",
        "",
        "| SPDX expression | Installed entries |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {_markdown_escape(license_id)} | {count} |"
        for license_id, count in sorted(license_counts.items())
    )
    lines.extend(
        [
            "",
            "## Python locked packages",
            "",
            "| Dependency | Version | Scope | Direct | License | Distribution SHA-256 | License evidence |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for dependency in python_packages:
        values = [
            dependency["name"],
            dependency["version"],
            dependency["scope"],
            "yes" if dependency["direct"] else "no",
            dependency["license"],
            dependency["distribution_sha256"],
            dependency["license_evidence"],
        ]
        lines.append("| " + " | ".join(_markdown_escape(value) for value in values) + " |")
    lines.extend(
        [
            "",
            "## npm locked package entries",
            "",
            "Repeated name/version rows represent distinct lockfile installation paths and retain their own integrity metadata in the SBOM.",
            "",
            "| Dependency | Version | Scope | Direct | License | Install path |",
            "|---|---|---|---|---|---|",
        ]
    )
    for component in npm_components:
        direct = direct_npm_by_name.get(component["name"])
        values = [
            component["name"],
            component["version"],
            "development" if component["dev"] else "runtime",
            "yes" if direct and component["install_path"] == f"node_modules/{component['name']}" else "no",
            component["license"],
            component["install_path"],
        ]
        lines.append("| " + " | ".join(_markdown_escape(str(value)) for value in values) + " |")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def _build_python_install_lock(python_packages: list[dict[str, Any]]) -> bytes:
    lines = [
        "# Generated by scripts/generate-supply-chain.py; do not edit manually.",
        "# Target: CPython 3.12 / Windows AMD64.",
        "--only-binary=:all:",
        "--require-hashes",
        "",
    ]
    for package in python_packages:
        normalized_name = package["name"]
        lines.append(
            f"{normalized_name}=={package['version']} --hash=sha256:{package['distribution_sha256']}"
        )
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def build_supply_chain_documents(root: Path) -> dict[Path, bytes]:
    root = root.resolve()
    requirements_bytes, lock_bytes, lock, python_lock_bytes, python_lock = _read_inputs(root)
    python_dependencies = _parse_python_requirements(requirements_bytes)
    python_packages, python_graph = _parse_python_lock(
        python_lock, requirements_bytes, python_dependencies
    )
    purpose_by_name = {item["name"]: item["purpose"] for item in python_dependencies}
    for package in python_packages:
        package["purpose"] = purpose_by_name.get(package["name"], "transitive dependency")
    npm_components, npm_data, unresolved = _parse_npm_lock(lock)
    input_hashes = {
        "requirements.txt": _sha256(requirements_bytes),
        "requirements-lock-win-py312.json": _sha256(python_lock_bytes),
        "kongpu-demo/package-lock.json": _sha256(lock_bytes),
    }
    input_hashes["aggregate"] = _sha256(
        "\n".join(f"{name}:{digest}" for name, digest in sorted(input_hashes.items())).encode("ascii")
    )

    python_by_name = {item["name"]: item for item in python_packages}
    python_refs = [
        f"pypi:{item['name']}@{item['version']}"
        for item in python_packages
        if item["direct"]
    ]
    npm_graph = npm_data["graph"]
    root_graph = next(item for item in npm_graph if item["ref"] == "application:kongpu")
    root_graph["depends_on"] = sorted(set(root_graph["depends_on"]) | set(python_refs))
    npm_graph.extend(python_graph)
    npm_graph.sort(key=lambda item: item["ref"])

    sbom = {
        "bomFormat": "CycloneDX",
        "components": [
            *[_python_component(item) for item in python_packages],
            *[_npm_component(item) for item in npm_components],
        ],
        "dependencies": [
            {"ref": item["ref"], "dependsOn": item["depends_on"]}
            for item in npm_graph
        ],
        "metadata": {
            "component": {
                "bom-ref": "application:kongpu",
                "name": "kongpu",
                "type": "application",
                "version": "m3-prerequisite",
            },
            "properties": [
                _property("kongpu:generator", "scripts/generate-supply-chain.py"),
                _property("kongpu:generatorSchemaVersion", str(SCHEMA_VERSION)),
                _property("kongpu:inputAggregateSha256", input_hashes["aggregate"]),
                _property("kongpu:pythonCoverage", "windows-cpython-3.12-locked-closure"),
                _property("kongpu:npmCoverage", "package-lock-v3-complete"),
            ],
            "tools": {
                "components": [
                    {"name": "kongpu deterministic supply-chain generator", "type": "application", "version": str(SCHEMA_VERSION)}
                ]
            },
        },
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'kongpu-sbom:' + input_hashes['aggregate'])}",
        "specVersion": CYCLONEDX_SPEC_VERSION,
        "version": 1,
    }

    license_counts = Counter(
        [item["license"] for item in python_packages]
        + [item["license"] for item in npm_components]
    )
    audit = {
        "coverage": {
            "npm": "all package-lock v3 installation entries and resolvable declared dependency edges",
            "python": "complete hash-pinned pip wheel closure for CPython 3.12 on Windows AMD64",
        },
        "direct_dependencies": {
            "npm": npm_data["direct"],
            "python": python_dependencies,
        },
        "findings": [],
        "generator": "scripts/generate-supply-chain.py",
        "input_files": input_hashes,
        "license_counts": dict(sorted(license_counts.items())),
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "summary": {
            "npm_direct": len(npm_data["direct"]),
            "npm_locked_entries": len(npm_components),
            "python_direct": len(python_dependencies),
            "python_locked_packages": len(python_packages),
            "unresolved_dependency_edges": 0,
            "unresolved_licenses": len(unresolved),
        },
        "unresolved_dependency_edges": [],
        "unresolved_licenses": unresolved,
        "validation_level": "automatic",
    }

    return {
        OUTPUT_PATHS[0]: _json_document(sbom),
        OUTPUT_PATHS[1]: _json_document(audit),
        OUTPUT_PATHS[2]: _build_license_markdown(
            input_hashes, python_packages, npm_components, npm_data["direct"]
        ),
        OUTPUT_PATHS[3]: _build_python_install_lock(python_packages),
    }


def write_supply_chain_documents(root: Path) -> list[Path]:
    documents = build_supply_chain_documents(root)
    written: list[Path] = []
    for relative_path, content in documents.items():
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        written.append(destination)
    return written


def check_supply_chain_documents(root: Path) -> list[Path]:
    documents = build_supply_chain_documents(root)
    stale: list[Path] = []
    for relative_path, content in documents.items():
        destination = root / relative_path
        if not destination.is_file() or destination.read_bytes() != content:
            stale.append(relative_path)
    return stale
