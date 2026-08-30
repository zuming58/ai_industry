from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class TargetProfileError(ValueError):
    pass


@dataclass(frozen=True)
class PlcProfile:
    profile_id: str
    brand: str
    series: str
    models: tuple[str, ...]
    adapter_id: str
    vendor_tool: str
    program_language: str
    address_pattern: re.Pattern[str]
    direct_address_binding: bool
    claim_boundary: str

    def matches(self, target: dict[str, Any]) -> bool:
        brand = str(target.get("brand") or target.get("plc_brand") or "").strip().casefold()
        series = str(target.get("series") or target.get("plc_series") or "").strip().casefold()
        model = str(target.get("model") or target.get("plc_model") or "").strip().upper()
        brand_aliases = {
            self.brand.casefold(),
            *(value.casefold() for value in _BRAND_ALIASES.get(self.profile_id, ())),
        }
        series_aliases = {
            self.series.casefold(),
            *(value.casefold() for value in _SERIES_ALIASES.get(self.profile_id, ())),
        }
        return brand in brand_aliases and series in series_aliases and model in self.models

    def target(self, model: str) -> dict[str, str]:
        normalized = str(model).strip().upper()
        if normalized not in self.models:
            raise TargetProfileError(f"{self.profile_id} 不支持型号 {model}")
        return {"brand": self.brand, "series": self.series, "model": normalized}


_BASIC_DISCRETE_ADDRESS = re.compile(r"[XYM][0-9A-F]+", re.IGNORECASE)

PROFILES = (
    PlcProfile(
        profile_id="mitsubishi-fx5u-st-v1",
        brand="三菱电机",
        series="MELSEC iQ-F",
        models=("FX5U-32MT/ES", "FX5U-64MT/ES", "FX5U-80MT/ES", "FX5UC-96MT/DSS"),
        adapter_id="gxworks3",
        vendor_tool="GX Works3",
        program_language="ST",
        address_pattern=_BASIC_DISCRETE_ADDRESS,
        direct_address_binding=True,
        claim_boundary="GX Works3、GX Simulator3、MX Component 和真实 FX5U 均待集中外部验证。",
    ),
    PlcProfile(
        profile_id="inovance-h5u-st-v1",
        brand="汇川技术",
        series="H5U",
        models=("H5U-1614MTD-A8", "H5U-3232MTD-A8"),
        adapter_id="autoshop",
        vendor_tool="AutoShop",
        program_language="ST",
        address_pattern=_BASIC_DISCRETE_ADDRESS,
        direct_address_binding=False,
        claim_boundary="AutoShop 直接地址绑定、编译、厂商模拟和真实 H5U 均待集中外部验证。",
    ),
)

_BRAND_ALIASES = {
    "mitsubishi-fx5u-st-v1": ("Mitsubishi", "Mitsubishi Electric"),
    "inovance-h5u-st-v1": ("Inovance", "汇川"),
}
_SERIES_ALIASES = {
    "mitsubishi-fx5u-st-v1": ("FX5U", "FX5UC"),
    "inovance-h5u-st-v1": ("H5U 系列",),
}


def profile_for_target(target: dict[str, Any]) -> PlcProfile:
    language = str(target.get("program_language") or "ST").strip().upper()
    if language not in {"ST", "STRUCTURED TEXT"}:
        raise TargetProfileError(f"当前仅支持 Structured Text，收到 {language or '空值'}")
    for profile in PROFILES:
        if profile.matches(target):
            return profile
    brand = target.get("brand") or target.get("plc_brand") or ""
    series = target.get("series") or target.get("plc_series") or ""
    model = target.get("model") or target.get("plc_model") or ""
    raise TargetProfileError(f"当前不支持 PLC 目标 {brand} {series} {model}")


def normalize_project_target(brand: str, series: str, model: str) -> dict[str, str]:
    profile = profile_for_target(
        {"brand": brand, "series": series, "model": model, "program_language": "ST"}
    )
    return profile.target(model)


def compatibility_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for profile in PROFILES:
        for model in profile.models:
            entries.append(
                {
                    "profile_id": profile.profile_id,
                    "target": profile.target(model),
                    "program_language": profile.program_language,
                    "adapter_id": profile.adapter_id,
                    "vendor_tool": profile.vendor_tool,
                    "machine_spec": "automatic_reference",
                    "structured_text_generation": "automatic",
                    "static_audit": "automatic",
                    "reference_simulation": "automatic_reference",
                    "vendor_compile": "unverified",
                    "vendor_simulation": "unverified",
                    "hardware": "pending_external",
                    "electrical_review": "pending_external",
                    "safety_plc": "excluded",
                    "claim_boundary": profile.claim_boundary,
                }
            )
    return entries
