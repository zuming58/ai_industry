"""Add immutable release candidate evidence ledger."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2c4e6f8b0d1"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "release_candidate_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("release_candidate_id", sa.String(length=36), nullable=False),
        sa.Column("source_artifact_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_kind", sa.String(length=40), nullable=False),
        sa.Column("verification_level", sa.String(length=40), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["release_candidate_id"], ["release_candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["source_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("release_candidate_id", "source_artifact_id", "evidence_kind", name="uq_release_candidate_evidence_source_kind"),
    )
    op.create_index("ix_release_candidate_evidence_project_id", "release_candidate_evidence", ["project_id"])
    op.create_index("ix_release_candidate_evidence_release_candidate_id", "release_candidate_evidence", ["release_candidate_id"])
    op.create_index("ix_release_candidate_evidence_source_artifact_id", "release_candidate_evidence", ["source_artifact_id"])
    op.create_index("ix_release_candidate_evidence_evidence_kind", "release_candidate_evidence", ["evidence_kind"])


def downgrade() -> None:
    op.drop_index("ix_release_candidate_evidence_evidence_kind", table_name="release_candidate_evidence")
    op.drop_index("ix_release_candidate_evidence_source_artifact_id", table_name="release_candidate_evidence")
    op.drop_index("ix_release_candidate_evidence_release_candidate_id", table_name="release_candidate_evidence")
    op.drop_index("ix_release_candidate_evidence_project_id", table_name="release_candidate_evidence")
    op.drop_table("release_candidate_evidence")
