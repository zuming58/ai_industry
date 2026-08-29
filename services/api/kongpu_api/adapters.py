from __future__ import annotations

import hashlib
import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


CAPABILITIES = (
    "detect_environment",
    "get_capabilities",
    "prepare_workspace_copy",
    "compile",
    "get_diagnostics",
    "start_simulation",
    "get_trace",
    "export_vendor_project",
)


class AdapterContract(Protocol):
    """Versioned adapter surface with explicit, bounded operations."""

    adapter_id: str
    version: str

    def detect_environment(self, target: dict[str, Any] | None = None) -> dict[str, Any]: ...
    def get_capabilities(self) -> dict[str, str]: ...
    def prepare_workspace_copy(self, source: str, destination: str) -> dict[str, Any]: ...
    def compile(self, workspace: str) -> dict[str, Any]: ...
    def get_diagnostics(self, run_id: str) -> dict[str, Any]: ...
    def start_simulation(self, workspace: str) -> dict[str, Any]: ...
    def get_trace(self, session_id: str) -> dict[str, Any]: ...
    def export_vendor_project(self, workspace: str, destination: str) -> dict[str, Any]: ...


class AdapterOperationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    name: str
    version: str
    vendor: str
    capabilities: dict[str, str]
    verification_level: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "name": self.name,
            "version": self.version,
            "vendor": self.vendor,
            "capabilities": self.capabilities,
            "verification_level": self.verification_level,
        }


def _capabilities(**supported: str) -> dict[str, str]:
    values = {name: "unsupported" for name in CAPABILITIES}
    values.update(supported)
    return values


def descriptors() -> list[AdapterDescriptor]:
    return [
        AdapterDescriptor(
            "reference", "控谱参考逻辑模拟", "1", "Kongpu", 
            _capabilities(detect_environment="supported", get_capabilities="supported", start_simulation="supported", get_trace="supported"),
            "automatic_reference",
        ),
        AdapterDescriptor(
            "gxworks3", "MELSOFT GX Works3", "1", "Mitsubishi Electric",
            _capabilities(detect_environment="experimental", get_capabilities="experimental", prepare_workspace_copy="manual", compile="manual", get_diagnostics="manual", start_simulation="manual", get_trace="manual", export_vendor_project="manual"),
            "unverified",
        ),
        AdapterDescriptor(
            "autoshop", "汇川 AutoShop", "1", "Inovance",
            _capabilities(detect_environment="experimental", get_capabilities="experimental", prepare_workspace_copy="manual", compile="manual", get_diagnostics="manual", start_simulation="manual", get_trace="manual", export_vendor_project="manual"),
            "unverified",
        ),
        AdapterDescriptor(
            "codesys", "CODESYS", "1", "CODESYS GmbH",
            _capabilities(detect_environment="experimental", get_capabilities="experimental", prepare_workspace_copy="manual", compile="manual", get_diagnostics="manual", start_simulation="manual", get_trace="manual", export_vendor_project="manual"),
            "unverified",
        ),
    ]


def descriptor(adapter_id: str) -> AdapterDescriptor:
    for item in descriptors():
        if item.adapter_id == adapter_id:
            return item
    raise KeyError(adapter_id)


class ManualAdapter:
    """Safe fallback for vendor tools that are not installed or verified."""

    def __init__(self, item: AdapterDescriptor):
        self.adapter_id = item.adapter_id
        self.version = item.version
        self._descriptor = item

    def detect_environment(self, target: dict[str, Any] | None = None) -> dict[str, Any]:
        return detect(self.adapter_id, target)

    def get_capabilities(self) -> dict[str, str]:
        return dict(self._descriptor.capabilities)

    def _manual(self, operation: str, **details: Any) -> dict[str, Any]:
        return {
            "status": "manual_required",
            "verification_level": "unverified",
            "operation": operation,
            "message": "当前 Adapter 只提供人工降级路径，不启动未知厂商程序。",
            **details,
        }

    def prepare_workspace_copy(self, source: str, destination: str) -> dict[str, Any]:
        return self._manual("prepare_workspace_copy", source=source, destination=destination)

    def compile(self, workspace: str) -> dict[str, Any]:
        return self._manual("compile", workspace=workspace)

    def get_diagnostics(self, run_id: str) -> dict[str, Any]:
        return self._manual("get_diagnostics", run_id=run_id, diagnostics=[])

    def start_simulation(self, workspace: str) -> dict[str, Any]:
        return self._manual("start_simulation", workspace=workspace)

    def get_trace(self, session_id: str) -> dict[str, Any]:
        return self._manual("get_trace", session_id=session_id, traces=[])

    def export_vendor_project(self, workspace: str, destination: str) -> dict[str, Any]:
        return self._manual("export_vendor_project", workspace=workspace, destination=destination)


class ReferenceAdapter(ManualAdapter):
    """Descriptor-backed adapter for the restricted deterministic simulator."""

    def _manual(self, operation: str, **details: Any) -> dict[str, Any]:
        if operation in {"start_simulation", "get_trace"}:
            return {
                "status": "supported",
                "verification_level": "automatic_reference",
                "operation": operation,
                "message": "由 API 的受限 TestSpec 执行器处理；不等同于 GX Simulator3。",
                **details,
            }
        return super()._manual(operation, **details)


def adapter(adapter_id: str) -> AdapterContract:
    item = descriptor(adapter_id)
    return ReferenceAdapter(item) if adapter_id == "reference" else ManualAdapter(item)


def detect(adapter_id: str, target: dict[str, Any] | None = None) -> dict[str, Any]:
    item = descriptor(adapter_id)
    target = target or {}
    details: dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "target_model": target.get("plc_model"),
        "checked_paths": [],
        "tool_version": None,
        "message": "未检测到可安全调用的厂商工具" if adapter_id != "reference" else "使用内置受限参考逻辑引擎",
    }
    if adapter_id == "reference":
        status = "supported"
        verification = "automatic_reference"
    else:
        # Environment detection is deliberately read-only. No vendor process is started.
        variable = {
            "gxworks3": "KONGPU_GXWORKS3_PATH",
            "autoshop": "KONGPU_AUTOSHOP_PATH",
            "codesys": "KONGPU_CODESYS_PATH",
        }[adapter_id]
        value = os.environ.get(variable)
        candidates = [value] if value else []
        details["checked_environment_variable"] = variable
        details["checked_paths"] = candidates
        existing = next((str(Path(path)) for path in candidates if Path(path).exists()), None)
        if existing:
            details["detected_path"] = existing
            status = "manual_required"
        else:
            status = "unavailable"
        verification = "unverified"
    fingerprint = hashlib.sha256(json.dumps({"adapter": item.adapter_id, "version": item.version, "details": details}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"descriptor": item.as_dict(), "status": status, "verification_level": verification, "fingerprint": fingerprint, "details": details}
