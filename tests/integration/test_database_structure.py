from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import NUMERIC, DateTime

import pytest

pytestmark = pytest.mark.integration


def test_schemas_and_tables(db_engine) -> None:
    inspector = inspect(db_engine)
    expected_schemas = {"authz", "core", "source", "lending", "docs", "truth", "eval"}
    assert expected_schemas <= set(inspector.get_schema_names())
    expected = {
        "authz": {"tenants", "branches", "analysts", "analyst_scopes"},
        "core": {"seasonality_profiles", "merchants", "persons", "merchant_persons", "addresses", "merchant_addresses", "applications", "loan_requests"},
        "source": {"merchant_bank_accounts", "bank_transactions", "banking_metrics", "merchant_gstins", "gst_returns", "financial_statements", "bureau_snapshots", "digital_payment_metrics", "digital_sales_daily"},
        "lending": {"historical_loans", "repayment_schedule", "repayment_transactions", "loan_outcomes", "reconciliation_results"},
        "docs": {"documents", "document_entities", "policies", "policy_clauses"},
        "truth": {"fact_authority_rules", "gt_facts", "gt_spans"},
        "eval": {"golden_questions"},
    }
    for schema, tables in expected.items():
        assert tables <= set(inspector.get_table_names(schema=schema))


def test_critical_keys_indexes_and_foreign_keys(db_engine) -> None:
    inspector = inspect(db_engine)
    assert {"analyst_id", "branch_id", "valid_from"} == set(inspector.get_pk_constraint("analyst_scopes", "authz")["constrained_columns"])
    assert {"loan_id", "installment_number"} == set(inspector.get_pk_constraint("repayment_schedule", "lending")["constrained_columns"])
    assert any(fk["referred_table"] == "tenants" for fk in inspector.get_foreign_keys("merchants", "core"))
    indexes = {i["name"] for i in inspector.get_indexes("applications", "core")}
    assert "ix_core_applications_tenant_id" in indexes


def test_postgres_types_are_exact(db_engine) -> None:
    inspector = inspect(db_engine)
    amount = next(c for c in inspector.get_columns("applications", "core") if c["name"] == "requested_amount")["type"]
    available = next(c for c in inspector.get_columns("bank_transactions", "source") if c["name"] == "available_at")["type"]
    jsonb = next(c for c in inspector.get_columns("gt_facts", "truth") if c["name"] == "value_json")["type"]
    assert isinstance(amount, NUMERIC) and amount.precision == 18 and amount.scale == 2
    assert isinstance(available, DateTime) and available.timezone
    assert isinstance(jsonb, JSONB)
