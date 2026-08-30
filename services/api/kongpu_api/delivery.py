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
