import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import Connection, create_engine
from sqlalchemy.engine import Engine, URL, make_url


@pytest.fixture(scope="session")
def postgres_url() -> URL:
    load_dotenv()
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("set TEST_DATABASE_URL to a PostgreSQL connection URL")
    return make_url(url)


@pytest.fixture(scope="session")
def db_engine(postgres_url: URL) -> Iterator[Engine]:
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(postgres_url)
    yield engine
    command.downgrade(config, "base")
    engine.dispose()


@pytest.fixture
def db_connection(db_engine: Engine) -> Iterator[Connection]:
    with db_engine.begin() as connection:
        connection.exec_driver_sql(
            """
            INSERT INTO authz.tenants VALUES ('t1', 'Tenant One', 'ACTIVE', now()) ON CONFLICT DO NOTHING;
            INSERT INTO authz.branches VALUES ('b1', 't1', 'Branch One', 'Pune', 'MH', 'ACTIVE') ON CONFLICT DO NOTHING;
            INSERT INTO authz.analysts VALUES ('a1', 't1', 'Analyst One', 'ANALYST', 'BRANCH', 'ACTIVE') ON CONFLICT DO NOTHING;
            INSERT INTO core.merchants (merchant_id, tenant_id, branch_id, legal_name, status, created_at)
              VALUES ('m1', 't1', 'b1', 'Merchant One', 'ACTIVE', now()) ON CONFLICT DO NOTHING;
            INSERT INTO core.applications (application_id, tenant_id, merchant_id, application_date, application_status,
              requested_amount, requested_tenor_months, as_of_date, created_at)
              VALUES ('app1', 't1', 'm1', '2026-01-01', 'SUBMITTED', 10000, 12, '2026-01-01', now()) ON CONFLICT DO NOTHING;
            INSERT INTO source.merchant_bank_accounts (bank_account_id, tenant_id, merchant_id, account_hash, status, available_at)
              VALUES ('ba1', 't1', 'm1', 'hash1', 'ACTIVE', now()) ON CONFLICT DO NOTHING;
            INSERT INTO lending.historical_loans (loan_id, tenant_id, merchant_id, application_id, sanctioned_amount,
              disbursed_amount, disbursement_date, maturity_date, available_at)
              VALUES ('l1', 't1', 'm1', 'app1', 10000, 9000, '2026-02-01', '2027-02-01', now()) ON CONFLICT DO NOTHING;
            """
        )
        yield connection
