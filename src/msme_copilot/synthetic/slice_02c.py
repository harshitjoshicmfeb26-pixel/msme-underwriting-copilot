"""Phase 1 Slice 02C: historically coherent lending and evaluation evidence.

The public generator separates application-time snapshots from post-disbursement
state.  The historical lender receives only ``ApplicationSnapshot`` objects;
future states are used only after a loan has been booked.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from msme_copilot.synthetic.models import SourceRecord, SourceWorld, SyntheticWorld


@dataclass(frozen=True, slots=True)
class ApplicationSnapshot:
    application_id: str
    merchant_id: str
    assessment_time: datetime
    banking: tuple[SourceRecord, ...]
    gst: tuple[SourceRecord, ...]
    digital: tuple[SourceRecord, ...]
    financials: tuple[SourceRecord, ...]
    bureau: tuple[SourceRecord, ...]
    prior_loans: tuple[SourceRecord, ...]
    policy_version: str


@dataclass(frozen=True, slots=True)
class HistoricalDecisionContext:
    snapshot: ApplicationSnapshot
    product_type: str
    requested_amount: Decimal
    requested_tenor_months: int


@dataclass(frozen=True, slots=True)
class DecisionResult:
    application_id: str
    status: str
    decision_date: date
    reason_code: str


@dataclass(frozen=True, slots=True)
class LendingWorld:
    applications: tuple[SourceRecord, ...]
    loan_requests: tuple[SourceRecord, ...]
    decisions: tuple[DecisionResult, ...]
    loans: tuple[SourceRecord, ...]
    schedules: tuple[SourceRecord, ...]
    repayments: tuple[SourceRecord, ...]
    outcomes: tuple[SourceRecord, ...]
    policies: tuple[SourceRecord, ...]
    policy_clauses: tuple[SourceRecord, ...]
    documents: tuple[SourceRecord, ...]
    document_entities: tuple[SourceRecord, ...]
    authority_rules: tuple[SourceRecord, ...]
    gt_facts: tuple[SourceRecord, ...]
    gt_spans: tuple[SourceRecord, ...]
    golden_questions: tuple[SourceRecord, ...]
    seed: int

    def table_rows(self) -> dict[str, tuple[SourceRecord, ...]]:
        return {
            "applications": self.applications,
            "loan_requests": self.loan_requests,
            "historical_loans": self.loans,
            "repayment_schedule": self.schedules,
            "repayment_transactions": self.repayments,
            "loan_outcomes": self.outcomes,
            "policies": self.policies,
            "policy_clauses": self.policy_clauses,
            "documents": self.documents,
            "document_entities": self.document_entities,
            "fact_authority_rules": self.authority_rules,
            "gt_facts": self.gt_facts,
            "gt_spans": self.gt_spans,
            "golden_questions": self.golden_questions,
        }


def _row(**values: object) -> SourceRecord:
    return SourceRecord(values)


def _float(value: object) -> float:
    return float(cast(float | int | str | Decimal, value))


def _date(value: object) -> date:
    return cast(date, value)


def _datetime(value: object) -> datetime:
    return cast(datetime, value)


def _id(prefix: str, *parts: object) -> str:
    return (
        prefix
        + hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[: max(8, 32 - len(prefix))]
    )


def _rng(seed: int, *parts: object) -> random.Random:
    return random.Random(
        int.from_bytes(hashlib.sha256(f"{seed}|{parts}".encode()).digest()[:8], "big")
    )


def _month_shift(month: date, offset: int) -> date:
    absolute = month.year * 12 + month.month - 1 + offset
    return date(absolute // 12, absolute % 12 + 1, 1)


def policy_version_for_date(value: date) -> str:
    """Return the only underwriting policy effective at ``value``."""
    return "2026-v1" if value >= date(2026, 1, 1) else "2025-v1"


def _visible(rows: Iterable[SourceRecord], assessment: datetime) -> tuple[SourceRecord, ...]:
    return tuple(
        row
        for row in rows
        if isinstance(row.values.get("available_at"), datetime)
        and _datetime(row.values["available_at"]) <= assessment
    )


def _visible_prior_loan(row: SourceRecord, assessment: datetime) -> SourceRecord | None:
    """Expose a prior loan and only its repayment events known by assessment."""
    values = row.values
    disbursement = values.get("disbursement_date")
    if not isinstance(disbursement, date) or disbursement >= assessment.date():
        return None
    filtered = dict(values)
    for key in ("repayment_history", "delinquency_events"):
        events = values.get(key)
        if isinstance(events, list):
            filtered[key] = [
                event for event in events
                if isinstance(event, dict)
                and (
                    (isinstance(event.get("available_at"), datetime) and event["available_at"] <= assessment)
                    or (isinstance(event.get("transaction_date"), date) and event["transaction_date"] < assessment.date())
                    or (isinstance(event.get("event_date"), date) and event["event_date"] < assessment.date())
                )
            ]
    return SourceRecord(filtered)


def application_snapshot(
    application_id: str,
    merchant_id: str,
    assessment_time: datetime,
    source: SourceWorld,
    prior_loans: Iterable[SourceRecord] = (),
    policy_version: str | None = None,
) -> ApplicationSnapshot:
    """Build an immutable point-in-time view; future source rows cannot enter it."""
    effective_policy = policy_version_for_date(assessment_time.date())
    if policy_version is not None and policy_version != effective_policy:
        raise ValueError("policy version is not effective at assessment time")
    return ApplicationSnapshot(
        application_id,
        merchant_id,
        assessment_time,
        _visible(
            (r for r in source.banking_metrics if r.values["merchant_id"] == merchant_id),
            assessment_time,
        ),
        _visible(
            (r for r in source.gst_returns if r.values["merchant_id"] == merchant_id),
            assessment_time,
        ),
        _visible(
            (r for r in source.digital_metrics if r.values["merchant_id"] == merchant_id),
            assessment_time,
        ),
        _visible(
            (r for r in source.financial_statements if r.values["merchant_id"] == merchant_id),
            assessment_time,
        ),
        _visible(
            (r for r in source.bureau_snapshots if r.values["merchant_id"] == merchant_id),
            assessment_time,
        ),
        tuple(
            visible
            for r in prior_loans
            if (visible := _visible_prior_loan(r, assessment_time)) is not None
        ),
        effective_policy,
    )


def historical_decision(context: HistoricalDecisionContext, rng: random.Random) -> str:
    """Synthetic lender using only the supplied application-time snapshot."""
    snapshot = context.snapshot
    bank = sum(_float(r.values.get("eligible_business_credits") or 0) for r in snapshot.banking)
    revenue = sum(_float(r.values.get("revenue") or 0) for r in snapshot.financials)
    bureau_scores = [
        _float(r.values["synthetic_rank"])
        for r in snapshot.bureau
        if r.values.get("synthetic_rank") is not None
    ]
    score = (sum(bureau_scores) / len(bureau_scores)) if bureau_scores else 600.0
    evidence_score = (
        min(1.0, bank / max(float(context.requested_amount) * 2.0, 1.0)) * 0.35
        + min(1.0, revenue / max(float(context.requested_amount), 1.0)) * 0.25
        + max(0.0, min(1.0, (score - 400) / 500)) * 0.25
        + min(1.0, len(snapshot.gst) / 12) * 0.15
    )
    draw = rng.random()
    if draw < 0.08:
        return "WITHDRAWN"
    return "APPROVED" if draw < 0.18 + 0.72 * evidence_score else "DECLINED"


def _policy_rows(tenant_id: str) -> tuple[list[SourceRecord], list[SourceRecord]]:
    policies: list[SourceRecord] = []
    clauses: list[SourceRecord] = []
    definitions = (
        ("POL-2025-v1", date(2025, 1, 1), date(2026, 1, 1)),
        ("POL-2026-v1", date(2026, 1, 1), None),
    )
    topics = (
        ("VINTAGE", "Minimum business vintage is reviewed using incorporation evidence."),
        ("BANKING", "Review available banking history and eligible business credits."),
        ("GST", "Review available GST filing history and reporting timeliness."),
        ("BUREAU", "Review bureau exposure and delinquency evidence when available."),
    )
    for version, start, end in definitions:
        pid = _id("PO", version)
        policies.append(
            _row(
                policy_id=pid,
                tenant_id=tenant_id,
                policy_code="SYNTHETIC_UNDERWRITING",
                version=version[4:],
                effective_from=start,
                effective_to=end,
            )
        )
        for code, text in topics:
            clauses.append(
                _row(
                    clause_id=_id("PC", version, code),
                    policy_id=pid,
                    clause_code=code,
                    clause_text=text,
                )
            )
    return policies, clauses


def generate_lending_world(world: SyntheticWorld, source: SourceWorld) -> LendingWorld:
    """Generate applications through evaluation rows without future-data feedback."""
    months = sorted({s.month for s in world.monthly_states})
    source_index: dict[str, dict[str, list[SourceRecord]]] = defaultdict(lambda: defaultdict(list))
    for name, rows in {
        "banking": source.banking_metrics,
        "gst": source.gst_returns,
        "digital": source.digital_metrics,
        "financials": source.financial_statements,
        "bureau": source.bureau_snapshots,
    }.items():
        for row in rows:
            source_index[str(row.values["merchant_id"])][name].append(row)
    app_rows: list[SourceRecord] = []
    request_rows: list[SourceRecord] = []
    decisions: list[DecisionResult] = []
    loans: list[SourceRecord] = []
    schedules: list[SourceRecord] = []
    repayments: list[SourceRecord] = []
    outcomes: list[SourceRecord] = []
    applications_by_merchant: dict[str, list[SourceRecord]] = defaultdict(list)
    # Applications occur early enough to leave an observation window.
    for merchant in world.merchants:
        local = _rng(world.seed, merchant.merchant_id, "apps")
        merchant_rows = source_index[merchant.merchant_id]
        merchant_source = SourceWorld(
            tuple(), tuple(), tuple(), tuple(merchant_rows["banking"]), tuple(), tuple(merchant_rows["gst"]),
            tuple(merchant_rows["digital"]), tuple(), tuple(merchant_rows["financials"]), tuple(merchant_rows["bureau"]), world.seed
        )
        if local.random() > 0.84:
            continue
        count = 2 if local.random() < 0.12 else 1
        # Most applications are early enough for mature performance, while a
        # small deterministic tail exercises the 2026 policy and censoring
        # rules without fabricating post-horizon observations.
        first_index = (
            local.randint(15, min(17, len(months) - 6))
            if local.random() < 0.10
            else local.randint(4, min(8, len(months) - 10))
        )
        for ordinal in range(count):
            month = months[min(first_index + ordinal * local.randint(2, 5), len(months) - 6)]
            app_date = month + timedelta(days=local.randint(5, 23) + ordinal * 3)
            application_id = _id("AP", merchant.merchant_id, ordinal, app_date)
            assessment = datetime(app_date.year, app_date.month, app_date.day, 18, tzinfo=UTC)
            product = (
                "RECEIVABLE_BACKED_LOAN"
                if merchant.product_affinity == "RECEIVABLE_BACKED_LOAN" and local.random() < 0.72
                else "TERM_LOAN"
            )
            visible_bank = [
                r
                for r in merchant_rows["banking"]
                if _datetime(r.values["available_at"]) <= assessment
            ]
            observed_revenue = sum(
                _float(r.values.get("eligible_business_credits") or 0) for r in visible_bank[-6:]
            )
            requested = Decimal(
                str(round(max(25_000, observed_revenue * (0.35 + local.random() * 0.65) / 6), 2))
            )
            tenor = local.choice((12, 18) if product == "TERM_LOAN" else (6, 9, 12))
            snapshot = application_snapshot(
                application_id,
                merchant.merchant_id,
                assessment,
                merchant_source,
                (
                    loan
                    for loan in loans
                    if loan.values["merchant_id"] == merchant.merchant_id
                    and _date(loan.values["disbursement_date"]) < app_date
                ),
            )
            policy_version = policy_version_for_date(app_date)
            snapshot = ApplicationSnapshot(
                snapshot.application_id,
                snapshot.merchant_id,
                snapshot.assessment_time,
                snapshot.banking,
                snapshot.gst,
                snapshot.digital,
                snapshot.financials,
                snapshot.bureau,
                snapshot.prior_loans,
                policy_version,
            )
            decision = historical_decision(
                HistoricalDecisionContext(snapshot, product, requested, tenor), local
            )
            decision_date = app_date + timedelta(days=local.randint(3, 12))
            app_rows.append(
                _row(
                    application_id=application_id,
                    tenant_id=merchant.tenant_id,
                    merchant_id=merchant.merchant_id,
                    application_date=app_date,
                    application_status=decision,
                    as_of_date=app_date,
                    requested_amount=requested,
                    requested_tenor_months=tenor,
                    loan_purpose="RECEIVABLES_FINANCING"
                    if product == "RECEIVABLE_BACKED_LOAN"
                    else "BUSINESS_EXPANSION",
                    created_at=datetime.combine(app_date, datetime.min.time(), tzinfo=UTC),
                )
            )
            request_id = _id("LR", application_id)
            request_rows.append(
                _row(
                    loan_request_id=request_id,
                    tenant_id=merchant.tenant_id,
                    application_id=application_id,
                    product_type=product,
                    requested_amount=requested,
                    requested_tenor_months=tenor,
                    requested_repayment_frequency="MONTHLY",
                    proposed_interest_rate=Decimal("0.18")
                    if product == "TERM_LOAN"
                    else Decimal("0.21"),
                    estimated_installment=None,
                    purpose_code="RECEIVABLES_FINANCING"
                    if product == "RECEIVABLE_BACKED_LOAN"
                    else "BUSINESS_EXPANSION",
                )
            )
            decisions.append(
                DecisionResult(application_id, decision, decision_date, "SYNTHETIC_POLICY")
            )
            app_rows[-1] = _row(**(app_rows[-1].values | {"decision_date": decision_date}))
            applications_by_merchant[merchant.merchant_id].append(app_rows[-1])
            if decision != "APPROVED":
                continue
            disbursement = decision_date + timedelta(days=local.randint(3, 20))
            sanctioned = (
                requested * Decimal(str(round(0.72 + local.random() * 0.25, 4)))
            ).quantize(Decimal("0.01"))
            disbursed = (
                sanctioned * Decimal(str(round(0.94 + local.random() * 0.06, 4)))
            ).quantize(Decimal("0.01"))
            loan_id = _id("LN", application_id)
            maturity = disbursement + timedelta(days=30 * tenor)
            loans.append(
                _row(
                    loan_id=loan_id,
                    tenant_id=merchant.tenant_id,
                    merchant_id=merchant.merchant_id,
                    application_id=application_id,
                    lender_name="Synthetic Historical Lender",
                    product_type=product,
                    sanctioned_amount=sanctioned,
                    disbursed_amount=disbursed,
                    sanction_date=decision_date,
                    disbursement_date=disbursement,
                    maturity_date=maturity,
                    status="ACTIVE",
                    available_at=datetime.combine(disbursement, datetime.min.time(), tzinfo=UTC),
                )
            )
            principal = (disbursed / tenor).quantize(Decimal("0.01"))
            interest = (disbursed * Decimal("0.18") / 12).quantize(Decimal("0.01"))
            remainder = disbursed - principal * tenor
            trajectory = _repayment_trajectory(
                world, merchant, disbursement, tenor, principal, interest, local
            )
            for installment in range(1, tenor + 1):
                due = disbursement + timedelta(days=30 * installment)
                p_due = principal + (remainder if installment == tenor else Decimal("0.00"))
                i_due = interest
                schedules.append(
                    _row(
                        loan_id=loan_id,
                        installment_number=installment,
                        due_date=due,
                        principal_due=p_due,
                        interest_due=i_due,
                        total_due=p_due + i_due,
                    )
                )
                payment = trajectory[installment - 1]
                payment_amount = cast(Decimal, payment["amount"])
                payment_date = cast(date, payment["date"])
                if payment_amount > 0 and cast(bool, payment["observed"]):
                    repayments.append(
                        _row(
                            repayment_transaction_id=_id("RP", loan_id, installment),
                            tenant_id=merchant.tenant_id,
                            loan_id=loan_id,
                            installment_number=installment,
                            transaction_date=payment_date,
                            amount_paid=payment_amount,
                            principal_allocated=min(p_due, payment_amount),
                            interest_allocated=max(
                                Decimal("0.00"), payment_amount - min(p_due, payment_amount)
                            ),
                            available_at=datetime.combine(
                                payment_date, datetime.min.time(), tzinfo=UTC
                            ),
                        )
                    )
            observed = [p for p in trajectory if cast(bool, p["observed"])]
            dpds = [int(cast(int, p["dpd"])) for p in observed]
            max_dpd = max(dpds, default=0)
            ever30 = max_dpd >= 30
            ever60 = max_dpd >= 60
            ever90 = max_dpd >= 90
            censored = len(observed) < tenor
            first_30 = next((i for i, value in enumerate(dpds) if value >= 30), None)
            first_60 = next((i for i, value in enumerate(dpds) if value >= 60), None)
            first_90 = next((i for i, value in enumerate(dpds) if value >= 90), None)
            cured = ever30 and any(
                cast(int, p["dpd"]) == 0
                for p in observed[max(i for i, p in enumerate(observed) if cast(int, p["dpd"]) >= 30) + 1 :]
                or []
            )
            cured_60 = first_60 is not None and any(value < 60 for value in dpds[first_60 + 1 :])
            cured_90 = first_90 is not None and any(value < 90 for value in dpds[first_90 + 1 :])
            runs: list[int] = []
            run = 0
            for value in dpds:
                run = run + 1 if value >= 30 else 0
                runs.append(run)
            observed_end = cast(date, observed[-1]["date"]) if observed else disbursement
            shock_states = [
                s for s in world.monthly_states
                if s.merchant_id == merchant.merchant_id
                and disbursement.replace(day=1) <= s.month <= observed_end.replace(day=1)
                and s.shock_type is not None
            ]
            code = (
                "CENSORED"
                if censored
                else "PERSISTENT_90_PLUS"
                if ever90 and not cured
                else "CURED_30_PLUS"
                if cured
                else "MATURED_CURRENT"
            )
            outcomes.append(
                _row(
                    outcome_id=_id("OC", loan_id),
                    tenant_id=merchant.tenant_id,
                    loan_id=loan_id,
                    outcome_date=max((cast(date, p["date"]) for p in observed), default=disbursement),
                    outcome_code=code,
                    days_past_due=max_dpd,
                    loss_amount=Decimal("0.00")
                    if max_dpd < 90
                    else (disbursed * Decimal("0.08")).quantize(Decimal("0.01")),
                    available_at=datetime.combine(
                        max((cast(date, p["date"]) for p in observed), default=disbursement),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                    # These are generator-side audit fields.  Persistence
                    # intentionally projects them away because the approved
                    # foundation schema stores only the public outcome fields.
                    ever_30=ever30,
                    ever_60=ever60,
                    ever_90=ever90,
                    observed_months=len(observed),
                    follow_up_months=len(observed),
                    delinquency_duration_months=max(runs, default=0),
                    cured_30=cured,
                    cured_60=cured_60,
                    cured_90=cured_90,
                    first_30_month=(first_30 + 1) if first_30 is not None else None,
                    first_60_month=(first_60 + 1) if first_60 is not None else None,
                    first_90_month=(first_90 + 1) if first_90 is not None else None,
                    shock_exposed=bool(shock_states),
                    shock_types=sorted(cast(str, s.shock_type) for s in shock_states),
                )
            )

    policies, clauses = _policy_rows(world.merchants[0].tenant_id)
    authority = [
        _row(
            rule_id=_id("AR", fact),
            tenant_id=world.merchants[0].tenant_id,
            fact_type=fact,
            source_type=source_type,
            priority=1,
        )
        for fact, source_type in (
            ("BANK_INFLOW", "BANKING"),
            ("GST_TURNOVER", "GST"),
            ("ACCOUNTING_REVENUE", "FINANCIALS"),
            ("BUREAU_EXPOSURE", "BUREAU"),
            ("APPLICATION_AMOUNT", "APPLICATION"),
            ("POLICY_THRESHOLD", "POLICY"),
        )
    ]
    documents, entities, facts, spans, questions = _evaluation_rows(
        world, source, app_rows, loans, policies
    )
    return LendingWorld(
        tuple(app_rows),
        tuple(request_rows),
        tuple(decisions),
        tuple(loans),
        tuple(schedules),
        tuple(repayments),
        tuple(outcomes),
        tuple(policies),
        tuple(clauses),
        tuple(documents),
        tuple(entities),
        tuple(authority),
        tuple(facts),
        tuple(spans),
        tuple(questions),
        world.seed,
    )


def _repayment_trajectory(
    world: SyntheticWorld,
    merchant: Any,
    disbursement: date,
    tenor: int,
    principal: Decimal,
    interest: Decimal,
    rng: random.Random,
) -> list[dict[str, object]]:
    states = [
        s
        for s in world.monthly_states
        if s.merchant_id == merchant.merchant_id and s.month >= disbursement.replace(day=1)
    ]
    current_dpd = 0
    result: list[dict[str, object]] = []
    for index in range(tenor):
        due = disbursement + timedelta(days=30 * (index + 1))
        state = states[index] if index < len(states) else None
        stress = max(0.0, -(state.shock_component if state else 0.0))
        risk = max(
            0.02,
            min(
                0.7,
                0.015
                + 0.07 * (1 - merchant.latent.values["repayment_discipline"])
                + 0.05 * merchant.latent.values["existing_leverage"]
                + 0.06 * stress
                + rng.gauss(0, 0.02),
            ),
        )
        if current_dpd >= 30:
            risk = min(0.65, risk + 0.10)
        missed = rng.random() < risk
        cure = current_dpd >= 30 and rng.random() < (
            0.10 + 0.25 * merchant.latent.values["repayment_discipline"]
        )
        if cure:
            current_dpd = 0
        elif missed:
            current_dpd = min(120, max(30, current_dpd + 30))
        else:
            current_dpd = max(0, current_dpd - 30)
        observed = due <= date(2026, 9, 1)
        amount = Decimal("0.00") if missed else principal + interest
        if not missed and current_dpd >= 30 and rng.random() < 0.35:
            amount = (amount * Decimal("0.55")).quantize(Decimal("0.01"))
        result.append({"date": due, "amount": amount, "dpd": current_dpd, "observed": observed})
    return result


def _evaluation_rows(
    world: SyntheticWorld,
    source: SourceWorld,
    applications: list[SourceRecord],
    loans: list[SourceRecord],
    policies: list[SourceRecord],
) -> tuple[list[SourceRecord], list[SourceRecord], list[SourceRecord], list[SourceRecord], list[SourceRecord]]:
    documents: list[SourceRecord] = []
    entities: list[SourceRecord] = []
    facts: list[SourceRecord] = []
    spans: list[SourceRecord] = []
    questions: list[SourceRecord] = []
    deep = [m for m in world.merchants if m.deep_cohort]
    merchant_facts: dict[str, dict[str, tuple[str, str, str]]] = {}
    merchant_meta: dict[str, tuple[str, date, float]] = {}
    for merchant in deep:
        app = next((a for a in applications if a.values["merchant_id"] == merchant.merchant_id), None)
        merchant_source_rows = [
            row for rows in (source.banking_metrics, source.gst_returns, source.financial_statements, source.bureau_snapshots)
            for row in rows if row.values["merchant_id"] == merchant.merchant_id
        ]
        if app is not None:
            as_of = _date(app.values["as_of_date"])
            available = datetime.combine(as_of, datetime.min.time(), tzinfo=UTC)
        else:
            # A deep merchant without an application still receives corpus
            # coverage from its latest structured evidence, but never gets an
            # invented application, policy or underwriting decision.
            available = max(
                (_datetime(row.values["available_at"]) for row in merchant_source_rows),
                default=datetime.combine(max(s.month for s in world.monthly_states), datetime.max.time(), tzinfo=UTC),
            )
            as_of = available.date()
        rows = {
            "banking": [r for r in source.banking_metrics if r.values["merchant_id"] == merchant.merchant_id and _datetime(r.values["available_at"]) <= available],
            "gst": [r for r in source.gst_returns if r.values["merchant_id"] == merchant.merchant_id and _datetime(r.values["available_at"]) <= available],
            "financials": [r for r in source.financial_statements if r.values["merchant_id"] == merchant.merchant_id and _datetime(r.values["available_at"]) <= available],
            "bureau": [r for r in source.bureau_snapshots if r.values["merchant_id"] == merchant.merchant_id and _datetime(r.values["available_at"]) <= available],
        }
        bank_total = sum((_float(r.values.get("eligible_business_credits") or 0) for r in rows["banking"]), 0.0)
        gst_total = sum((_float(r.values.get("outward_supplies") or 0) for r in rows["gst"]), 0.0)
        financial = max(rows["financials"], key=lambda r: _date(r.values["period_end"])) if rows["financials"] else None
        bureau = max(rows["bureau"], key=lambda r: _date(r.values["snapshot_date"])) if rows["bureau"] else None
        policy_version = policy_version_for_date(as_of)
        merchant_meta[merchant.merchant_id] = (merchant.sector_code, as_of, bank_total)
        policy_text = f"Policy {policy_version} clause BANKING: review available banking history and eligible business credits."
        source_values: list[tuple[str, str, str, str, object]] = []
        if app is not None:
            source_values.extend((
                ("APPLICATION_SUMMARY", "APPLICATION", "REQUESTED_AMOUNT", f"requested amount INR {app.values['requested_amount']}", {"amount": str(app.values["requested_amount"]), "as_of": str(as_of)}),
                ("CREDIT_APPRAISAL", "APPLICATION", "APPLICATION_PRODUCT", f"application {app.values['application_id']} requests {app.values['requested_tenor_months']} months for {app.values['loan_purpose']}", {"application_id": app.values["application_id"], "tenor": app.values["requested_tenor_months"]}),
                ("POLICY_EXCERPT", "POLICY", "POLICY_THRESHOLD", policy_text, {"policy_version": policy_version, "clause_code": "BANKING"}),
            ))
        if rows["banking"]:
            source_values.append(("BANKING_ANALYSIS", "BANKING", "ELIGIBLE_BANK_CREDITS", f"eligible bank credits INR {bank_total:.2f}", {"amount": str(bank_total), "as_of": str(as_of)}))
        if rows["gst"]:
            source_values.append(("GST_SUMMARY", "GST", "GST_TURNOVER", f"GST outward supplies INR {gst_total:.2f}", {"amount": str(gst_total), "as_of": str(as_of)}))
        if financial is not None:
            source_values.append(("FINANCIAL_ANALYSIS", "FINANCIALS", "FINANCIAL_REVENUE", f"financial revenue {_float(financial.values.get('revenue') or 0):.2f}", {"revenue": str(financial.values.get("revenue")), "liabilities": str(financial.values.get("total_liabilities")), "as_of": str(as_of)}))
        if bureau is not None:
            source_values.append(("BUREAU_SUMMARY", "BUREAU", "BUREAU_EXPOSURE", f"bureau outstanding INR {_float(bureau.values.get('total_outstanding') or 0):.2f}", {"outstanding": str(bureau.values.get("total_outstanding")), "score": str(bureau.values.get("synthetic_rank")), "as_of": str(as_of)}))
        merchant_facts[merchant.merchant_id] = {}
        for doc_type, source_type, fact_type, evidence, value in source_values:
            doc_id = _id("DO", merchant.merchant_id, app.values["application_id"] if app else "NO-APPLICATION", doc_type)
            text = f"{merchant.legal_name} {evidence}."
            documents.append(_row(document_id=doc_id, tenant_id=merchant.tenant_id, document_name=f"{merchant.merchant_id}-{doc_type.lower()}.txt", origin="SYNTHETIC_STRUCTURED", storage_uri=f"synthetic://02c/{doc_id}", content_hash=hashlib.sha256(text.encode()).hexdigest(), document_version="02C-v2", authorization_metadata={"access": "UNDERWRITING", "restricted": merchant.merchant_id.endswith(("7", "8"))}, available_at=available, content=text, document_type=doc_type, source_type=source_type))
            entities.append(_row(document_id=doc_id, entity_type="MERCHANT", entity_id=merchant.merchant_id))
            start = text.index(evidence)
            fact_id = _id("GF", doc_id, fact_type)
            span_id = _id("GS", doc_id, fact_type)
            facts.append(_row(fact_id=fact_id, tenant_id=merchant.tenant_id, entity_type="MERCHANT", entity_id=merchant.merchant_id, fact_type=fact_type, value_json=value, document_id=doc_id, version="02C-v2", source_type=source_type))
            spans.append(_row(span_id=span_id, tenant_id=merchant.tenant_id, document_id=doc_id, version="02C-v2", page=1, char_start=start, char_end=start + len(evidence), verbatim_text=evidence, source_type=source_type))
            merchant_facts[merchant.merchant_id][source_type] = (fact_id, span_id, doc_id)

        merchant_sources = merchant_facts[merchant.merchant_id]
        if app is not None:
            policy_fact, policy_span, policy_doc = merchant_sources["POLICY"]
            if "BANKING" in merchant_sources:
                bank_fact, bank_span, bank_doc = merchant_sources["BANKING"]
                questions.append(_row(question_id=_id("GQ", merchant.merchant_id, "DIRECT"), tenant_id=merchant.tenant_id, question=f"What eligible bank credits were available for {merchant.legal_name}?", expected_route={"source": "BANKING", "document_id": bank_doc}, required_evidence=[bank_fact], supporting_evidence=[bank_span], forbidden_evidence=[], expected_answer={"status": "SUPPORTED"}, behaviour="DIRECT_FACT"))
                questions.append(_row(question_id=_id("GQ", merchant.merchant_id, "TEMPORAL"), tenant_id=merchant.tenant_id, question=f"What evidence was available for {merchant.legal_name} at assessment time?", expected_route={"source": "BANKING", "as_of": str(as_of)}, required_evidence=[bank_fact], supporting_evidence=[bank_span], forbidden_evidence=[], expected_answer={"as_of": str(as_of)}, behaviour="TEMPORAL"))
            if "BANKING" in merchant_sources and "GST" in merchant_sources:
                gst_fact, gst_span, _ = merchant_sources["GST"]
                questions.append(_row(question_id=_id("GQ", merchant.merchant_id, "COMPARISON"), tenant_id=merchant.tenant_id, question=f"How should bank credits for {merchant.legal_name} be compared with GST turnover?", expected_route={"sources": ["BANKING", "GST"], "as_of": str(as_of)}, required_evidence=[bank_fact, gst_fact], supporting_evidence=[bank_span, gst_span], forbidden_evidence=[], expected_answer={"comparison": "Use aligned periods and source scope."}, behaviour="SOURCE_COMPARISON"))
            if all(key in merchant_sources for key in ("BANKING", "FINANCIALS", "BUREAU")):
                fin_fact, fin_span, _ = merchant_sources["FINANCIALS"]
                bureau_fact, bureau_span, _ = merchant_sources["BUREAU"]
                questions.append(_row(question_id=_id("GQ", merchant.merchant_id, "MULTI_HOP"), tenant_id=merchant.tenant_id, question=f"Why can reported activity coexist with repayment-capacity concern for {merchant.legal_name}?", expected_route={"sources": ["BANKING", "FINANCIALS", "BUREAU"]}, required_evidence=[bank_fact, fin_fact, bureau_fact], supporting_evidence=[bank_span, fin_span, bureau_span], forbidden_evidence=["FUTURE_OUTCOME"], expected_answer={"explanation": "Activity and repayment capacity are distinct evidence dimensions."}, behaviour="MULTI_HOP"))
            questions.append(_row(question_id=_id("GQ", merchant.merchant_id, "POLICY"), tenant_id=merchant.tenant_id, question="Which policy topic governs review of banking history?", expected_route={"policy_version": policy_version, "clause_code": "BANKING", "document_id": policy_doc}, required_evidence=[policy_fact], supporting_evidence=[policy_span], forbidden_evidence=[], expected_answer={"clause_code": "BANKING", "policy_version": policy_version}, behaviour="POLICY"))
            questions.append(_row(question_id=_id("GQ", merchant.merchant_id, "INSUFFICIENT"), tenant_id=merchant.tenant_id, question=f"What was {merchant.legal_name}'s post-application default probability?", expected_route={"answer": "INSUFFICIENT_EVIDENCE"}, required_evidence=[], supporting_evidence=[], forbidden_evidence=["MODEL_PREDICTION"], expected_answer={"status": "INSUFFICIENT_EVIDENCE"}, behaviour="INSUFFICIENT_EVIDENCE"))
        else:
            # Non-application deep merchants receive only source-grounded
            # questions plus an intentionally unanswerable application query.
            for source_type, category in (("BANKING", "BANKING"), ("GST", "GST"), ("FINANCIALS", "FINANCIALS"), ("BUREAU", "BUREAU")):
                if source_type not in merchant_sources:
                    continue
                fact_id, span_id, doc_id = merchant_sources[source_type]
                questions.append(_row(question_id=_id("GQ", merchant.merchant_id, "DIRECT", source_type), tenant_id=merchant.tenant_id, question=f"What {category.lower()} evidence is available for {merchant.legal_name}?", expected_route={"source": source_type, "document_id": doc_id}, required_evidence=[fact_id], supporting_evidence=[span_id], forbidden_evidence=[], expected_answer={"status": "SUPPORTED"}, behaviour="DIRECT_FACT"))
            questions.append(_row(question_id=_id("GQ", merchant.merchant_id, "INSUFFICIENT"), tenant_id=merchant.tenant_id, question=f"What application decision was made for {merchant.legal_name}?", expected_route={"answer": "INSUFFICIENT_EVIDENCE"}, required_evidence=[], supporting_evidence=[], forbidden_evidence=["APPLICATION"], expected_answer={"status": "INSUFFICIENT_EVIDENCE"}, behaviour="INSUFFICIENT_EVIDENCE"))

    # Each deep merchant gets a deterministic cross-merchant distractor.  The
    # distractor is real structured evidence, not fabricated text, and is
    # explicitly forbidden for the merchant's direct fact question.
    eligible = sorted(merchant_facts)
    for merchant_id in eligible:
        merchant = next(m for m in deep if m.merchant_id == merchant_id)
        sector, as_of, bank_total = merchant_meta[merchant_id]
        candidates = [candidate for candidate in eligible if candidate != merchant_id]
        distractor_id = min(
            candidates,
            key=lambda candidate: (
                merchant_meta[candidate][0] != sector,
                abs(merchant_meta[candidate][2] - bank_total),
                abs((merchant_meta[candidate][1] - as_of).days),
                abs(int(candidate[1:]) - int(merchant_id[1:])),
            ),
        )
        distractor_fact = merchant_facts[distractor_id]["BANKING"][0]
        bank_fact, bank_span, bank_doc = merchant_facts[merchant_id]["BANKING"]
        questions.append(_row(question_id=_id("GQ", merchant_id, "HARD_NEGATIVE"), tenant_id=merchant.tenant_id, question=f"Which banking fact belongs to {merchant.legal_name}, not a similar merchant?", expected_route={"source": "BANKING", "document_id": bank_doc}, required_evidence=[bank_fact], supporting_evidence=[bank_span], forbidden_evidence=[distractor_fact], expected_answer={"merchant_id": merchant_id, "distractor_merchant_id": distractor_id, "dimensions": ["similar_name", "similar_id", "similar_monetary_value", "nearby_period"]}, behaviour="HARD_NEGATIVE"))
    return documents, entities, facts, spans, questions


def lending_checksum(world: LendingWorld) -> str:
    payload = {table: [r.values for r in rows] for table, rows in world.table_rows().items()}
    payload["decisions"] = [asdict(d) for d in world.decisions]
    return hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
