from __future__ import annotations

from copy import deepcopy

from kongpu_api.version_compare import compare_version_snapshots


def _snapshot(commit_id: str, git_sha: str) -> dict:
    source = {"sheet": "Signals", "row": 2}
    return {
        "commit": {"id": commit_id, "git_sha": git_sha},
        "files": {"src/Main.st": "PROGRAM Main\nEND_PROGRAM\n"},
        "machine_spec": {
            "schema_version": "1.0",
            "template_version": "1.0",
            "project": {"cycle_target": 10, "cycle_unit": "s"},
            "plc_target": {"brand": "Mitsubishi", "series": "FX5U"},
            "components": [
                {"component_id": "CYL-1", "display_name": "Cylinder", "source": {"sheet": "Components", "row": 2}}
            ],
            "signals": [
                {"signal_id": "DO-1", "display_name": "Extend", "address": "Y0", "direction": "DO", "data_type": "BOOL", "source": source}
            ],
            "sequence": [
                {"step_id": "STEP-1", "next_step_id": "STEP-1", "source": {"sheet": "Sequence", "row": 2}}
            ],
            "interlocks": [],
            "exceptions": [],
        },
        "control_ir": {
            "ir_version": "1",
            "generator_version": "1",
            "target": {"series": "FX5U"},
            "project": {"id": "P-1"},
            "components": [{"component_id": "CYL-1"}],
            "signals": [{"id": "DO-1", "address": "Y0"}],
            "steps": [{"id": "STEP-1", "next_step_id": "STEP-1"}],
            "interlocks": [],
            "exceptions": [],
        },
        "test_spec": {"version": "1", "target": "FX5U", "tests": [{"id": "TC-1", "expected": "DO-1"}]},
        "generation": {"generator_version": "1", "machine_spec_hash": "a"},
        "verification": {"automated_review": {"status": "passed", "verification_level": "automatic"}},
        "vendor_configuration": {"environment": {"status": "not_detected", "verification_level": "unverified"}},
    }


def test_structured_comparison_is_stable_and_traces_semantic_changes() -> None:
    base = _snapshot("base", "a" * 40)
    target = deepcopy(base)
    target["commit"] = {"id": "target", "git_sha": "b" * 40}
    target["machine_spec"]["signals"][0]["address"] = "Y1"
    target["control_ir"]["signals"][0]["address"] = "Y1"
    target["test_spec"]["tests"][0]["expected"] = "DO-2"

    first = compare_version_snapshots(base, target, source_diff="")
    second = compare_version_snapshots(base, target, source_diff="")

    assert first["comparison_hash"] == second["comparison_hash"]
    sections = {item["id"]: item for item in first["sections"]}
    assert sections["machine_spec"]["status"] == "changed"
    assert sections["io"]["status"] == "changed"
    assert sections["control_ir"]["status"] == "changed"
    assert sections["test_spec"]["status"] == "changed"
    io_change = sections["io"]["items"][0]
    assert io_change["source_before"] == {"sheet": "Signals", "row": 2}
    assert io_change["fields"] == [
        {"field": "address", "before": "Y0", "after": "Y1"}
    ]
    assert sections["vendor_configuration"]["verification_level"] == "unverified"


def test_source_only_change_does_not_change_semantic_sections() -> None:
    base = _snapshot("base", "a" * 40)
    target = deepcopy(base)
    target["commit"] = {"id": "target", "git_sha": "b" * 40}
    target["files"]["src/Main.st"] += "// reviewed\n"

    comparison = compare_version_snapshots(
        base, target, source_diff="+// reviewed"
    )
    sections = {item["id"]: item for item in comparison["sections"]}
    assert sections["source"]["status"] == "changed"
    for section_id in (
        "machine_spec", "io", "parameters", "control_ir",
        "test_spec", "generation", "verification",
        "vendor_configuration",
    ):
        assert sections[section_id]["status"] == "unchanged"
