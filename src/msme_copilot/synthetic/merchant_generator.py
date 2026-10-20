import math
import random
from datetime import date
from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP

from msme_copilot.synthetic.archetypes import choose_archetype, sample_latents
from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.models import LatentProfile, MerchantProfile, MonthlyState, ShockEvent, SyntheticWorld

SECTORS = (
    ("RETAIL", "retail/trading"), ("FOOD", "food/restaurants"), ("MFG", "manufacturing"),
    ("PROF", "professional/business services"), ("LOG", "logistics/transport"),
    ("HEALTH", "healthcare-related SME"), ("CONST", "construction/material supply"),
    ("WHOLESALE", "wholesale/distribution"),
)
LOCATIONS = (
    ("Maharashtra", "Mumbai"), ("Maharashtra", "Pune"), ("Karnataka", "Bengaluru"),
    ("Gujarat", "Ahmedabad"), ("Delhi", "New Delhi"), ("Tamil Nadu", "Chennai"),
    ("Telangana", "Hyderabad"), ("Rajasthan", "Jaipur"),
)
CONSTITUTIONS = ("PROPRIETORSHIP", "PARTNERSHIP", "LLP", "PRIVATE_LIMITED")
MONTHS_PER_YEAR = 12


def _month_start(year: int, month: int) -> date:
    return date(year + (month - 1) // 12, (month - 1) % 12 + 1, 1)


def _month_shift(value: date, offset: int) -> date:
    return _month_start(value.year, value.month + offset)


def _money(value: float) -> Decimal:
    return Decimal(str(max(0.0, value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _tags(profile: MerchantProfile) -> tuple[str, ...]:
    tags: list[str] = []
    latent = profile.latent.values
    if profile.intended_gstin_count > 1:
        tags.append("multiple_gstins_intended")
    if profile.intended_bank_account_count > 1:
        tags.append("multiple_bank_accounts_intended")
    if latent["cash_dependence"] > 0.7:
        tags.append("cash_heavy")
    if latent["cash_dependence"] > 0.68 and latent["digital_adoption"] > 0.55:
        tags.append("own_account_transfer_heavy")
    if latent["seasonality_strength"] > 0.72:
        tags.append("strongly_seasonal")
    if profile.archetype == "strong_with_temporary_liquidity_pressure":
        tags.append("temporary_liquidity_pressure")
    if latent["liquidity_buffer"] < 0.38 and latent["working_capital_intensity"] > 0.65:
        tags.append("temporary_cash_flow_stress")
    if latent["business_scale"] > 0.68 and latent["repayment_discipline"] < 0.48:
        tags.append("strong_revenue_weak_repayment_capacity")
    if latent["business_scale"] > 0.65 and latent["revenue_growth"] > 0.55 and latent["working_capital_intensity"] > 0.65:
        tags.append("rapid_growth_cash_constraint")
    if latent["existing_leverage"] > 0.7 and latent["operating_margin_quality"] > 0.6:
        tags.append("leveraged_profitable")
    if latent["gst_compliance_quality"] < 0.4 and latent["business_stability"] > 0.6:
        tags.append("healthy_weak_compliance")
    return tuple(sorted(set(tags)))


def _build_merchant(index: int, config: GeneratorConfig, rng: random.Random, complex_ids: set[str], deep_ids: set[str]) -> MerchantProfile:
    merchant_id = f"M{index:06d}"
    archetype = choose_archetype(rng)
    latent = sample_latents(archetype, rng)
    sector_code, sector_name = rng.choice(SECTORS)
    state, city = rng.choice(LOCATIONS)
    scale = latent["business_scale"]
    gst_count = 1 + int(scale > 0.67 and rng.random() < 0.48) + int(scale > 0.84 and rng.random() < 0.22)
    bank_count = 1 + int(scale > 0.50 and rng.random() < 0.42) + int(scale > 0.80 and rng.random() < 0.18)
    if sector_code in {"WHOLESALE", "MFG", "LOG"} and rng.random() < 0.35:
        affinity = "RECEIVABLE_BACKED_LOAN"
    else:
        affinity = "TERM_LOAN"
    first_month = _month_shift(config.reference_date, -config.number_of_months + 1)
    start = date(first_month.year - rng.randint(1, 12), rng.randint(1, 12), 1)
    profile = MerchantProfile(
        merchant_id=merchant_id,
        tenant_id=config.tenant_id,
        legal_name=f"{sector_name.title()} Enterprise {index:06d}",
        trade_name=f"{sector_code.title()} Works {index:06d}",
        constitution=rng.choice(CONSTITUTIONS),
        sector_code=sector_code,
        sector_name=sector_name,
        incorporation_date=start,
        city=city,
        state=state,
        udyam_category="MICRO" if scale < 0.45 else "SMALL" if scale < 0.78 else "MEDIUM",
        digital_share=Decimal(str(round(latent["digital_adoption"] * 0.9, 6))),
        archetype=archetype,
        latent=LatentProfile(latent),
        intended_gstin_count=gst_count,
        intended_bank_account_count=bank_count,
        product_affinity=affinity,
        complex_cohort=merchant_id in complex_ids,
        deep_cohort=merchant_id in deep_ids,
        scenario_tags=(),
    )
    return replace(profile, scenario_tags=_tags(profile))


def _monthly_states(profile: MerchantProfile, config: GeneratorConfig, rng: random.Random) -> tuple[list[MonthlyState], list[ShockEvent]]:
    latent = profile.latent.values
    sector_scale = {"MFG": 1.25, "WHOLESALE": 1.18, "LOG": 1.05, "PROF": 0.85}.get(profile.sector_code, 1.0)
    base = 100_000 * (0.45 + 1.8 * latent["business_scale"]) * sector_scale * rng.uniform(0.78, 1.24)
    phase = rng.uniform(0, 2 * math.pi)
    shock_events: list[ShockEvent] = []
    shock_types = ("temporary_demand_drop", "supplier_disruption", "temporary_liquidity_pressure", "growth_acceleration", "short_operational_disruption")
    if rng.random() < 0.68:
        shock_type = rng.choice(shock_types)
        severity = rng.uniform(0.12, 0.28) if shock_type == "growth_acceleration" else -rng.uniform(0.14, 0.34)
        shock_events.append(ShockEvent(profile.merchant_id, shock_type, rng.randrange(2, config.number_of_months - 3), rng.randint(1, 3), severity))
    if profile.archetype in {"distressed_business", "strong_with_temporary_liquidity_pressure"} and rng.random() < 0.65:
        shock_events.append(ShockEvent(profile.merchant_id, "temporary_liquidity_pressure", rng.randrange(3, config.number_of_months - 3), rng.randint(1, 3), -rng.uniform(0.18, 0.38)))
    rows: list[MonthlyState] = []
    for offset in range(config.number_of_months):
        month = _month_shift(config.reference_date, -config.number_of_months + 1 + offset)
        trend = (1 + latent["revenue_growth"] * 0.22 - 0.09) ** (offset / max(1, config.number_of_months - 1))
        seasonal = 1 + latent["seasonality_strength"] * (0.10 + 0.28 * math.sin(2 * math.pi * month.month / 12 + phase))
        active = [event for event in shock_events if event.start_offset <= offset < event.start_offset + event.duration_months]
        shock = sum(event.severity for event in active)
        active_shock_type: str | None = active[0].shock_type if active else None
        realized = base * trend * seasonal * (1 + shock) * max(0.55, rng.gauss(1.0, 0.06 + 0.13 * latent["revenue_volatility"]))
        liquidity = max(0.0, min(1.0, latent["liquidity_buffer"] - latent["working_capital_intensity"] * 0.28 - max(0.0, -shock) * 0.45 + rng.gauss(0, 0.05)))
        operating = max(0.0, min(1.0, latent["business_stability"] - max(0.0, -shock) * 0.25 + rng.gauss(0, 0.04)))
        rows.append(MonthlyState(profile.merchant_id, month, _money(base), trend, seasonal, shock, active_shock_type, _money(realized), liquidity, operating))
    return rows, shock_events


def generate_world(config: GeneratorConfig | None = None) -> SyntheticWorld:
    """Generate a reproducible canonical merchant world and hidden monthly state."""
    config = config or GeneratorConfig()
    rng = random.Random(config.seed)
    ids = [f"M{i:06d}" for i in range(1, config.number_of_merchants + 1)]
    complex_ids = set(rng.sample(ids, config.complex_cohort_size))
    deep_ids = set(rng.sample(ids, config.deep_cohort_size))
    merchants: list[MerchantProfile] = []
    states: list[MonthlyState] = []
    shocks: list[ShockEvent] = []
    for index in range(1, config.number_of_merchants + 1):
        merchant = _build_merchant(index, config, rng, complex_ids, deep_ids)
        merchants.append(merchant)
        merchant_states, merchant_shocks = _monthly_states(merchant, config, rng)
        states.extend(merchant_states)
        shocks.extend(merchant_shocks)
    return SyntheticWorld(tuple(merchants), tuple(states), tuple(shocks), config.seed)
