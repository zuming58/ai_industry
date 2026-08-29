from __future__ import annotations

import argparse

import httpx


DEMO_NAME = "FX5U 托盘举升示例"


def require(response: httpx.Response):
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a complete local Kongpu demo project.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        projects = require(client.get("/api/v1/projects", params={"include_archived": True}))
        project = next((item for item in projects if item["name"] == DEMO_NAME), None)
        if project is None:
            project = require(
                client.post(
                    "/api/v1/projects",
                    json={
                        "name": DEMO_NAME,
                        "customer_code": "DEMO-001",
                        "plc_brand": "三菱电机",
                        "plc_series": "MELSEC iQ-F",
                        "plc_model": "FX5U-64MT/ES",
                    },
                )
            )

        if not project.get("current_import_id"):
            workbook = client.post(f"/api/v1/projects/{project['id']}/templates", params={"kind": "example"})
            workbook.raise_for_status()
            require(
                client.post(
                    f"/api/v1/projects/{project['id']}/imports",
                    files={"file": ("MachineSpec_example.xlsx", workbook.content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                )
            )
            project = require(client.get(f"/api/v1/projects/{project['id']}"))

        revision = require(client.get(f"/api/v1/spec-revisions/{project['current_spec_revision_id']}"))
        if revision["status"] != "locked":
            for issue in revision["issues"]:
                if issue["severity"] == "warning" and not issue["resolved"]:
                    revision = require(
                        client.post(
                            f"/api/v1/spec-revisions/{revision['id']}/warnings/{issue['id']}/accept",
                            json={"reason": "本机演示种子已复核", "expected_revision": revision["revision"]},
                        )
                    )
            confirmed = {item["view"] for item in revision["confirmations"]}
            for view in revision["required_views"]:
                if view not in confirmed:
                    revision = require(
                        client.put(
                            f"/api/v1/spec-revisions/{revision['id']}/confirmations/{view}",
                            json={"confirmed_by": "本机演示种子", "expected_revision": revision["revision"]},
                        )
                    )
            locked = require(
                client.post(
                    f"/api/v1/spec-revisions/{revision['id']}/lock",
                    json={"confirmed_by": "本机演示种子", "expected_revision": revision["revision"]},
                )
            )
            revision = locked["revision"]

        branches = require(client.get(f"/api/v1/projects/{project['id']}/branches"))
        if not branches:
            require(
                client.post(
                    f"/api/v1/projects/{project['id']}/generation-runs",
                    json={"spec_revision_id": revision["id"], "branch_name": "generated/demo-baseline"},
                )
            )

        print(f"Seed ready: {project['code']} {DEMO_NAME}")


if __name__ == "__main__":
    main()

