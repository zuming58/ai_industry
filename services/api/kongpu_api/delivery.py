from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import PurePosixPath
from typing import Any


DELIVERY_SCHEMA_VERSION = "1"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class DeliveryInputError(ValueError):
    pass


def build_validation_package(
    *,
    project: dict[str, Any],
    target_profile: dict[str, Any],
    machine_spec_hash: str,
    program_commit_id: str,
    git_sha: str,
    generator_version: str,
    test_spec_hash: str,
    gates: list[dict[str, Any]],
) -> bytes:
    """Build a deterministic, profile-bound checklist for future vendor validation."""
    vendor_tool = str(target_profile.get("vendor_tool") or "厂商 IDE")
    model = str(target_profile.get("model") or "PLC")
    steps = [
        {"id": "environment", "title": "记录验证环境", "owner": "电气工程师", "required": True, "expected": f"记录 {vendor_tool} 精确版本、{model} CPU/模块、授权和操作系统。", "evidence": "版本截图或导出报告"},
        {"id": "import", "title": "导入生成工程", "owner": "电气工程师", "required": True, "expected": f"在隔离副本导入 Structured Text，确认 {target_profile.get('series')} 变量与逻辑地址映射。", "evidence": "工程副本和导入日志"},
        {"id": "compile", "title": "厂商编译", "owner": "电气工程师", "required": True, "expected": "完整编译并保存全部诊断、行号和告警；不得覆盖生成基线。", "evidence": "编译日志"},
        {"id": "simulation", "title": "厂商模拟对照", "owner": "电气工程师", "required": True, "expected": "执行正常、缺反馈、超时、互锁、复位、断线和重启场景。", "evidence": "模拟 Trace 或报告"},
        {"id": "hardware", "title": "受控台架实测", "owner": "电气工程师", "required": True, "expected": f"在明确型号 {model} 台架核对 I/O、断电/断线恢复和失效状态。", "evidence": "接线清单、现场记录"},
        {"id": "signoff", "title": "电气逻辑确认", "owner": "电气工程师", "required": True, "expected": "确认互锁、复位、异常策略及安全回路边界；安全功能不由本系统自动生成。", "evidence": "签字记录"},
    ]
    payload = {
        "schema": "kongpu-validation-package/v1",
        "status": "pending_external",
        "verification_level": "manual_unverified",
        "project": {"id": project.get("id"), "code": project.get("code"), "name": project.get("name")},
        "target": target_profile,
        "baseline": {"machine_spec_hash": machine_spec_hash, "program_commit_id": program_commit_id, "git_sha": git_sha, "generator_version": generator_version, "test_spec_hash": test_spec_hash},
        "gates": gates,
        "steps": steps,
        "result_policy": "任何外部证据默认 manual_unverified；签名升级由集中验证流程人工完成，不由上传动作自动升级。",
        "claim_boundary": f"本包只为 {target_profile.get('brand')} {target_profile.get('series')} 的集中外部验证提供可追溯清单；{vendor_tool} 编译/模拟、真实硬件和电气工程师确认尚未验证。",
    }
    return stable_json_bytes(payload)


def render_validation_checklist(package: dict[str, Any]) -> bytes:
    """Render the immutable validation package as a human-readable checklist."""
    target = package["target"]
    baseline = package["baseline"]
    lines = [
        "# 控谱集中外部验证执行清单",
        "",
        f"目标：{target['brand']} {target['series']} {target['model']}",
        f"厂商工具：{target['vendor_tool']}",
        f"MachineSpec SHA-256：{baseline['machine_spec_hash']}",
        f"Program Commit：{baseline['git_sha']}",
        f"生成器：{baseline['generator_version']}",
        f"TestSpec SHA-256：{baseline['test_spec_hash']}",
        "",
        "验证等级：`pending_external`。不得将本清单或参考模拟表述为厂商编译、硬件实测或安全确认通过。",
        "",
        "## 执行步骤",
        "",
        "| 状态 | 步骤 | 负责人 | 预期结果 | 证据 | 实际结果 |",
        "|---|---|---|---|---|---|",
    ]
    for step in package["steps"]:
        lines.append(f"| [ ] | {step['title']} | {step['owner']} | {step['expected']} | {step['evidence']} |  |")
    lines.extend(["", "## 外部验证门", ""])
    for gate in package["gates"]:
        lines.extend([f"- [ ] **{gate['title']}**：{gate['required_evidence']}"])
    lines.extend(["", "## 回退", "", "发生失败时保留原工程副本、日志和截图；创建新 Issue/分支修复并新增自动回归，禁止覆盖锁定规格、既有 Commit 或证据原件。", ""])
    return "\n".join(lines).encode("utf-8")


def stable_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def safe_package_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or any(":" in part for part in path.parts)
        or any(part in {"", "."} for part in path.parts)
    ):
        raise DeliveryInputError(f"交付包路径无效: {value}")
    return path.as_posix()


def entry_index(entries: dict[str, bytes]) -> list[dict[str, Any]]:
    indexed = []
    for raw_path, content in sorted(entries.items()):
        path = safe_package_path(raw_path)
        indexed.append(
            {
                "path": path,
                "sha256": sha256_bytes(content),
                "size_bytes": len(content),
            }
        )
    return indexed


def build_delivery_candidate(
    manifest: dict[str, Any], entries: dict[str, bytes]
) -> tuple[bytes, dict[str, Any]]:
    if "MANIFEST.json" in entries:
        raise DeliveryInputError("MANIFEST.json 由打包器生成，不能由调用方覆盖")
    normalized: dict[str, bytes] = {}
    for raw_path, content in entries.items():
        path = safe_package_path(raw_path)
        if path in normalized:
            raise DeliveryInputError(f"交付包路径重复: {path}")
        normalized[path] = bytes(content)

    complete_manifest = {
        **manifest,
        "schema": f"kongpu-delivery-candidate/v{DELIVERY_SCHEMA_VERSION}",
        "entries": entry_index(normalized),
    }
    normalized["MANIFEST.json"] = stable_json_bytes(complete_manifest)

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path, content in sorted(normalized.items()):
            info = zipfile.ZipInfo(path, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue(), complete_manifest


def verify_delivery_candidate(
    package: bytes,
    *,
    max_entries: int = 2_000,
    max_uncompressed_bytes: int = 100 * 1024 * 1024,
) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(package), mode="r") as archive:
            infos = archive.infolist()
            if len(infos) > max_entries:
                raise DeliveryInputError("交付包条目数超过限制")
            if sum(item.file_size for item in infos) > max_uncompressed_bytes:
                raise DeliveryInputError("交付包解压后大小超过限制")
            names = [safe_package_path(item.filename) for item in infos]
            if len(names) != len(set(names)):
                raise DeliveryInputError("交付包存在重复路径")
            if "MANIFEST.json" not in names:
                raise DeliveryInputError("交付包缺少 MANIFEST.json")
            manifest = json.loads(archive.read("MANIFEST.json").decode("utf-8"))
            expected = {item["path"]: item for item in manifest.get("entries", [])}
            actual_names = set(names) - {"MANIFEST.json"}
            if set(expected) != actual_names:
                raise DeliveryInputError("Manifest 条目与 ZIP 内容不一致")
            for path, item in expected.items():
                content = archive.read(path)
                if item.get("sha256") != sha256_bytes(content):
                    raise DeliveryInputError(f"交付包内容哈希不匹配: {path}")
                if item.get("size_bytes") != len(content):
                    raise DeliveryInputError(f"交付包内容大小不匹配: {path}")
            return manifest
    except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeliveryInputError(f"交付包格式无效: {exc}") from exc
