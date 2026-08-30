"""Scope Git commit SHA uniqueness to its program branch."""
from typing import Sequence, Union

from alembic import op


revision: str = "d7a1c2e9304f"
down_revision: Union[str, Sequence[str], None] = "c4e9f1a7206b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_program_commits_git_sha", table_name="program_commits")
    op.create_index(
        "ix_program_commits_git_sha",
        "program_commits",
        ["git_sha"],
        unique=False,
    )
    op.create_index(
        "uq_program_commit_branch_sha",
        "program_commits",
        ["branch_id", "git_sha"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_program_commit_branch_sha", table_name="program_commits"
    )
    op.drop_index("ix_program_commits_git_sha", table_name="program_commits")
    op.create_index(
        "ix_program_commits_git_sha",
        "program_commits",
        ["git_sha"],
        unique=True,
    )
