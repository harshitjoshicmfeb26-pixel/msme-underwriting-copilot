"""Empirical checks for the observable 02B layer."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from math import sqrt
from statistics import mean, quantiles
from typing import cast
from msme_copilot.synthetic.models import SourceRecord, SourceWorld, SyntheticWorld
from msme_copilot.synthetic.sources import source_checksum, source_missingness, source_row_counts


def _corr(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3:
        return None
    lm, rm = mean(left), mean(right)
    ldev, rdev = [x - lm for x in left], [x - rm for x in right]
    denominator = sqrt(sum(x * x for x in ldev) * sum(x * x for x in rdev))
    return None if denominator == 0 else sum(x * y for x, y in zip(ldev, rdev, strict=True)) / denominator


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    q = quantiles(values, n=100, method="inclusive") if len(values) > 1 else [values[0]] * 99
    return {"p10": q[9] if len(q) > 9 else values[0], "p50": q[49] if len(q) > 49 else values[0], "p90": q[89] if len(q) > 89 else values[0]}


def _by_merchant(rows: Iterable[SourceRecord], field: str) -> dict[str, float]:
    values: dict[str, float] = defaultdict(float)
    for row in rows:
        value = row.values.get(field)
        if value is not None:
            values[str(row.values["merchant_id"])] += float(cast(float | int | str, value))
    return dict(values)


def validate_source_world(world: SyntheticWorld, source: SourceWorld) -> dict[str, object]:
    canonical: dict[str, float] = defaultdict(float)
    for state in world.monthly_states:
        canonical[state.merchant_id] += float(state.canonical_revenue)
    gst = _by_merchant(source.gst_returns, "outward_supplies")
    bank = _by_merchant(source.banking_metrics, "eligible_business_credits")
    total_bank = _by_merchant(source.banking_metrics, "total_credits")
    digital = _by_merchant(source.digital_metrics, "gross_amount")
    financial = _by_merchant(source.financial_statements, "revenue")
    keys = sorted(set(canonical) & set(gst) & set(bank) & set(digital))
    correlations = {
        "canonical_vs_gst": _corr([canonical[k] for k in keys], [gst[k] for k in keys]),
        "canonical_vs_eligible_bank": _corr([canonical[k] for k in keys], [bank[k] for k in keys]),
        "canonical_vs_digital": _corr([canonical[k] for k in keys], [digital[k] for k in keys]),
        "gst_vs_eligible_bank": _corr([gst[k] for k in keys], [bank[k] for k in keys]),
        "gst_vs_total_bank": _corr([gst[k] for k in keys], [total_bank.get(k, 0.0) for k in keys]),
        "financial_vs_gst": _corr([financial[k] for k in set(financial) & set(gst)], [gst[k] for k in set(financial) & set(gst)]),
    }
    lags: dict[str, list[float]] = defaultdict(list)
    for table, rows in source.table_rows().items():
        for row in rows:
            available = row.values.get("available_at")
            described = row.values.get("period_end") or row.values.get("sale_date") or row.values.get("snapshot_date")
            if available is not None and described is not None:
                lags[table].append((available.date() - described).days if hasattr(available, "date") else 0)
    lag_report = {table: _percentiles(values) for table, values in lags.items()}
    actual_accounts: dict[str, int] = defaultdict(int)
    for row in source.bank_accounts:
        actual_accounts[str(row.values["merchant_id"])] += 1
    actual_gstins: dict[str, int] = defaultdict(int)
    for row in source.gstins:
        actual_gstins[str(row.values["merchant_id"])] += 1
    intended_accounts = {m.merchant_id: m.intended_bank_account_count for m in world.merchants}
    intended_gstins = {m.merchant_id: m.intended_gstin_count for m in world.merchants}
    deep_ids = {m.merchant_id for m in world.merchants if m.deep_cohort}
    tx_business = _by_merchant((row for row in source.bank_transactions if row.values.get("credit_category") == "BUSINESS_RECEIPT"), "amount")
    tx_total = _by_merchant((row for row in source.bank_transactions if row.values.get("direction") == "CREDIT"), "amount")
    daily = _by_merchant(source.digital_daily, "amount")
    deep_monthly_digital = _by_merchant((row for row in source.digital_metrics if row.values["merchant_id"] in deep_ids), "gross_amount")
    return {
        "checksum": source_checksum(source),
        "row_counts": source_row_counts(source),
        "missingness": source_missingness(source),
        "correlations": correlations,
        "suspicious_correlations": {name: value for name, value in correlations.items() if value is not None and abs(value) > .98},
        "availability_lags_days": lag_report,
        "deep_bank_transaction_count": sum(1 for row in source.bank_transactions if row.values["merchant_id"] in {m.merchant_id for m in world.merchants if m.deep_cohort}),
        "deep_digital_daily_count": sum(1 for row in source.digital_daily if row.values["merchant_id"] in {m.merchant_id for m in world.merchants if m.deep_cohort}),
        "scenario_propagation": {
            "multiple_bank_accounts_actual": sum(actual_accounts[k] > 1 for k, v in intended_accounts.items() if v > 1),
            "multiple_bank_accounts_expected": sum(v > 1 for v in intended_accounts.values()),
            "multiple_gstins_actual": sum(actual_gstins[k] > 1 for k, v in intended_gstins.items() if v > 1),
            "multiple_gstins_expected": sum(v > 1 for v in intended_gstins.values()),
            "deep_business_receipt_reconciliation_max_abs": max((abs(tx_business.get(k, 0) - _by_merchant(source.banking_metrics, "eligible_business_credits").get(k, 0)) for k in deep_ids), default=0.0),
            "deep_digital_daily_vs_monthly_max_abs": max((abs(daily.get(k, 0) - deep_monthly_digital.get(k, 0)) for k in deep_ids), default=0.0),
            "deep_total_credit_exceeds_eligible": sum(tx_total.get(k, 0) > tx_business.get(k, 0) for k in deep_ids),
        },
    }


audit_source_world = validate_source_world
