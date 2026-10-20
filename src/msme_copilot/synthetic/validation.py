import hashlib
import json
import math
import statistics
from collections import defaultdict
from collections import Counter
from dataclasses import asdict

from msme_copilot.synthetic.archetypes import ARCHETYPES
from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.models import LATENT_NAMES, SyntheticWorld


def _canonical(world: SyntheticWorld) -> str:
    return json.dumps(asdict(world), default=str, sort_keys=True, separators=(",", ":"))


def checksum(world: SyntheticWorld) -> str:
    return hashlib.sha256(_canonical(world).encode()).hexdigest()


def validate_world(world: SyntheticWorld, config: GeneratorConfig) -> dict[str, object]:
    merchants = world.merchants
    states = world.monthly_states
    assert len(merchants) == config.number_of_merchants
    assert len(states) == config.number_of_merchants * config.number_of_months
    assert len({merchant.merchant_id for merchant in merchants}) == len(merchants)
    assert sum(merchant.complex_cohort for merchant in merchants) == config.complex_cohort_size
    assert sum(merchant.deep_cohort for merchant in merchants) == config.deep_cohort_size
    for merchant in merchants:
        assert set(merchant.latent.values) == set(LATENT_NAMES)
        assert all(0 <= value <= 1 and math.isfinite(value) for value in merchant.latent.values.values())
        assert merchant.incorporation_date <= states[0].month
    assert len({(state.merchant_id, state.month) for state in states}) == len(states)
    assert all(state.canonical_revenue >= 0 for state in states)
    assert all(len({state.month for state in states if state.merchant_id == merchant.merchant_id}) == config.number_of_months for merchant in merchants)
    archetype_counts = Counter(merchant.archetype for merchant in merchants)
    assert set(archetype_counts) == set(ARCHETYPES)
    tags = {tag for merchant in merchants for tag in merchant.scenario_tags}
    required_tags = {"multiple_gstins_intended", "multiple_bank_accounts_intended", "strongly_seasonal", "temporary_liquidity_pressure"}
    assert required_tags <= tags
    return {"merchants": len(merchants), "merchant_months": len(states), "checksum": checksum(world), "archetype_counts": dict(sorted(archetype_counts.items())), "scenario_tags": sorted(tags)}


def statistical_sanity(world: SyntheticWorld) -> dict[str, float]:
    seasonal = [m for m in world.merchants if m.archetype == "seasonal_business"]
    stable = [m for m in world.merchants if m.archetype == "stable_established"]
    distressed = [m for m in world.merchants if m.archetype == "distressed_business"]
    digital = [m.latent.values["digital_adoption"] for m in world.merchants]
    cash = [m.latent.values["cash_dependence"] for m in world.merchants]
    stability = [m.latent.values["business_stability"] for m in world.merchants]
    volatility = [m.latent.values["revenue_volatility"] for m in world.merchants]

    def correlation(left: list[float], right: list[float]) -> float:
        left_mean = sum(left) / len(left)
        right_mean = sum(right) / len(right)
        numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
        denominator = (sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right)) ** 0.5
        return float(numerator / denominator)

    return {
        "seasonal_strength_mean": sum(m.latent.values["seasonality_strength"] for m in seasonal) / len(seasonal),
        "stable_strength_mean": sum(m.latent.values["seasonality_strength"] for m in stable) / len(stable),
        "digital_cash_correlation": correlation(digital, cash),
        "stability_volatility_correlation": correlation(stability, volatility),
        "distressed_liquidity_mean": sum(m.latent.values["liquidity_buffer"] for m in distressed) / len(distressed),
    }


def _percentiles(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {f"p{p}": ordered[min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1)))] for p in (10, 25, 50, 75, 90)}


def _ols_amplitude(values: list[float]) -> float:
    """Return annual Fourier amplitude after accounting for a linear trend."""
    rows = []
    for i, value in enumerate(values):
        angle = 2 * math.pi * (i % 12) / 12
        rows.append([1.0, i / max(1, len(values) - 1), math.sin(angle), math.cos(angle), math.log(max(value, 0.01))])
    normal = [[sum(row[a] * row[b] for row in rows) for b in range(4)] for a in range(4)]
    target = [sum(row[a] * row[4] for row in rows) for a in range(4)]
    for pivot in range(4):
        scale = normal[pivot][pivot]
        for col in range(pivot, 4):
            normal[pivot][col] /= scale
        target[pivot] /= scale
        for row in range(4):
            if row == pivot:
                continue
            factor = normal[row][pivot]
            for col in range(pivot, 4):
                normal[row][col] -= factor * normal[pivot][col]
            target[row] -= factor * target[pivot]
    return float(math.hypot(target[2], target[3]))


def _correlation(left: list[float], right: list[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    denominator = (sum((a - left_mean) ** 2 for a in left) * sum((b - right_mean) ** 2 for b in right)) ** 0.5
    return float(numerator / denominator)


def audit_world(world: SyntheticWorld) -> dict[str, object]:
    """Produce the final statistical-validation report for Slice 02A."""
    profiles = {merchant.merchant_id: merchant for merchant in world.merchants}
    series: dict[str, list[float]] = defaultdict(list)
    for state in world.monthly_states:
        series[state.merchant_id].append(float(state.canonical_revenue))
    realized = defaultdict(list)
    realized_volatility = defaultdict(list)
    for merchant_id, values in series.items():
        realized[profiles[merchant_id].archetype].append(_ols_amplitude(values))
        realized_volatility[profiles[merchant_id].archetype].append(statistics.pstdev([math.log(max(value, 0.01)) for value in values]))
    correlations = {
        "digital_adoption_vs_cash_dependence": _correlation([m.latent.values["digital_adoption"] for m in world.merchants], [m.latent.values["cash_dependence"] for m in world.merchants]),
        "business_stability_vs_revenue_volatility": _correlation([m.latent.values["business_stability"] for m in world.merchants], [m.latent.values["revenue_volatility"] for m in world.merchants]),
        "business_scale_vs_canonical_revenue": _correlation([m.latent.values["business_scale"] for m in world.merchants], [float(sum(series[m.merchant_id]) / len(series[m.merchant_id])) for m in world.merchants]),
        "repayment_discipline_vs_bureau_quality": _correlation([m.latent.values["repayment_discipline"] for m in world.merchants], [m.latent.values["bureau_quality"] for m in world.merchants]),
        "existing_leverage_vs_liquidity_buffer": _correlation([m.latent.values["existing_leverage"] for m in world.merchants], [m.latent.values["liquidity_buffer"] for m in world.merchants]),
    }
    overlap_variables = ("seasonality_strength", "cash_dependence", "business_stability", "revenue_volatility")
    overlap = {variable: {archetype: _percentiles([m.latent.values[variable] for m in world.merchants if m.archetype == archetype]) for archetype in sorted({m.archetype for m in world.merchants})} for variable in overlap_variables}
    scenario_counts = {tag: sum(tag in merchant.scenario_tags for merchant in world.merchants) for tag in sorted({tag for m in world.merchants for tag in m.scenario_tags})}
    shock_rows = {state.merchant_id: state for state in world.monthly_states}
    ordered_states = defaultdict(list)
    for state in world.monthly_states:
        ordered_states[state.merchant_id].append(state)
    shock_report: dict[str, object] = {}
    for shock_type in sorted({event.shock_type for event in world.shocks}):
        events = [event for event in world.shocks if event.shock_type == shock_type]
        affected = [state for state in world.monthly_states if state.shock_type == shock_type]
        recovery_ratios: list[float] = []
        for event in events:
            states_for_merchant = ordered_states[event.merchant_id]
            end = event.start_offset + event.duration_months
            recovery_ratios.extend(float(state.canonical_revenue / state.base_revenue) for state in states_for_merchant[end : min(len(states_for_merchant), end + 2)])
        shock_report[shock_type] = {
            "merchants": len({event.merchant_id for event in events}),
            "merchant_months": len(affected),
            "severity": _percentiles([event.severity for event in events]),
            "duration_months": _percentiles([float(event.duration_months) for event in events]),
            "mean_shock_revenue_ratio": sum(float(state.canonical_revenue / state.base_revenue) for state in affected) / len(affected),
            "mean_two_month_post_shock_ratio": sum(recovery_ratios) / len(recovery_ratios) if recovery_ratios else None,
        }
    return {"realized_seasonality": {archetype: {"n": len(values), "mean": sum(values) / len(values), "median": _percentiles(values)["p50"], "percentiles": _percentiles(values)} for archetype, values in realized.items()}, "realized_monthly_volatility": {archetype: {"n": len(values), "mean": sum(values) / len(values), "median": _percentiles(values)["p50"], "percentiles": _percentiles(values)} for archetype, values in realized_volatility.items()}, "correlations": correlations, "suspicious_correlations": {name: value for name, value in correlations.items() if abs(value) > 0.98}, "overlap": overlap, "scenario_counts": scenario_counts, "shock_report": shock_report, "shock_event_count": len(world.shocks), "shock_state_count": len(shock_rows)}
