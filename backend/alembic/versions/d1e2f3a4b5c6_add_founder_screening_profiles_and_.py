"""add founder screening profiles and imports

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-07-21 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("founders", sa.Column("linkedin_url_normalized", sa.String(), nullable=True))
    op.add_column(
        "founders",
        sa.Column(
            "enrichment_policy",
            sa.String(),
            nullable=False,
            server_default="AUTO",
        ),
    )
    op.create_index("ix_founders_linkedin_url_normalized", "founders", ["linkedin_url_normalized"], unique=False)
    op.create_index("ix_founders_enrichment_policy", "founders", ["enrichment_policy"], unique=False)

    op.create_table(
        "founder_csv_imports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_checksum", sa.String(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_founder_csv_imports_file_checksum", "founder_csv_imports", ["file_checksum"], unique=False)

    op.create_table(
        "founder_screening_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("founder_id", sa.String(), nullable=False),
        sa.Column("external_record_id", sa.String(), nullable=True),
        sa.Column("project_name", sa.String(), nullable=True),
        sa.Column("project_name_normalized", sa.String(), nullable=True),
        sa.Column("project_summary", sa.Text(), nullable=True),
        sa.Column("founder_role", sa.String(), nullable=True),
        sa.Column("sector", sa.String(), nullable=True),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("institution_or_program", sa.String(), nullable=True),
        sa.Column("school_or_lab", sa.String(), nullable=True),
        sa.Column("cohort_year", sa.String(), nullable=True),
        sa.Column("institution_affiliation_basis", sa.Text(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("city_normalized", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("city_basis", sa.String(), nullable=True),
        sa.Column("city_confidence", sa.Float(), nullable=True),
        sa.Column("target_market_geography", sa.String(), nullable=True),
        sa.Column("website_url", sa.String(), nullable=True),
        sa.Column("primary_source_url", sa.String(), nullable=True),
        sa.Column("source_locator", sa.String(), nullable=True),
        sa.Column("source_date", sa.String(), nullable=True),
        sa.Column("funding_status", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("funding_check_as_of", sa.String(), nullable=True),
        sa.Column("funding_check_confidence", sa.Float(), nullable=True),
        sa.Column("funding_notes", sa.Text(), nullable=True),
        sa.Column("founder_score", sa.Integer(), nullable=True),
        sa.Column("founder_score_rationale", sa.Text(), nullable=True),
        sa.Column("vision_product_score", sa.Integer(), nullable=True),
        sa.Column("vision_product_rationale", sa.Text(), nullable=True),
        sa.Column("differentiation_score", sa.Integer(), nullable=True),
        sa.Column("differentiation_rationale", sa.Text(), nullable=True),
        sa.Column("traction_score", sa.Integer(), nullable=True),
        sa.Column("traction_rationale", sa.Text(), nullable=True),
        sa.Column("evidence_confidence", sa.Float(), nullable=True),
        sa.Column("evidence_coverage", sa.Float(), nullable=True),
        sa.Column("individual_attribution_confidence", sa.Float(), nullable=True),
        sa.Column("evaluation_scope", sa.Text(), nullable=True),
        sa.Column("key_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("counter_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("unknowns", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("next_diligence_action", sa.Text(), nullable=True),
        sa.Column("recommended", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recommendation_trigger", sa.String(), nullable=False, server_default="INCOMPLETE_EVALUATION"),
        sa.Column("recommended_reason", sa.Text(), nullable=True),
        sa.Column("evaluation_version", sa.String(), nullable=False, server_default="associate_screen_v1"),
        sa.Column("pedigree_used_in_scoring", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("import_status", sa.String(), nullable=True),
        sa.Column("research_priority", sa.String(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("imported_associate_call_recommended", sa.Boolean(), nullable=True),
        sa.Column("imported_recommendation_trigger", sa.String(), nullable=True),
        sa.Column("imported_recommended_reason", sa.Text(), nullable=True),
        sa.Column("produced_by", sa.String(), nullable=True),
        sa.Column("import_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("founder_score IS NULL OR founder_score BETWEEN 0 AND 100", name="ck_founder_screening_profiles_founder_score"),
        sa.CheckConstraint("vision_product_score IS NULL OR vision_product_score BETWEEN 0 AND 100", name="ck_founder_screening_profiles_vision_product_score"),
        sa.CheckConstraint("differentiation_score IS NULL OR differentiation_score BETWEEN 0 AND 100", name="ck_founder_screening_profiles_differentiation_score"),
        sa.CheckConstraint("traction_score IS NULL OR traction_score BETWEEN 0 AND 100", name="ck_founder_screening_profiles_traction_score"),
        sa.CheckConstraint("city_confidence IS NULL OR (city_confidence >= 0 AND city_confidence <= 1)", name="ck_founder_screening_profiles_city_confidence"),
        sa.CheckConstraint("funding_check_confidence IS NULL OR (funding_check_confidence >= 0 AND funding_check_confidence <= 1)", name="ck_founder_screening_profiles_funding_check_confidence"),
        sa.CheckConstraint("evidence_confidence IS NULL OR (evidence_confidence >= 0 AND evidence_confidence <= 1)", name="ck_founder_screening_profiles_evidence_confidence"),
        sa.CheckConstraint("evidence_coverage IS NULL OR (evidence_coverage >= 0 AND evidence_coverage <= 1)", name="ck_founder_screening_profiles_evidence_coverage"),
        sa.CheckConstraint("individual_attribution_confidence IS NULL OR (individual_attribution_confidence >= 0 AND individual_attribution_confidence <= 1)", name="ck_founder_screening_profiles_individual_attribution_confidence"),
        sa.ForeignKeyConstraint(["founder_id"], ["founders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["import_id"], ["founder_csv_imports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("founder_id", "evaluation_version", name="uq_founder_screening_profile_founder_version"),
    )
    op.create_index("ix_founder_screening_profiles_founder_id", "founder_screening_profiles", ["founder_id"], unique=False)
    op.create_index("ix_founder_screening_profiles_project_name_normalized", "founder_screening_profiles", ["project_name_normalized"], unique=False)
    op.create_index("ix_founder_screening_profiles_city_normalized", "founder_screening_profiles", ["city_normalized"], unique=False)
    op.create_index("ix_founder_screening_profiles_import_id", "founder_screening_profiles", ["import_id"], unique=False)
    op.create_index("ix_founder_screening_profiles_recommended", "founder_screening_profiles", ["recommended"], unique=False)
    op.create_index("ix_founder_screening_profiles_recommendation_trigger", "founder_screening_profiles", ["recommendation_trigger"], unique=False)
    op.create_index("ix_founder_screening_profiles_evaluation_version", "founder_screening_profiles", ["evaluation_version"], unique=False)
    op.create_index("ix_founder_screening_profiles_external_record_id_unique", "founder_screening_profiles", ["external_record_id"], unique=True, postgresql_where=sa.text("external_record_id IS NOT NULL"))
    op.create_index("ix_founder_screening_profiles_recommended_city", "founder_screening_profiles", ["recommended", "city_normalized"], unique=False)
    op.create_index("ix_founder_screening_profiles_recommended_institution", "founder_screening_profiles", ["recommended", "institution_or_program"], unique=False)
    op.create_index("ix_founder_screening_profiles_source_type", "founder_screening_profiles", ["source_type"], unique=False)
    op.create_index("ix_founder_screening_profiles_sector", "founder_screening_profiles", ["sector"], unique=False)
    op.create_index("ix_founder_screening_profiles_funding_status", "founder_screening_profiles", ["funding_status"], unique=False)
    op.create_index("ix_founder_screening_profiles_cohort_year", "founder_screening_profiles", ["cohort_year"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_founder_screening_profiles_cohort_year", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_funding_status", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_sector", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_source_type", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_recommended_institution", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_recommended_city", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_external_record_id_unique", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_evaluation_version", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_recommendation_trigger", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_recommended", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_import_id", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_city_normalized", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_project_name_normalized", table_name="founder_screening_profiles")
    op.drop_index("ix_founder_screening_profiles_founder_id", table_name="founder_screening_profiles")
    op.drop_table("founder_screening_profiles")

    op.drop_index("ix_founder_csv_imports_file_checksum", table_name="founder_csv_imports")
    op.drop_table("founder_csv_imports")

    op.drop_index("ix_founders_enrichment_policy", table_name="founders")
    op.drop_index("ix_founders_linkedin_url_normalized", table_name="founders")
    op.drop_column("founders", "enrichment_policy")
    op.drop_column("founders", "linkedin_url_normalized")
