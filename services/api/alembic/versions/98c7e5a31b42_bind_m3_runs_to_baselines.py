"""Bind M3 evidence runs to immutable program and TestSpec baselines."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "98c7e5a31b42"
down_revision: Union[str, Sequence[str], None] = "6f4a2b8c1d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("generation_audits") as batch:
        batch.add_column(sa.Column("program_commit_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_generation_audits_program_commit_id", "program_commits", ["program_commit_id"], ["id"])
        batch.create_index("ix_generation_audits_program_commit_id", ["program_commit_id"], unique=False)
    with op.batch_alter_table("compile_runs") as batch:
        batch.add_column(sa.Column("program_commit_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_compile_runs_program_commit_id", "program_commits", ["program_commit_id"], ["id"])
        batch.create_index("ix_compile_runs_program_commit_id", ["program_commit_id"], unique=False)
    with op.batch_alter_table("simulation_runs") as batch:
        batch.add_column(sa.Column("program_commit_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("test_spec_revision_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_simulation_runs_program_commit_id", "program_commits", ["program_commit_id"], ["id"])
        batch.create_foreign_key("fk_simulation_runs_test_spec_revision_id", "test_spec_revisions", ["test_spec_revision_id"], ["id"])
        batch.create_index("ix_simulation_runs_program_commit_id", ["program_commit_id"], unique=False)
        batch.create_index("ix_simulation_runs_test_spec_revision_id", ["test_spec_revision_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("simulation_runs") as batch:
        batch.drop_index("ix_simulation_runs_test_spec_revision_id")
        batch.drop_index("ix_simulation_runs_program_commit_id")
        batch.drop_constraint("fk_simulation_runs_test_spec_revision_id", type_="foreignkey")
        batch.drop_constraint("fk_simulation_runs_program_commit_id", type_="foreignkey")
        batch.drop_column("test_spec_revision_id")
        batch.drop_column("program_commit_id")
    with op.batch_alter_table("compile_runs") as batch:
        batch.drop_index("ix_compile_runs_program_commit_id")
        batch.drop_constraint("fk_compile_runs_program_commit_id", type_="foreignkey")
        batch.drop_column("program_commit_id")
    with op.batch_alter_table("generation_audits") as batch:
        batch.drop_index("ix_generation_audits_program_commit_id")
        batch.drop_constraint("fk_generation_audits_program_commit_id", type_="foreignkey")
        batch.drop_column("program_commit_id")
