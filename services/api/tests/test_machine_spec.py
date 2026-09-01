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


def test_validation_uses_case_insensitive_iec_identifiers(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)
    spec, _ = parse_workbook(generate_workbook(project_payload(), kind="example"), settings)
    first_signal = spec["signals"][0]["signal_id"]
    spec["sequence"][0]["entry_condition"] = first_signal.lower()
    spec["sequence"][0]["next_step_id"] = spec["sequence"][1]["step_id"].lower()
    codes = {item.code for item in validate_spec(spec, project_payload())}
    assert "SIGNAL_REFERENCE_MISSING" not in codes
    assert "NEXT_STEP_MISSING" not in codes
    assert "UNREACHABLE_STEP" not in codes

    duplicate = dict(spec["signals"][0])
    duplicate["signal_id"] = first_signal.swapcase()
    duplicate["source"] = {"sheet": "Signals", "row": 999}
    duplicate["address"] = "X7F"
    spec["signals"].append(duplicate)
    assert "DUPLICATE_ID" in {item.code for item in validate_spec(spec, project_payload())}


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


def test_validation_report_is_bound_deterministic_and_read_only(
    client: TestClient,
    project: dict,
    imported_example: dict,
) -> None:
    import_id = imported_example["import"]["id"]
    before = client.get(f"/api/v1/imports/{import_id}").json()

    first = client.get(
        f"/api/v1/imports/{import_id}/validation-report",
        params={"kind": "json"},
    )
    second = client.get(
        f"/api/v1/imports/{import_id}/validation-report",
        params={"kind": "json"},
    )
    assert first.status_code == 200, first.text
    assert first.content == second.content
    assert first.headers["etag"] == second.headers["etag"]
    assert first.headers["content-disposition"].endswith(
        f'{project["code"]}-validation-report.json"'
    )

    report = first.json()
    assert report["schema"] == "kongpu-validation-report/v1"
    assert report["project"]["id"] == project["id"]
    assert report["project"]["plc_target"]["model"] == project["plc_model"]
    assert report["import"]["id"] == import_id
    assert (
        report["import"]["source_artifact"]["sha256"]
        == imported_example["artifact"]["sha256"]
    )
    assert report["spec_revision"]["id"] == imported_example["revision"]["id"]
    assert (
        report["spec_revision"]["content_hash"]
        == imported_example["revision"]["content_hash"]
    )
    assert report["summary"]["total"] == len(report["issues"])
    assert sum(report["summary"]["by_severity"].values()) == len(report["issues"])
    required_issue_fields = {
        "code", "severity", "title", "detail", "sheet", "row_number",
        "column_name", "entity_id", "resolved", "accepted_reason",
    }
    assert all(required_issue_fields <= issue.keys() for issue in report["issues"])

    markdown = client.get(
        f"/api/v1/imports/{import_id}/validation-report",
        params={"kind": "markdown"},
    )
    assert markdown.status_code == 200, markdown.text
    assert "# 控谱 MachineSpec 校验报告" in markdown.text
    assert imported_example["artifact"]["sha256"] in markdown.text
    assert imported_example["revision"]["content_hash"] in markdown.text

    after = client.get(f"/api/v1/imports/{import_id}").json()
    assert after == before
    assert client.get(
        f"/api/v1/imports/{import_id}/validation-report",
        params={"kind": "csv"},
    ).status_code == 422


def test_validation_report_keeps_projects_isolated(
    client: TestClient,
    imported_example: dict,
) -> None:
    other_project_response = client.post(
        "/api/v1/projects",
        json={"name": "第二个项目", "customer_code": "OTHER"},
    )
    assert other_project_response.status_code == 201, other_project_response.text
    other_project = other_project_response.json()
    other_template = client.post(
        f"/api/v1/projects/{other_project['id']}/templates?kind=example"
    )
    assert other_template.status_code == 200, other_template.text
    other_import_response = client.post(
        f"/api/v1/projects/{other_project['id']}/imports",
        files={
            "file": (
                "Other.xlsx",
                other_template.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert other_import_response.status_code == 201, other_import_response.text
    other_import = other_import_response.json()

    first_report = client.get(
        f"/api/v1/imports/{imported_example['import']['id']}/validation-report",
        params={"kind": "json"},
    ).json()
    other_report = client.get(
        f"/api/v1/imports/{other_import['import']['id']}/validation-report",
        params={"kind": "json"},
    ).json()
    assert first_report["project"]["id"] != other_report["project"]["id"]
    assert (
        first_report["import"]["source_artifact"]["id"]
        != other_report["import"]["source_artifact"]["id"]
    )


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
