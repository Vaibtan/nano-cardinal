"""Baseline schema — all 10 tables for Orion v3.2.

Revision ID: 001
Revises: None
Create Date: 2026-03-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.embeddings import VECTOR_DIMENSION

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── icps ─────────────────────────────────────────────
    op.create_table(
        "icps",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "config", sa.JSON(), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "weights", sa.JSON(), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active", sa.Boolean(),
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── sender_profiles ──────────────────────────────────
    op.create_table(
        "sender_profiles",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id", sa.String(), nullable=False, unique=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("current_title", sa.String(), nullable=True),
        sa.Column("current_company", sa.String(), nullable=True),
        sa.Column(
            "education", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "past_employers", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "cities_lived", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "hobbies_and_interests", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "investors", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "languages_spoken", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "conferences_attended", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── inbound_events ───────────────────────────────────
    # Created before leads so circular FK (leads.inbound_event_id)
    # can reference it.
    op.create_table(
        "inbound_events",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("company_domain", sa.String(), nullable=True),
        sa.Column(
            "raw_payload", sa.JSON(), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "processed", sa.Boolean(),
            server_default=sa.text("false"),
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column(
            "created_lead_id", sa.UUID(), nullable=True,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_inbound_events_processed",
        "inbound_events", ["processed"],
    )
    op.create_index(
        "idx_inbound_events_received",
        "inbound_events",
        [sa.text("received_at DESC")],
    )
    op.create_index(
        "idx_inbound_events_email",
        "inbound_events", ["email"],
    )

    # ── leads ────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Identity
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("linkedin_url", sa.String(), nullable=True),
        sa.Column("github_url", sa.String(), nullable=True),
        sa.Column("twitter_url", sa.String(), nullable=True),
        # Company
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("company_domain", sa.String(), nullable=True),
        sa.Column(
            "company_linkedin_url", sa.String(), nullable=True,
        ),
        sa.Column("company_size", sa.Integer(), nullable=True),
        sa.Column("industry", sa.String(), nullable=True),
        sa.Column("funding_stage", sa.String(), nullable=True),
        sa.Column(
            "total_funding_usd", sa.BigInteger(), nullable=True,
        ),
        sa.Column(
            "tech_stack", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Persona
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("seniority", sa.String(), nullable=True),
        sa.Column("department", sa.String(), nullable=True),
        # Enrichment
        sa.Column("enriched_data", sa.JSON(), nullable=True),
        sa.Column(
            "enrichment_status", sa.String(),
            server_default="PENDING",
        ),
        sa.Column(
            "enrichment_sources", sa.JSON(),
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "enrichment_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Scoring
        sa.Column("icp_score", sa.Float(), nullable=True),
        sa.Column(
            "icp_id", sa.UUID(),
            sa.ForeignKey("icps.id"),
            nullable=True,
        ),
        sa.Column(
            "icp_score_breakdown", sa.JSON(), nullable=True,
        ),
        # Outreach
        sa.Column(
            "outreach_status", sa.String(),
            server_default="UNTOUCHED",
        ),
        # Embedding (pgvector)
        sa.Column("embedding", Vector(VECTOR_DIMENSION), nullable=True),
        # Source tracking
        sa.Column(
            "source", sa.String(), server_default="MANUAL",
        ),
        sa.Column(
            "inbound_event_id", sa.UUID(),
            sa.ForeignKey(
                "inbound_events.id",
                use_alter=True,
                name="fk_leads_inbound_event_id",
            ),
            nullable=True,
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_leads_icp_score",
        "leads", [sa.text("icp_score DESC")],
    )
    op.create_index(
        "idx_leads_enrichment_status",
        "leads", ["enrichment_status"],
    )
    op.create_index(
        "idx_leads_source", "leads", ["source"],
    )
    op.create_index(
        "idx_leads_outreach_status",
        "leads", ["outreach_status"],
    )
    op.create_index(
        "idx_leads_updated_at",
        "leads", [sa.text("updated_at DESC")],
    )

    # Back-fill FK from inbound_events → leads.
    op.create_foreign_key(
        "fk_inbound_events_created_lead_id",
        "inbound_events", "leads",
        ["created_lead_id"], ["id"],
    )

    # ── signals ──────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lead_id", sa.UUID(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("company_domain", sa.String(), nullable=True),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("signal_title", sa.String(), nullable=False),
        sa.Column("signal_body", sa.Text(), nullable=True),
        sa.Column("signal_url", sa.String(), nullable=True),
        sa.Column("signal_strength", sa.Float(), nullable=True),
        sa.Column(
            "signal_hash", sa.String(), unique=True,
            nullable=True,
        ),
        sa.Column(
            "is_read", sa.Boolean(),
            server_default=sa.text("false"),
        ),
        sa.Column(
            "triggered_outreach", sa.Boolean(),
            server_default=sa.text("false"),
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_signals_lead_id", "signals", ["lead_id"],
    )
    op.create_index(
        "idx_signals_detected_at",
        "signals", [sa.text("detected_at DESC")],
    )
    op.create_index(
        "idx_signals_type", "signals", ["signal_type"],
    )
    op.create_index(
        "idx_signals_strength",
        "signals", [sa.text("signal_strength DESC")],
    )

    # ── sequences ────────────────────────────────────────
    op.create_table(
        "sequences",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "icp_id", sa.UUID(),
            sa.ForeignKey("icps.id"),
            nullable=True,
        ),
        sa.Column(
            "is_active", sa.Boolean(),
            server_default=sa.text("true"),
        ),
        sa.Column(
            "auto_enroll", sa.Boolean(),
            server_default=sa.text("false"),
        ),
        sa.Column(
            "auto_enroll_threshold", sa.Float(), nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── sequence_steps ───────────────────────────────────
    op.create_table(
        "sequence_steps",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "sequence_id", sa.UUID(),
            sa.ForeignKey("sequences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column(
            "step_type", sa.String(), server_default="OUTREACH",
        ),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column(
            "delay_days", sa.Integer(), server_default="0",
        ),
        sa.Column("template", sa.Text(), nullable=True),
        sa.Column(
            "use_ai_personalization", sa.Boolean(),
            server_default=sa.text("true"),
        ),
        sa.Column(
            "requires_approval", sa.Boolean(),
            server_default=sa.text("false"),
        ),
        sa.Column(
            "engagement_action", sa.String(), nullable=True,
        ),
        sa.UniqueConstraint(
            "sequence_id", "step_number",
            name="uq_sequence_step_number",
        ),
    )

    # ── lead_sequence_enrollments ────────────────────────
    op.create_table(
        "lead_sequence_enrollments",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lead_id", sa.UUID(),
            sa.ForeignKey("leads.id"),
            nullable=False,
        ),
        sa.Column(
            "sequence_id", sa.UUID(),
            sa.ForeignKey("sequences.id"),
            nullable=False,
        ),
        sa.Column(
            "current_step", sa.Integer(), server_default="1",
        ),
        sa.Column(
            "status", sa.String(), server_default="ACTIVE",
        ),
        sa.Column(
            "next_step_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "reply_received", sa.Boolean(),
            server_default=sa.text("false"),
        ),
        sa.Column("reply_body", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "lead_id", "sequence_id",
            name="uq_lead_sequence",
        ),
    )
    op.create_index(
        "idx_enrollments_next_step",
        "lead_sequence_enrollments",
        ["next_step_at"],
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    # ── personalization_drafts ───────────────────────────
    op.create_table(
        "personalization_drafts",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lead_id", sa.UUID(),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id", sa.UUID(),
            sa.ForeignKey("sender_profiles.id"),
            nullable=True,
        ),
        sa.Column(
            "sequence_id", sa.UUID(),
            sa.ForeignKey("sequences.id"),
            nullable=True,
        ),
        sa.Column(
            "sequence_step_id", sa.UUID(),
            sa.ForeignKey("sequence_steps.id"),
            nullable=True,
        ),
        sa.Column(
            "enrollment_id", sa.UUID(),
            sa.ForeignKey("lead_sequence_enrollments.id"),
            nullable=True,
        ),
        sa.Column("subject_line", sa.String(), nullable=True),
        sa.Column("email_body", sa.Text(), nullable=True),
        sa.Column("linkedin_message", sa.Text(), nullable=True),
        sa.Column(
            "personalization_hook", sa.Text(), nullable=True,
        ),
        sa.Column("hook_type", sa.String(), nullable=True),
        sa.Column("hook_strength", sa.Float(), nullable=True),
        sa.Column("signal_used", sa.String(), nullable=True),
        sa.Column("critique_score", sa.Float(), nullable=True),
        sa.Column(
            "critique_breakdown", sa.JSON(), nullable=True,
        ),
        sa.Column(
            "generation_iterations", sa.Integer(),
            server_default="1",
        ),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column(
            "status", sa.String(), server_default="DRAFT",
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_drafts_lead_id",
        "personalization_drafts", ["lead_id"],
    )
    op.create_index(
        "idx_drafts_enrollment_id",
        "personalization_drafts", ["enrollment_id"],
    )

    # ── outreach_logs ────────────────────────────────────
    op.create_table(
        "outreach_logs",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lead_id", sa.UUID(),
            sa.ForeignKey("leads.id"),
            nullable=True,
        ),
        sa.Column(
            "sequence_id", sa.UUID(),
            sa.ForeignKey("sequences.id"),
            nullable=True,
        ),
        sa.Column("step_number", sa.Integer(), nullable=True),
        sa.Column("step_type", sa.String(), nullable=True),
        sa.Column("channel", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "engagement_action", sa.String(), nullable=True,
        ),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "replied_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "draft_id", sa.UUID(),
            sa.ForeignKey("personalization_drafts.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_outreach_logs_lead",
        "outreach_logs", ["lead_id"],
    )


def downgrade() -> None:
    op.drop_table("outreach_logs")
    op.drop_table("personalization_drafts")
    op.drop_table("lead_sequence_enrollments")
    op.drop_table("sequence_steps")
    op.drop_table("sequences")
    op.drop_table("signals")
    op.drop_constraint(
        "fk_inbound_events_created_lead_id",
        "inbound_events", type_="foreignkey",
    )
    op.drop_table("leads")
    op.drop_table("inbound_events")
    op.drop_table("sender_profiles")
    op.drop_table("icps")
    op.execute("DROP EXTENSION IF EXISTS vector")
