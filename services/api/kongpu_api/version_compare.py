from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _stable(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if not isinstance(value, dict):
        return {prefix or "value": _stable(value)}
    result: dict[str, Any] = {}
    for key in sorted(value):
        if key == "source":
            continue
        path = f"{prefix}.{key}" if prefix else key
        item = value[key]
        if isinstance(item, dict):
            result.update(_flatten(item, path))
        else:
            result[path] = _stable(item)
    return result


def _field_changes(base: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    before = _flatten(base)
    after = _flatten(target)
    return [
        {"field": field, "before": before.get(field), "after": after.get(field)}
        for field in sorted(set(before) | set(after))
        if before.get(field) != after.get(field)
    ]


def _item(
    change: str,
    entity_type: str,
    entity_id: str,
    *,
    fields: list[dict[str, Any]] | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_fields = fields or []
    if not normalized_fields and before is None and after is not None:
        normalized_fields = _field_changes({}, after)
    elif not normalized_fields and before is not None and after is None:
        normalized_fields = _field_changes(before, {})
    return {
        "change": change,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "fields": normalized_fields,
        "source_before": (before or {}).get("source"),
        "source_after": (after or {}).get("source"),
    }


def _compare_object(entity_type: str, base: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    changes = _field_changes(base, target)
    return [_item("changed", entity_type, entity_type, fields=changes, before=base, after=target)] if changes else []


def _compare_collection(
    entity_type: str,
    base_rows: list[dict[str, Any]],
    target_rows: list[dict[str, Any]],
    id_field: str,
    fields: set[str] | None = None,
) -> list[dict[str, Any]]:
    base = {str(row.get(id_field)): row for row in base_rows}
    target = {str(row.get(id_field)): row for row in target_rows}
    result: list[dict[str, Any]] = []
    for entity_id in sorted(set(base) | set(target)):
        before = base.get(entity_id)
        after = target.get(entity_id)
        if before is None:
            result.append(_item("added", entity_type, entity_id, after=after))
            continue
        if after is None:
            result.append(_item("removed", entity_type, entity_id, before=before))
            continue
        before_value = before if fields is None else {key: before.get(key) for key in sorted(fields)}
        after_value = after if fields is None else {key: after.get(key) for key in sorted(fields)}
        changes = _field_changes(before_value, after_value)
        if changes:
            result.append(
                _item(
                    "changed",
                    entity_type,
                    entity_id,
                    fields=changes,
                    before=before,
                    after=after,
                )
            )
    return result


def _section(
    section_id: str,
    label: str,
    items: list[dict[str, Any]],
    *,
    verification_level: str = "automatic",
    note: str | None = None,
) -> dict[str, Any]:
    summary = {
        "added": sum(item["change"] == "added" for item in items),
        "removed": sum(item["change"] == "removed" for item in items),
        "changed": sum(item["change"] == "changed" for item in items),
        "total": len(items),
    }
    return {
        "id": section_id,
        "label": label,
        "status": "changed" if items else "unchanged",
        "verification_level": verification_level,
        "summary": summary,
        "items": items,
        "note": note,
    }


def _compare_files(base: dict[str, str], target: dict[str, str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in sorted(set(base) | set(target)):
        before = base.get(path)
        after = target.get(path)
        if before == after:
            continue
        change = "added" if before is None else "removed" if after is None else "changed"
        fields = [
            {
                "field": "sha256",
                "before": hashlib.sha256(before.encode("utf-8")).hexdigest() if before is not None else None,
                "after": hashlib.sha256(after.encode("utf-8")).hexdigest() if after is not None else None,
            },
            {
                "field": "size_bytes",
                "before": len(before.encode("utf-8")) if before is not None else None,
                "after": len(after.encode("utf-8")) if after is not None else None,
            },
        ]
        result.append(_item(change, "source_file", path, fields=fields))
    return result


def compare_version_snapshots(
    base: dict[str, Any],
    target: dict[str, Any],
    *,
    source_diff: str,
) -> dict[str, Any]:
    base_spec = base["machine_spec"]
    target_spec = target["machine_spec"]
    machine_spec_items = [
        *_compare_object(
            "machine_spec_metadata",
            {
                "schema_version": base_spec.get("schema_version"),
                "template_version": base_spec.get("template_version"),
                "project": base_spec.get("project", {}),
                "plc_target": base_spec.get("plc_target", {}),
            },
            {
                "schema_version": target_spec.get("schema_version"),
                "template_version": target_spec.get("template_version"),
                "project": target_spec.get("project", {}),
                "plc_target": target_spec.get("plc_target", {}),
            },
        ),
    ]
    for entity_type, id_field in (
        ("components", "component_id"),
        ("signals", "signal_id"),
        ("sequence", "step_id"),
        ("interlocks", "interlock_id"),
        ("exceptions", "exception_id"),
    ):
        machine_spec_items.extend(
            _compare_collection(
                entity_type,
                base_spec.get(entity_type, []),
                target_spec.get(entity_type, []),
                id_field,
            )
        )

    io_fields = {
        "display_name", "direction", "address", "data_type", "unit",
        "component_id", "normal_state", "description",
    }
    io_items = _compare_collection(
        "io_signal",
        base_spec.get("signals", []),
        target_spec.get("signals", []),
        "signal_id",
        io_fields,
    )
    parameter_fields = {
        "display_name", "parent_id", "component_type", "control_template",
        "parameter_value", "parameter_unit", "notes",
    }
    parameter_items = _compare_collection(
        "component_parameter",
        base_spec.get("components", []),
        target_spec.get("components", []),
        "component_id",
        parameter_fields,
    )
    parameter_items.extend(
        _compare_object(
            "project_parameter",
            {
                "cycle_target": base_spec.get("project", {}).get("cycle_target"),
                "cycle_unit": base_spec.get("project", {}).get("cycle_unit"),
            },
            {
                "cycle_target": target_spec.get("project", {}).get("cycle_target"),
                "cycle_unit": target_spec.get("project", {}).get("cycle_unit"),
            },
        )
    )

    base_ir = base["control_ir"]
    target_ir = target["control_ir"]
    control_ir_items = _compare_object(
        "control_ir_metadata",
        {key: base_ir.get(key) for key in ("ir_version", "generator_version", "target", "project")},
        {key: target_ir.get(key) for key in ("ir_version", "generator_version", "target", "project")},
    )
    for entity_type, id_field in (
        ("components", "component_id"),
        ("signals", "id"),
        ("steps", "id"),
        ("interlocks", "interlock_id"),
        ("exceptions", "exception_id"),
    ):
        control_ir_items.extend(
            _compare_collection(
                f"control_ir_{entity_type}",
                base_ir.get(entity_type, []),
                target_ir.get(entity_type, []),
                id_field,
            )
        )

    test_spec_items = _compare_object(
        "test_spec_metadata",
        {key: base["test_spec"].get(key) for key in ("version", "target")},
        {key: target["test_spec"].get(key) for key in ("version", "target")},
    )
    test_spec_items.extend(
        _compare_collection(
            "test_case",
            base["test_spec"].get("tests", []),
            target["test_spec"].get("tests", []),
            "id",
        )
    )

    sections = [
        _section("source", "程序源码", _compare_files(base["files"], target["files"])),
        _section("machine_spec", "MachineSpec", machine_spec_items),
        _section("io", "I/O 映射", io_items),
        _section("parameters", "组件与工程参数", parameter_items),
        _section("control_ir", "Control IR", control_ir_items),
        _section("test_spec", "TestSpec", test_spec_items),
        _section(
            "generation",
            "生成配置",
            _compare_object("generation_config", base["generation"], target["generation"]),
        ),
        _section(
            "verification",
            "自动验证摘要",
            _compare_object("verification", base["verification"], target["verification"]),
        ),
        _section(
            "vendor_configuration",
            "厂商配置摘要",
            _compare_object("vendor_configuration", base["vendor_configuration"], target["vendor_configuration"]),
            verification_level="unverified",
            note="仅比较已保存的 Adapter、环境和证据摘要；厂商二进制工程未接入，未经过 GX Works3 验证。",
        ),
    ]
    changed_sections = sum(section["status"] == "changed" for section in sections)
    changed_items = sum(section["summary"]["total"] for section in sections)
    fingerprint_input = {
        "base_commit_id": base["commit"]["id"],
        "target_commit_id": target["commit"]["id"],
        "base_git_sha": base["commit"]["git_sha"],
        "target_git_sha": target["commit"]["git_sha"],
        "sections": sections,
    }
    comparison_hash = hashlib.sha256(
        json.dumps(
            fingerprint_input,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "kongpu-version-comparison/v1",
        "base": base["commit"],
        "target": target["commit"],
        "same_commit": base["commit"]["git_sha"] == target["commit"]["git_sha"],
        "comparison_hash": comparison_hash,
        "summary": {
            "changed_sections": changed_sections,
            "unchanged_sections": len(sections) - changed_sections,
            "changed_items": changed_items,
        },
        "sections": sections,
        "source_diff": source_diff,
        "claim_boundary": "结构化比较只基于两个明确 Commit 及其不可变本机工件；厂商二进制工程、真实编译、真实模拟和硬件结果未验证。",
    }
