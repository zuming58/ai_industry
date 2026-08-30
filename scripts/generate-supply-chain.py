from __future__ import annotations

import argparse
from pathlib import Path

from supply_chain import (
    PYTHON_LOCK_PATH,
    SupplyChainError,
    build_python_lock_from_pip_report,
    check_supply_chain_documents,
    write_supply_chain_documents,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic SBOM, dependency audit, and license inventory."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if checked-in supply-chain outputs differ from deterministic generation.",
    )
    parser.add_argument(
        "--pip-report",
        type=Path,
        help="Normalize a pip --report file into the reviewed Windows/Python 3.12 lock before generating outputs.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.pip_report:
            lock_content = build_python_lock_from_pip_report(root, args.pip_report.resolve())
            (root / PYTHON_LOCK_PATH).write_bytes(lock_content)
            print(f"Updated {PYTHON_LOCK_PATH.as_posix()} from pip report.")
        if args.check:
            stale = check_supply_chain_documents(root)
            if stale:
                print("Supply-chain outputs are missing or stale:")
                for path in stale:
                    print(f"- {path.as_posix()}")
                return 1
            print("Supply-chain outputs are current.")
            return 0
        written = write_supply_chain_documents(root)
    except (OSError, SupplyChainError) as exc:
        print(f"Supply-chain generation failed: {exc}")
        return 2
    print(f"Generated {len(written)} deterministic supply-chain outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
