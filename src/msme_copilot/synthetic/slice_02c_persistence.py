"""Persistence for approved Slice 02C tables."""

import json

from sqlalchemy import create_engine, text

from msme_copilot.config import get_settings
from msme_copilot.synthetic.models import SyntheticWorld
from msme_copilot.synthetic.persistence import persist_merchants
from msme_copilot.synthetic.slice_02c import LendingWorld


_TABLES = {
    "applications": (
        "application_id",
        {
            "application_id",
            "tenant_id",
            "merchant_id",
            "application_date",
            "application_status",
            "loan_purpose",
            "requested_amount",
            "requested_tenor_months",
            "as_of_date",
            "created_at",
        },
    ),
    "loan_requests": ("loan_request_id", None),
    "historical_loans": ("loan_id", None),
    "repayment_schedule": ("loan_id, installment_number", None),
    "repayment_transactions": ("repayment_transaction_id", None),
    "loan_outcomes": (
        "outcome_id",
        (
            "outcome_id",
            "tenant_id",
            "loan_id",
            "outcome_date",
            "outcome_code",
            "days_past_due",
            "loss_amount",
            "available_at",
        ),
    ),
    "policies": ("policy_id", None),
    "policy_clauses": ("clause_id", None),
    "documents": (
        "document_id",
        {
            "document_id",
            "tenant_id",
            "document_name",
            "origin",
            "storage_uri",
            "content_hash",
            "document_version",
            "authorization_metadata",
            "available_at",
        },
    ),
    "document_entities": ("document_id, entity_type, entity_id", None),
    "fact_authority_rules": ("rule_id", None),
    "gt_facts": (
        "fact_id",
        ("fact_id", "tenant_id", "entity_type", "entity_id", "fact_type", "value_json", "document_id", "version"),
    ),
    "gt_spans": (
        "span_id",
        ("span_id", "tenant_id", "document_id", "version", "page", "char_start", "char_end", "verbatim_text"),
    ),
    "golden_questions": ("question_id", None),
}


def persist_lending_world(canonical: SyntheticWorld, lending: LendingWorld) -> None:
    """Insert/update 02C rows in FK-safe order without persisting hidden state."""
    persist_merchants(canonical)
    settings = get_settings()
    engine = create_engine(settings.test_database_url or settings.database_url)
    with engine.begin() as connection:
        for table in (
            "applications",
            "loan_requests",
            "historical_loans",
            "repayment_schedule",
            "repayment_transactions",
            "loan_outcomes",
            "policies",
            "policy_clauses",
            "documents",
            "document_entities",
            "fact_authority_rules",
            "gt_facts",
            "gt_spans",
            "golden_questions",
        ):
            rows = lending.table_rows()[table]
            if not rows:
                continue
            allowed = _TABLES[table][1]
            cleaned = [
                {k: v for k, v in row.values.items() if allowed is None or k in allowed}
                for row in rows
            ]
            columns = tuple(cleaned[0])
            quoted = ", ".join(columns)
            json_columns = {"authorization_metadata", "value_json", "expected_route", "required_evidence",
                            "supporting_evidence", "forbidden_evidence", "expected_answer"}
            binds = ", ".join(f"CAST(:{c} AS jsonb)" if c in json_columns else f":{c}" for c in columns)
            key = _TABLES[table][0]
            updates = ", ".join(
                f"{c}=EXCLUDED.{c}" for c in columns if c not in {x.strip() for x in key.split(",")}
            )
            action = f"DO UPDATE SET {updates}" if updates else "DO NOTHING"
            statement = text(
                f"INSERT INTO {('core' if table in {'applications', 'loan_requests'} else 'lending' if table in {'historical_loans', 'repayment_schedule', 'repayment_transactions', 'loan_outcomes'} else 'docs' if table in {'documents', 'document_entities', 'policies', 'policy_clauses'} else 'truth' if table in {'fact_authority_rules', 'gt_facts', 'gt_spans'} else 'eval')}.{table} ({quoted}) VALUES ({binds}) ON CONFLICT ({key}) {action}"
            )
            for row in cleaned:
                for column in json_columns & set(row):
                    if isinstance(row[column], (dict, list)):
                        row[column] = json.dumps(row[column], sort_keys=True)
                connection.execute(statement, row)
    engine.dispose()
