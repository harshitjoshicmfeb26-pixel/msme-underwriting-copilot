"""Slice 02B observable source-system generation.

The generator deliberately keeps source rows as small dictionaries.  This mirrors
the approved physical schema and makes it straightforward to inspect, validate,
or persist rows without introducing a second ORM model for synthetic data.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import cast
from msme_copilot.synthetic.models import MonthlyState, SourceRecord, SourceWorld, SyntheticWorld


CENT = Decimal("0.01")


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(max(0.0, value))).quantize(CENT, rounding=ROUND_HALF_UP)


def _partition(total: Decimal, count: int, rng: random.Random) -> list[Decimal]:
    """Split a positive total into positive money amounts that sum exactly."""
    if count <= 1:
        return [total]
    weights = [0.35 + rng.random() for _ in range(count)]
    amounts = [_money(float(total) * weight / sum(weights)) for weight in weights[:-1]]
    remainder = total - sum(amounts, Decimal("0.00"))
    if remainder <= 0:
        return _partition(total, count - 1, rng)
    return amounts + [remainder]


def _row(**values: object) -> SourceRecord:
    return SourceRecord(values)


def _available(day: date, low: int, high: int, rng: random.Random) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC) + timedelta(days=rng.randint(low, high))


def _month_end(month: date) -> date:
    next_month = date(month.year + (month.month == 12), 1 if month.month == 12 else month.month + 1, 1)
    return next_month - timedelta(days=1)


def _stable_id(prefix: str, *parts: object) -> str:
    payload = "|".join(map(str, parts)).encode()
    return prefix + hashlib.sha1(payload).hexdigest()[: max(8, 32 - len(prefix))]


def _rng(seed: int, merchant_id: str, salt: int) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{merchant_id}:{salt}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def _states(world: SyntheticWorld) -> dict[tuple[str, date], MonthlyState]:
    return {(s.merchant_id, s.month): s for s in world.monthly_states}


def generate_source_world(world: SyntheticWorld) -> SourceWorld:
    """Generate all five imperfect, independently observed source systems."""
    state_by_key = _states(world)
    months = sorted({s.month for s in world.monthly_states})
    account_rows: list[SourceRecord] = []
    transaction_rows: list[SourceRecord] = []
    banking_rows: list[SourceRecord] = []
    gstin_rows: list[SourceRecord] = []
    gst_rows: list[SourceRecord] = []
    digital_rows: list[SourceRecord] = []
    daily_rows: list[SourceRecord] = []
    financial_rows: list[SourceRecord] = []
    bureau_rows: list[SourceRecord] = []
    account_ids: dict[str, list[str]] = {}
    gstin_ids: dict[str, list[str]] = {}

    for merchant in world.merchants:
        rng = _rng(world.seed, merchant.merchant_id, 11)
        count = max(1, min(4, merchant.intended_bank_account_count))
        ids: list[str] = []
        for index in range(count):
            aid = _stable_id("BA", merchant.merchant_id, index)
            ids.append(aid)
            account_rows.append(_row(bank_account_id=aid, tenant_id=merchant.tenant_id, merchant_id=merchant.merchant_id,
                account_hash=hashlib.sha256(f"synthetic:{aid}".encode()).hexdigest(),
                account_type="CURRENT" if index == 0 else rng.choice(("CURRENT", "SAVINGS", "OD_CC")),
                status="ACTIVE", opened_on=merchant.incorporation_date,
                available_at=_available(merchant.incorporation_date, 0, 7, rng)))
        account_ids[merchant.merchant_id] = ids

        gst_count = max(1, merchant.intended_gstin_count)
        gids: list[str] = []
        for index in range(gst_count):
            gid = _stable_id("GI", merchant.merchant_id, index)
            gids.append(gid)
            gstin_rows.append(_row(gstin_id=gid, tenant_id=merchant.tenant_id, merchant_id=merchant.merchant_id,
                gstin=f"SYN{merchant.merchant_id}{index:02d}", legal_name=merchant.legal_name,
                registration_date=merchant.incorporation_date, state_code="00", status="ACTIVE",
                available_at=_available(merchant.incorporation_date, 1, 8, rng)))
        gstin_ids[merchant.merchant_id] = gids

        # Source-specific capture is noisy and probabilistic; no row copies canonical revenue.
        latent = merchant.latent.values
        bank_capture = min(.96, max(.12, .84 - .48 * latent["cash_dependence"] + .13 * latent["digital_adoption"] + rng.gauss(0, .05)))
        digital_share = min(.92, max(.04, float(merchant.digital_share) * (.72 + .35 * latent["digital_adoption"]) + rng.gauss(0, .025)))
        gst_quality = latent["gst_compliance_quality"]
        for offset, month in enumerate(months):
            state = state_by_key[(merchant.merchant_id, month)]
            revenue = float(state.canonical_revenue)
            month_end = _month_end(month)
            bank_receipt = revenue * bank_capture * (1 + rng.gauss(0, .09))
            if offset and rng.random() < .18 + .15 * latent["working_capital_intensity"]:
                bank_receipt *= .76 + rng.random() * .16
            bank_receipt = max(0.0, bank_receipt)
            transfer_heavy = "own_account_transfer_heavy" in merchant.scenario_tags
            internal_factor = (0.06 + rng.random() * .06) if not transfer_heavy else (0.06 + rng.random() * .28)
            # Internal transfers are account-movement noise, not a second copy of receipts.
            internal_base = 180_000 * (0.4 + 1.6 * latent["business_scale"])
            internal = internal_base * internal_factor * (0.25 + rng.random() * 1.75)
            total_credit = bank_receipt + internal + revenue * (.02 + .06 * rng.random())
            debit = revenue * (.57 + .28 * latent["working_capital_intensity"] + .10 * latent["existing_leverage"]) * (1 + rng.gauss(0, .07))
            opening = 0.18 * revenue * (.6 + latent["liquidity_buffer"])
            closing = max(0.0, opening + total_credit - max(0.0, debit))
            metric_id = _stable_id("BM", merchant.merchant_id, month)
            banking_rows.append(_row(metric_id=metric_id, tenant_id=merchant.tenant_id, merchant_id=merchant.merchant_id,
                period_start=month, period_end=month_end, eligible_business_credits=_money(bank_receipt),
                total_credits=_money(total_credit), total_debits=_money(debit), average_balance=_money((opening + closing) / 2),
                cash_deposit_ratio=round(min(1.0, max(0.0, latent["cash_dependence"] * (.65 + rng.random() * .3))), 6),
                bounce_count=1 if state.liquidity_condition < .35 and rng.random() < .12 else 0,
                inflow_growth=round(rng.gauss(.03 + latent["revenue_growth"] * .12, .06), 6),
                inflow_volatility=round(min(1.0, max(0.0, latent["revenue_volatility"] + rng.gauss(0, .05))), 6),
                available_at=_available(month_end, 2, 9, rng), calculation_version="02B-v1"))

            # Detailed bank transactions are restricted to the deep cohort.
            if merchant.deep_cohort or transfer_heavy:
                activity = .30 + .70 * latent["business_scale"]
                sector_factor = 1.15 if merchant.sector_code in ("RETAIL", "HOSPITALITY") else .9
                transaction_count = max(20, min(100, int(round((20 + 80 * activity * sector_factor) * (0.85 + rng.random() * .3)))))
                credit_count = max(3, int(transaction_count * (.48 + rng.random() * .12)))
                debit_count = max(3, transaction_count - credit_count)
                credit_targets = [(_money(bank_receipt), "BUSINESS_RECEIPT"), (_money(internal), "OWN_ACCOUNT_TRANSFER")]
                other_credit = max(Decimal("0.00"), _money(total_credit) - credit_targets[0][0] - credit_targets[1][0])
                credit_targets.append((other_credit, rng.choice(("OTHER_CREDIT", "INTEREST_INCOME", "CAPITAL_INFUSION"))))
                credit_targets = [(amount, category) for amount, category in credit_targets if amount > 0]
                credit_rows: list[tuple[Decimal, str]] = []
                for amount, category in credit_targets:
                    pieces = _partition(amount, max(1, round(credit_count * amount / max(_money(total_credit), CENT))), rng)
                    credit_rows.extend((piece, category) for piece in pieces)
                debit_category = "EMI_DEBT_SERVICE" if latent["existing_leverage"] > .65 else "SUPPLIER_PAYMENT"
                debit_categories = [debit_category, "PAYROLL", "UTILITY", "OTHER_BUSINESS_DEBIT"]
                debit_rows = [(piece, debit_categories[index % len(debit_categories)]) for index, piece in enumerate(_partition(_money(debit), debit_count, rng))]
                for index, (amount, category) in enumerate(credit_rows + debit_rows):
                    is_credit = category in {"BUSINESS_RECEIPT", "OWN_ACCOUNT_TRANSFER", "OTHER_CREDIT", "INTEREST_INCOME", "CAPITAL_INFUSION"}
                    transaction_rows.append(_row(transaction_id=_stable_id("BT", merchant.merchant_id, month, index, category), tenant_id=merchant.tenant_id,
                        merchant_id=merchant.merchant_id, bank_account_id=ids[index % len(ids)],
                        transaction_time=datetime(month.year, month.month, min(28, 2 + (index * 3) % 25), tzinfo=UTC),
                        value_date=month + timedelta(days=min(27, 2 + (index * 3) % 25)), amount=amount,
                        direction="CREDIT" if is_credit else "DEBIT", credit_category=category if is_credit else None,
                        debit_category=None if is_credit else category, description=f"synthetic {category.lower()}",
                        available_at=_available(month_end, 1, 5, rng)))

            reportable = revenue * (.72 + .22 * gst_quality) * (1 + rng.gauss(0, .07))
            if rng.random() > .04 + .10 * (1 - gst_quality):
                for gi, gid in enumerate(gids):
                    allocated = reportable / len(gids) * (1 + rng.gauss(0, .035))
                    filing = month_end + timedelta(days=rng.randint(12, 35) + (8 if gst_quality < .35 else 0))
                    version = "ORIGINAL"
                    gst_rows.append(_row(gst_return_id=_stable_id("GR", merchant.merchant_id, month, gi), tenant_id=merchant.tenant_id,
                        merchant_id=merchant.merchant_id, gstin_id=gid, period_start=month, period_end=month_end,
                        return_type="GSTR3B", due_date=month_end + timedelta(days=20), filing_date=filing,
                        available_at=_available(filing, 0, 2, rng), outward_supplies=_money(allocated), taxable_supplies=_money(allocated * .88),
                        b2b_supplies=_money(allocated * .58), b2c_supplies=_money(allocated * .42), credit_notes=_money(allocated * .015),
                        tax_liability=_money(allocated * .12), amended_return_id=None, source_version=version))
                    if rng.random() < .03 + .06 * (1 - gst_quality):
                        amended_id = _stable_id("GR", merchant.merchant_id, month, gi, "amend")
                        gst_rows.append(_row(gst_return_id=amended_id, tenant_id=merchant.tenant_id, merchant_id=merchant.merchant_id, gstin_id=gid,
                            period_start=month, period_end=month_end, return_type="GSTR3B", due_date=month_end + timedelta(days=20),
                            filing_date=filing + timedelta(days=12), available_at=_available(filing + timedelta(days=12), 0, 2, rng),
                            outward_supplies=_money(allocated * (1 + rng.gauss(0, .04))), taxable_supplies=_money(allocated * .88),
                            b2b_supplies=_money(allocated * .58), b2c_supplies=_money(allocated * .42), credit_notes=_money(allocated * .015),
                            tax_liability=_money(allocated * .12), amended_return_id=_stable_id("GR", merchant.merchant_id, month, gi), source_version="AMENDED"))

            digital_total = max(0.0, revenue * digital_share * (1 + rng.gauss(0, .08)))
            channels = ("UPI", "CARD_POS", "PAYMENT_GATEWAY", "OTHER_DIGITAL")
            weights = [(.45, .25, .2, .1), (.28, .4, .2, .12), (.2, .12, .5, .18)][0 if merchant.sector_code in ("RETAIL", "HOSPITALITY") else 2 if merchant.sector_code == "SERVICES" else 1]
            channel = rng.choices(channels, weights=weights, k=1)[0]
            digital_rows.append(_row(metric_id=_stable_id("DP", merchant.merchant_id, month), tenant_id=merchant.tenant_id,
                merchant_id=merchant.merchant_id, period_start=month, period_end=month_end, channel=channel,
                transaction_count=max(0, int(digital_total / max(1, 40 + rng.random() * 100))), gross_amount=_money(digital_total),
                net_amount=_money(digital_total * (.985 - rng.random() * .018)), available_at=_available(month_end, 2, 8, rng)))
            if merchant.deep_cohort:
                days = (month_end - month).days + 1
                daily_weights = [max(.1, (1 + .18 * math.sin(2 * math.pi * (d % 7) / 7))) for d in range(days)]
                scale = digital_total / sum(daily_weights)
                for d, weight in enumerate(daily_weights):
                    sale_day = month + timedelta(days=d)
                    daily_rows.append(_row(sale_id=_stable_id("DS", merchant.merchant_id, sale_day), tenant_id=merchant.tenant_id,
                        merchant_id=merchant.merchant_id, sale_date=sale_day, channel=rng.choice(channels), amount=_money(scale * weight),
                        available_at=_available(sale_day, 0, 2, rng)))

        # Annual statements: two valid periods when the incorporation date permits it.
        for year_end in (date(months[-1].year - 1, 3, 31), date(months[-1].year, 3, 31)):
            period_start = max(date(year_end.year - 1, 4, 1), merchant.incorporation_date)
            covered = [state_by_key[(merchant.merchant_id, m)] for m in months if period_start <= m <= year_end and m >= merchant.incorporation_date.replace(day=1)]
            if not covered or merchant.incorporation_date > year_end:
                continue
            total_revenue = sum(float(s.canonical_revenue) for s in covered) * (1 + rng.gauss(0, .035))
            cogs = total_revenue * (0.55 + .18 * (1 - latent["gross_margin_quality"]))
            operating = total_revenue - cogs - total_revenue * (.12 + .08 * rng.random())
            interest = total_revenue * (.015 + .05 * latent["existing_leverage"])
            net = operating - interest
            assets = total_revenue * (.55 + latent["working_capital_intensity"] * .45 + latent["liquidity_buffer"] * .2)
            liabilities = total_revenue * (.12 + .55 * latent["existing_leverage"])
            financial_rows.append(_row(statement_id=_stable_id("FS", merchant.merchant_id, year_end), tenant_id=merchant.tenant_id,
                merchant_id=merchant.merchant_id, period_start=period_start, period_end=year_end, statement_type="ANNUAL",
                revenue=_money(total_revenue), gross_profit=_money(total_revenue - cogs), operating_profit=_money(operating), net_profit=_money(net),
                total_assets=_money(assets), total_liabilities=_money(liabilities), available_at=_available(year_end, 75, 180, rng), source_version="ORIGINAL"))

        for index in range(6):
            snap = months[min(len(months) - 1, index * max(1, len(months) // 6))]
            as_of = _month_end(snap)
            history_age = max(0, (as_of - merchant.incorporation_date).days // 365)
            thin = rng.random() < .035
            no_hit = rng.random() < .012
            exposure = 0.0 if no_hit else max(0.0, 6000 * latent["business_scale"] * (.35 + latent["existing_leverage"] * 1.8) * (1 + rng.gauss(0, .15)))
            obligations = exposure * (.025 + .025 * rng.random())
            score = None if thin or no_hit else int(max(300, min(900, 500 + 180 * latent["repayment_discipline"] + 55 * latent["business_stability"] - 45 * latent["existing_leverage"] + min(80, history_age * 12) + rng.gauss(0, 42))))
            overdue = 0 if no_hit or rng.random() > (.04 + .25 * (1 - latent["repayment_discipline"])) else _money(obligations * (.5 + rng.random() * 2))
            bureau_rows.append(_row(snapshot_id=_stable_id("BU", merchant.merchant_id, index), tenant_id=merchant.tenant_id, merchant_id=merchant.merchant_id,
                snapshot_date=as_of, synthetic_rank=score, active_accounts=0 if no_hit else max(1, int(round(1 + 3 * latent["existing_leverage"]))),
                overdue_accounts=1 if overdue else 0, total_outstanding=_money(exposure), available_at=_available(as_of, 7, 15, rng), source_version="THIN_FILE" if thin else "NO_HIT" if no_hit else "SYNTHETIC_02B"))

    return SourceWorld(tuple(), tuple(account_rows), tuple(transaction_rows), tuple(banking_rows), tuple(gstin_rows), tuple(gst_rows),
                       tuple(digital_rows), tuple(daily_rows), tuple(financial_rows), tuple(bureau_rows), world.seed)


def source_checksum(source: SourceWorld) -> str:
    import json
    payload = {name: [record.values for record in rows] for name, rows in sorted(source.table_rows().items())}
    return hashlib.sha256(json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rows_usable_at(rows: Iterable[SourceRecord], as_of: datetime) -> tuple[SourceRecord, ...]:
    return tuple(row for row in rows if cast(datetime, row.values["available_at"]) <= as_of)


def source_row_counts(source: SourceWorld) -> dict[str, int]:
    return {name: len(rows) for name, rows in source.table_rows().items()}


def source_missingness(source: SourceWorld) -> dict[str, float]:
    result: dict[str, float] = {}
    required = {
        "bank_transactions": ("transaction_id", "merchant_id", "amount", "direction", "available_at"),
        "gst_returns": ("gst_return_id", "merchant_id", "period_start", "period_end", "outward_supplies", "available_at"),
    }
    for name, rows in source.table_rows().items():
        if not rows:
            result[name] = 0.0
            continue
        fields = required.get(name, tuple(rows[0].values))
        result[name] = sum(any(row.values.get(field) is None for field in fields) for row in rows) / len(rows)
    return result
