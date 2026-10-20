from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


def rejects(connection, statement: str, params: dict) -> None:
    savepoint = connection.begin_nested()
    try:
        connection.execute(text(statement), params)
    except IntegrityError:
        savepoint.rollback()
    else:
        savepoint.commit()
        pytest.fail("expected PostgreSQL to reject the statement")


def test_core_constraints(db_connection) -> None:
    rejects(db_connection, "INSERT INTO core.merchants (merchant_id, tenant_id, legal_name, digital_share, status, created_at) VALUES (:id, 't1', 'x', -0.1, 'ACTIVE', now())", {"id": "mneg"})
    rejects(db_connection, "INSERT INTO core.merchants (merchant_id, tenant_id, legal_name, digital_share, status, created_at) VALUES (:id, 't1', 'x', 1.1, 'ACTIVE', now())", {"id": "mhigh"})
    rejects(db_connection, "INSERT INTO core.seasonality_profiles VALUES ('sp', 'S', 13, 1, 1)", {})
    rejects(db_connection, "INSERT INTO core.applications (application_id, tenant_id, merchant_id, application_date, application_status, requested_amount, requested_tenor_months, as_of_date, created_at) VALUES (:id, 't1', 'm1', '2026-01-01', 'X', 0, 12, '2026-01-01', now())", {"id": "app0"})
    rejects(db_connection, "INSERT INTO core.applications (application_id, tenant_id, merchant_id, application_date, application_status, requested_amount, requested_tenor_months, as_of_date, created_at) VALUES (:id, 't1', 'm1', '2026-01-01', 'X', 1, 0, '2026-01-01', now())", {"id": "appt0"})
    rejects(db_connection, "INSERT INTO core.applications (application_id, tenant_id, merchant_id, application_date, application_status, requested_amount, requested_tenor_months, as_of_date, created_at) VALUES (:id, 't1', 'm1', '2026-01-02', 'X', 1, 1, '2026-01-01', now())", {"id": "appdate"})


def test_authorization_and_bank_constraints(db_connection) -> None:
    rejects(db_connection, "INSERT INTO authz.analyst_scopes VALUES ('a1', 'b1', '2026-02-01', '2026-01-01')", {})
    rejects(db_connection, "INSERT INTO source.bank_transactions (transaction_id, tenant_id, merchant_id, bank_account_id, transaction_time, amount, direction, debit_category, available_at) VALUES ('tx0', 't1', 'm1', 'ba1', now(), 0, 'DEBIT', 'OTHER', now())", {})
    rejects(db_connection, "INSERT INTO source.bank_transactions (transaction_id, tenant_id, merchant_id, bank_account_id, transaction_time, amount, direction, available_at) VALUES ('tx1', 't1', 'm1', 'ba1', now(), 1, 'CREDIT', now())", {})
    rejects(db_connection, "INSERT INTO source.bank_transactions (transaction_id, tenant_id, merchant_id, bank_account_id, transaction_time, amount, direction, credit_category, available_at) VALUES ('tx2', 't1', 'm1', 'ba1', now(), 1, 'DEBIT', 'OTHER', now())", {})


def test_historical_loan_and_repayment_constraints(db_connection) -> None:
    rejects(db_connection, "INSERT INTO lending.historical_loans (loan_id, tenant_id, merchant_id, sanctioned_amount, disbursed_amount, available_at) VALUES ('l0', 't1', 'm1', 0, 1, now())", {})
    rejects(db_connection, "INSERT INTO lending.historical_loans (loan_id, tenant_id, merchant_id, sanctioned_amount, disbursed_amount, available_at) VALUES ('l2', 't1', 'm1', 10, 11, now())", {})
    rejects(db_connection, "INSERT INTO lending.historical_loans (loan_id, tenant_id, merchant_id, sanctioned_amount, disbursed_amount, disbursement_date, maturity_date, available_at) VALUES ('l3', 't1', 'm1', 10, 9, '2026-02-01', '2026-02-01', now())", {})
    rejects(db_connection, "INSERT INTO lending.repayment_schedule VALUES ('l1', 1, '2026-03-01', 10, 2, 99)", {})
    rejects(db_connection, "INSERT INTO lending.repayment_transactions VALUES ('rt1', 't1', 'l1', 1, :date, 15, 10, 2, now())", {"date": date(2026, 3, 1)})
