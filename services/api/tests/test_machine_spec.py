from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from kongpu_api.config import Settings
from kongpu_api.machine_spec import (
    WorkbookInputError,
    generate_workbook,
    inspect_xlsx_archive,
    parse_workbook,
    patch_cells,
    spec_hash,
    validate_spec,
)


def project_payload() -> dict[str, str]:
    return {
        "id": "project-id",
        "code": "KP-TEST-001",
        "name": "装配线",
        "customer_code": "C001",
        "plc_brand": "三菱电机",
        "plc_series": "MELSEC iQ-F",
        "plc_model": "FX5U-64MT/ES",
    }


def test_template_round_trip_and_hash_is_stable(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    content = generate_workbook(project_payload(), kind="example")
    workbook = load_workbook(io.BytesIO(content))
    assert workbook["_meta"].sheet_state == "hidden"
    spec, parse_issues = parse_workbook(content, settings)
    issues = parse_issues + validate_spec(spec, project_payload())
    assert not [item for item in issues if item.severity == "blocker"]
    assert spec_hash(spec) == spec_hash(dict(reversed(list(spec.items()))))


def test_validation_rules_cover_core_engineering_failures(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    spec, _ = parse_workbook(generate_workbook(project_payload(), kind="example"), settings)
    spec["signals"][1]["address"] = spec["signals"][0]["address"]
    spec["signals"][0]["data_type"] = "REAL"
    spec["signals"][3]["unit"] = None
    spec["sequence"][0]["next_step_id"] = "UNKNOWN_STEP"
    spec["sequence"].append(
        dict(spec["sequence"][0], step_id="UNREACHABLE", source={"sheet": "Sequence", "row": 99})
    )
    codes = {item.code for item in validate_spec(spec, project_payload())}
    assert {
        "DUPLICATE_IO_ADDRESS",
        "SIGNAL_TYPE_MISMATCH",
        "UNIT_REQUIRED",
        "NEXT_STEP_MISSING",
        "UNREACHABLE_STEP",
    } <= codes


def test_cell_patch_does_not_mutate_source(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    spec, _ = parse_workbook(generate_workbook(project_payload(), kind="example"), settings)
    old_name = spec["signals"][0]["display_name"]
    updated = patch_cells(
        spec,
        [{"sheet": "Signals", "row": 2, "column": "display_name", "value": "新名称"}],
    )
    assert spec["signals"][0]["display_name"] == old_name
    assert updated["signals"][0]["display_name"] == "新名称"


def test_archive_security_limits(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, max_xlsx_entries=1)
    content = generate_workbook(project_payload(), kind="blank")
    try:
        inspect_xlsx_archive(content, settings)
    except WorkbookInputError as exc:
        assert exc.code == "XLSX_TOO_MANY_ENTRIES"
    else:
        raise AssertionError("entry limit should reject workbook")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escape.xml", "bad")
        archive.writestr("[Content_Types].xml", "types")
    settings = Settings(data_dir=tmp_path)
    try:
        inspect_xlsx_archive(buffer.getvalue(), settings)
    except WorkbookInputError as exc:
        assert exc.code == "XLSX_PATH_TRAVERSAL"
    else:
        raise AssertionError("path traversal should be rejected")


def test_archive_rejects_active_content_duplicate_and_windows_paths(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    cases = [
        ("xl/vbaProject.bin", "XLSX_ACTIVE_CONTENT"),
        ("xl/activeX/activeX1.bin", "XLSX_ACTIVE_CONTENT"),
        ("C:/escape.xml", "XLSX_PATH_TRAVERSAL"),
        ("xl/./workbook.xml", "XLSX_PATH_TRAVERSAL"),
    ]
    for name, expected_code in cases:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "types")
            archive.writestr(name, "bad")
        try:
            inspect_xlsx_archive(buffer.getvalue(), settings)
        except WorkbookInputError as exc:
            assert exc.code == expected_code
        else:
            raise AssertionError(f"{name} should be rejected")

    duplicate = io.BytesIO()
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("[Content_Types].xml", "types")
        archive.writestr("xl/workbook.xml", "first")
        archive.writestr("xl/workbook.xml", "second")
    try:
        inspect_xlsx_archive(duplicate.getvalue(), settings)
    except WorkbookInputError as exc:
        assert exc.code == "XLSX_DUPLICATE_ENTRY"
    else:
        raise AssertionError("duplicate archive entries should be rejected")


def test_project_import_revision_and_concurrency(
    client: TestClient,
    imported_example: dict,
) -> None:
    revision = imported_example["revision"]
    import_id = imported_example["import"]["id"]
    original_artifact = imported_example["artifact"]["sha256"]
    edited = client.patch(
        f"/api/v1/imports/{import_id}/cells",
        json={
            "expected_revision": revision["revision"],
            "edits": [
                {"sheet": "Signals", "row": 2, "column": "display_name", "value": "托盘存在"}
            ],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["id"] != revision["id"]
    conflict = client.patch(
        f"/api/v1/imports/{import_id}/cells",
        json={
            "expected_revision": 999,
            "edits": [
                {"sheet": "Signals", "row": 2, "column": "display_name", "value": "冲突"}
            ],
        },
    )
    assert conflict.status_code == 409
    assert imported_example["artifact"]["sha256"] == original_artifact


def test_lock_gate_and_snapshot(
    client: TestClient,
    imported_example: dict,
    locked_example: dict,
) -> None:
    revision = imported_example["revision"]
    blocked = client.post(
        f"/api/v1/spec-revisions/{revision['id']}/lock",
        json={"confirmed_by": "测试工程师", "expected_revision": revision["revision"]},
    )
    assert blocked.status_code == 409
    assert locked_example["locked"] is True
    artifact = client.get(f"/api/v1/artifacts/{locked_example['snapshot_artifact_id']}")
    assert artifact.status_code == 200
    assert b"machine_spec" in artifact.content
