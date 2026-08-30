from __future__ import annotations

import json
from typing import Any


READINESS_SCHEMA = "kongpu-readiness/v1"


def build_readiness_report(
    *,
    project: dict[str, Any],
    target: dict[str, Any],
    generation_run: dict[str, Any] | None,
    commit: dict[str, Any] | None,
    review: dict[str, Any] | None,
    audit: dict[str, Any] | None,
    simulation: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    candidate_verification: dict[str, Any] | None,
    external_gates: list[dict[str, Any]],
) -> dict[str, Any]:
    checks = [
        _check("project", "项目目标", bool(project.get("id") and target.get("model")), "项目与 PLC 目标已解析。" if project.get("id") and target.get("model") else "缺少项目或 PLC 目标。"),
        _check("locked_spec", "锁定 MachineSpec", bool(generation_run and generation_run.get("locked")), "生成任务绑定不可变锁定规格。" if generation_run and generation_run.get("locked") else "生成任务未绑定锁定 MachineSpec。"),
        _check("program_commit", "当前程序 Commit", bool(commit and commit.get("git_sha")), "当前分支存在不可变 Commit。" if commit and commit.get("git_sha") else "当前生成分支没有 Commit。"),
        _check("automated_review", "项目自动审核", bool(review and review.get("status") == "passed"), "自动审核已通过。" if review and review.get("status") == "passed" else "自动审核尚未通过。"),
        _check("static_audit", "生成物静态审计", bool(audit and audit.get("status") != "blocked"), "静态审计没有 blocker。" if audit and audit.get("status") != "blocked" else "静态审计缺失或存在 blocker。"),
        _check("reference_simulation", "控谱参考逻辑模拟", bool(simulation and simulation.get("status") == "review_ready"), "参考模拟已完成。" if simulation and simulation.get("status") == "review_ready" else "当前 Commit 尚无通过的参考模拟。"),
        _check("candidate", "交付候选 ZIP", bool(candidate), "候选包已生成。" if candidate else "尚未生成交付候选包。"),
        _check("candidate_integrity", "候选 ZIP 完整性复核", bool(candidate_verification and candidate_verification.get("status") == "passed"), "候选 ZIP 已独立复核。" if candidate_verification and candidate_verification.get("status") == "passed" else "候选 ZIP 尚未独立复核。"),
    ]
    automatic_ready = all(item["status"] == "ready" for item in checks)
    return {
        "schema": READINESS_SCHEMA,
        "project": {"id": project.get("id"), "code": project.get("code"), "name": project.get("name")},
        "target": target,
        "status": "ready_for_external_validation" if automatic_ready else "automatic_work_remaining",
        "verification_level": "automatic" if automatic_ready else "automatic_partial",
        "checks": checks,
        "summary": {
            "total": len(checks),
            "ready": sum(item["status"] == "ready" for item in checks),
            "remaining": sum(item["status"] != "ready" for item in checks),
            "external_pending": len(external_gates),
        },
        "external_validation_gates": external_gates,
        "claim_boundary": "本报告只反映本机确定性门禁；AutoShop/GX Works3 编译、厂商模拟、真实 PLC、硬件和电气工程师确认仍为 pending_external。",
    }


def _check(check_id: str, title: str, ready: bool, detail: str) -> dict[str, str]:
    return {
        "id": check_id,
        "title": title,
        "status": "ready" if ready else "remaining",
        "detail": detail,
    }


def stable_report_bytes(report: dict[str, Any]) -> bytes:
    return (json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
