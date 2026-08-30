from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.supply_chain import (
    OUTPUT_PATHS,
    PYTHON_DEPENDENCY_POLICY,
    PYTHON_LOCK_PATH,
    SupplyChainError,
    build_supply_chain_documents,
)


ROOT = Path(__file__).resolve().parents[3]


def _copy_inputs(destination: Path) -> None:
    (destination / "kongpu-demo").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "requirements.txt", destination / "requirements.txt")
    shutil.copyfile(ROOT / PYTHON_LOCK_PATH, destination / PYTHON_LOCK_PATH)
    shutil.copyfile(
        ROOT / "kongpu-demo/package-lock.json",
        destination / "kongpu-demo/package-lock.json",
    )


def test_supply_chain_generation_is_deterministic_and_complete() -> None:
    first = build_supply_chain_documents(ROOT)
    second = build_supply_chain_documents(ROOT)

    assert first == second
    assert set(first) == set(OUTPUT_PATHS)
    audit = json.loads(first[Path("docs/supply-chain/dependency-audit.json")])
    sbom = json.loads(first[Path("docs/supply-chain/sbom.cdx.json")])
    python_names = {item["name"] for item in audit["direct_dependencies"]["python"]}
    root_lock = json.loads((ROOT / "kongpu-demo/package-lock.json").read_text(encoding="utf-8"))["packages"][""]
    npm_direct_names = {item["name"] for item in audit["direct_dependencies"]["npm"]}

    assert python_names == set(PYTHON_DEPENDENCY_POLICY)
    assert npm_direct_names == set(root_lock["dependencies"]) | set(root_lock["devDependencies"])
    assert audit["summary"]["unresolved_licenses"] == 0
    assert audit["summary"]["unresolved_dependency_edges"] == 0
    assert audit["status"] == "passed"
    assert audit["findings"] == []
    assert audit["summary"]["python_locked_packages"] > audit["summary"]["python_direct"]
    assert all(component.get("version") for component in sbom["components"])
    assert all(component.get("licenses") for component in sbom["components"])
    python_components = [item for item in sbom["components"] if item["bom-ref"].startswith("pypi:")]
    assert len(python_components) == audit["summary"]["python_locked_packages"]
    assert all(component.get("hashes") for component in python_components)
    assert all(
        set(choice) in ({"license"}, {"expression"})
        for component in sbom["components"]
        for choice in component["licenses"]
    )
    assert all(
        "id" in choice["license"] or "name" in choice["license"]
        for component in sbom["components"]
        for choice in component["licenses"]
        if "license" in choice
    )


def test_checked_in_supply_chain_outputs_are_current() -> None:
    generated = build_supply_chain_documents(ROOT)
    for relative_path, expected in generated.items():
        assert (ROOT / relative_path).read_bytes() == expected, f"stale {relative_path}"


def test_lockfile_byte_change_changes_audit_input_hash(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    original = build_supply_chain_documents(tmp_path)
    lock_path = tmp_path / "kongpu-demo/package-lock.json"
    lock_path.write_bytes(lock_path.read_bytes() + b"\n")
    changed = build_supply_chain_documents(tmp_path)

    original_audit = json.loads(original[Path("docs/supply-chain/dependency-audit.json")])
    changed_audit = json.loads(changed[Path("docs/supply-chain/dependency-audit.json")])
    assert original_audit["input_files"]["kongpu-demo/package-lock.json"] != changed_audit["input_files"]["kongpu-demo/package-lock.json"]
    assert original_audit["input_files"]["aggregate"] != changed_audit["input_files"]["aggregate"]


def test_python_lock_hash_and_license_are_enforced(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    lock_path = tmp_path / PYTHON_LOCK_PATH
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"][0]["distribution_sha256"] = "not-a-hash"
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(SupplyChainError, match="version, license, or SHA-256"):
        build_supply_chain_documents(tmp_path)

    _copy_inputs(tmp_path)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["packages"][0]["license"] = ""
    lock_path.write_text(json.dumps(lock), encoding="utf-8")
    with pytest.raises(SupplyChainError, match="version, license, or SHA-256"):
        build_supply_chain_documents(tmp_path)


def test_missing_npm_license_is_rejected(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    lock_path = tmp_path / "kongpu-demo/package-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    first_package = next(path for path in lock["packages"] if path)
    lock["packages"][first_package].pop("license", None)
    lock_path.write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(SupplyChainError, match="unresolved licenses"):
        build_supply_chain_documents(tmp_path)


def test_unreviewed_or_unpinned_python_dependency_is_rejected(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    requirements_path = tmp_path / "requirements.txt"
    requirements_path.write_text(
        requirements_path.read_text(encoding="utf-8") + "unknown-package==1.0.0\n",
        encoding="utf-8",
    )
    with pytest.raises(SupplyChainError, match="no reviewed license/purpose policy"):
        build_supply_chain_documents(tmp_path)

    requirements_path.write_text("fastapi>=0.116.1\n", encoding="utf-8")
    with pytest.raises(SupplyChainError, match="exact == pin"):
        build_supply_chain_documents(tmp_path)


def test_outputs_do_not_expose_machine_paths_or_usernames() -> None:
    documents = build_supply_chain_documents(ROOT)
    combined = b"\n".join(documents.values()).decode("utf-8").lower()

    assert str(ROOT).lower() not in combined
    assert "c:\\users\\" not in combined
    assert "f:\\codex\\" not in combined
    assert "zuming" not in combined


def test_check_command_passes_for_checked_in_outputs() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate-supply-chain.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
