import json
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import create_engine, text

from msme_copilot.config import get_settings
from msme_copilot.synthetic.models import SourceWorld, SyntheticWorld


def write_artifacts(world: SyntheticWorld, output_path: Path) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    with (output_path / "merchants.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for merchant in world.merchants:
            handle.write(json.dumps(asdict(merchant), default=str, sort_keys=True, separators=(",", ":")) + "\n")
    with (output_path / "monthly_state.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for state in world.monthly_states:
            handle.write(json.dumps(asdict(state), default=str, sort_keys=True, separators=(",", ":")) + "\n")


def persist_merchants(world: SyntheticWorld) -> None:
    """Persist only canonical merchant records; hidden state remains synthetic artifacts."""
    settings = get_settings()
    engine = create_engine(settings.test_database_url or settings.database_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO authz.tenants (tenant_id, tenant_name, status, created_at) VALUES (:id, :name, 'ACTIVE', now()) ON CONFLICT (tenant_id) DO NOTHING"), {"id": world.merchants[0].tenant_id, "name": "Synthetic Tenant 001"})
        for merchant in world.merchants:
            connection.execute(text("""
                INSERT INTO core.merchants
                (merchant_id, tenant_id, legal_name, trade_name, constitution, sector_code, sector_name,
                 udyam_category, incorporation_date, city, state, digital_share, status, created_at)
                VALUES (:merchant_id, :tenant_id, :legal_name, :trade_name, :constitution, :sector_code,
                        :sector_name, :udyam_category, :incorporation_date, :city, :state, :digital_share,
                        'ACTIVE', now())
                ON CONFLICT (merchant_id) DO UPDATE SET tenant_id = EXCLUDED.tenant_id,
                    legal_name = EXCLUDED.legal_name, digital_share = EXCLUDED.digital_share
            """), asdict(merchant) | {"digital_share": merchant.digital_share})
    engine.dispose()


def write_source_artifacts(source: SourceWorld, output_path: Path) -> None:
    """Write observable rows to ignored JSONL artifacts for inspection."""
    output_path.mkdir(parents=True, exist_ok=True)
    for table, rows in source.table_rows().items():
        with (output_path / f"{table}.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row.values, default=str, sort_keys=True, separators=(",", ":")) + "\n")


def persist_source_world(world: SyntheticWorld, source: SourceWorld) -> None:
    """Persist only approved observable source tables; latent state never enters PostgreSQL."""
    persist_merchants(world)
    settings = get_settings()
    engine = create_engine(settings.test_database_url or settings.database_url)
    table_ids = {
        "merchant_bank_accounts": "bank_account_id", "bank_transactions": "transaction_id", "banking_metrics": "metric_id",
        "merchant_gstins": "gstin_id", "gst_returns": "gst_return_id", "digital_payment_metrics": "metric_id",
        "digital_sales_daily": "sale_id", "financial_statements": "statement_id", "bureau_snapshots": "snapshot_id",
    }
    with engine.begin() as connection:
        for table, rows in source.table_rows().items():
            if not rows:
                continue
            columns = tuple(rows[0].values)
            quoted = ", ".join(columns)
            bind = ", ".join(f":{column}" for column in columns)
            updates = ", ".join(f"{column}=EXCLUDED.{column}" for column in columns if column != table_ids[table])
            statement = text(f"INSERT INTO source.{table} ({quoted}) VALUES ({bind}) ON CONFLICT ({table_ids[table]}) DO UPDATE SET {updates}")
            for row in rows:
                connection.execute(statement, row.values)
    engine.dispose()
