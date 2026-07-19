"""update demo schedules to hourly staggered

Revision ID: 96119774d656
Revises: f6cea5e9817c
Create Date: 2026-07-19 13:34:02.009812

"""
from datetime import datetime, timedelta, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96119774d656'
down_revision: Union[str, Sequence[str], None] = 'f6cea5e9817c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_INTERVAL_SECONDS = 3600
DEMO_SCHEDULE_IDS = [
    "demo_sch_1",
    "demo_sch_2",
    "demo_sch_3",
    "demo_sch_4",
    "demo_sch_5",
]


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    schedules_table = sa.table(
        "sourcing_schedules",
        sa.column("id"),
        sa.column("interval_seconds"),
        sa.column("next_run_at"),
        sa.column("updated_at"),
    )

    total = len(DEMO_SCHEDULE_IDS)
    for idx, schedule_id in enumerate(DEMO_SCHEDULE_IDS):
        stagger_seconds = (DEFAULT_INTERVAL_SECONDS // total) * idx
        next_run_at = now + timedelta(seconds=stagger_seconds)
        bind.execute(
            sa.update(schedules_table)
            .where(schedules_table.c.id == schedule_id)
            .values(
                interval_seconds=DEFAULT_INTERVAL_SECONDS,
                next_run_at=next_run_at,
                updated_at=now,
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    schedules_table = sa.table(
        "sourcing_schedules",
        sa.column("id"),
        sa.column("interval_seconds"),
        sa.column("next_run_at"),
        sa.column("updated_at"),
    )

    for schedule_id in DEMO_SCHEDULE_IDS:
        bind.execute(
            sa.update(schedules_table)
            .where(schedules_table.c.id == schedule_id)
            .values(
                interval_seconds=300,
                next_run_at=now,
                updated_at=now,
            )
        )
