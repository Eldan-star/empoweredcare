"""ephi fields and alert levels

Revision ID: 9ddb11e10486
Revises: e43670afe39f
Create Date: 2026-10-10 23:18:17.318192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9ddb11e10486'
down_revision: Union[str, Sequence[str], None] = 'e43670afe39f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    """EPHI alignment (docs/EPHI_ALIGNMENT.md): alert levels in EPHI terms, report
    timeliness, EPHI case classifications and the rumour-log timeline on signals."""
    # Alerts: colour tiers become EPHI levels. The table is empty before M5; any rows are
    # carried over (RED and ORANGE both meet the action threshold, YELLOW is a signal).
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_alerts_tier"))
        batch_op.alter_column("tier", new_column_name="level", existing_type=sa.String(length=10),
                              existing_nullable=False)
        batch_op.add_column(sa.Column("priority", sa.Float(), nullable=True))
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_alerts_level"), ["level"], unique=False)
    op.execute("UPDATE alerts SET level = 'action' WHERE level IN ('RED', 'ORANGE')")
    op.execute("UPDATE alerts SET level = 'signal' WHERE level = 'YELLOW'")

    with op.batch_alter_table("indicator_counts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reports_on_time", sa.Integer(), nullable=True))

    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.add_column(sa.Column("syndrome", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("candidate_diseases", JSON, nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("onset_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("verification_result", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("investigated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("intervention_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column("classification", existing_type=sa.VARCHAR(length=20),
                              type_=sa.String(length=30), existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("signals", schema=None) as batch_op:
        batch_op.alter_column("classification", existing_type=sa.String(length=30),
                              type_=sa.VARCHAR(length=20), existing_nullable=True)
        for col in ("intervention_at", "investigated_at", "verification_result", "verified_at",
                    "notified_at", "seen_at", "onset_date", "candidate_diseases", "syndrome"):
            batch_op.drop_column(col)

    with op.batch_alter_table("indicator_counts", schema=None) as batch_op:
        batch_op.drop_column("reports_on_time")

    op.execute("UPDATE alerts SET level = 'RED' WHERE level = 'action'")
    op.execute("UPDATE alerts SET level = 'ORANGE' WHERE level = 'alert'")
    op.execute("UPDATE alerts SET level = 'YELLOW' WHERE level = 'signal'")
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_alerts_level"))
        batch_op.drop_column("priority")
        batch_op.alter_column("level", new_column_name="tier", existing_type=sa.String(length=10),
                              existing_nullable=False)
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_alerts_tier"), ["tier"], unique=False)
