from random import Random

ARCHETYPES = (
    "stable_established", "fast_growing_cash_constrained", "seasonal_business",
    "leveraged_but_profitable", "cash_heavy_traditional", "digitally_mature",
    "weak_compliance", "volatile_young_business", "distressed_business",
    "strong_with_temporary_liquidity_pressure",
)

_BIAS = {
    "stable_established": (0.75, 0.05, 0.30, 0.65, 0.70, 0.75, 0.70, 0.75, 0.75, 0.20, 0.80, 0.78, 0.80, 0.78, 0.68, 0.35, 0.35, 0.55),
    "fast_growing_cash_constrained": (0.50, 0.80, 0.48, 0.35, 0.58, 0.45, 0.35, 0.65, 0.30, 0.52, 0.58, 0.60, 0.65, 0.55, 0.55, 0.45, 0.45, 0.82),
    "seasonal_business": (0.48, 0.18, 0.45, 0.88, 0.58, 0.55, 0.48, 0.52, 0.55, 0.35, 0.65, 0.63, 0.66, 0.58, 0.62, 0.42, 0.42, 0.65),
    "leveraged_but_profitable": (0.65, 0.15, 0.28, 0.28, 0.72, 0.65, 0.52, 0.55, 0.35, 0.82, 0.62, 0.65, 0.68, 0.65, 0.68, 0.40, 0.40, 0.70),
    "cash_heavy_traditional": (0.42, 0.05, 0.30, 0.32, 0.55, 0.48, 0.62, 0.18, 0.50, 0.30, 0.60, 0.55, 0.55, 0.42, 0.62, 0.45, 0.48, 0.60),
    "digitally_mature": (0.58, 0.20, 0.25, 0.32, 0.65, 0.62, 0.50, 0.90, 0.65, 0.30, 0.72, 0.74, 0.75, 0.72, 0.72, 0.35, 0.35, 0.60),
    "weak_compliance": (0.43, 0.10, 0.36, 0.35, 0.52, 0.42, 0.62, 0.38, 0.45, 0.40, 0.52, 0.45, 0.25, 0.30, 0.48, 0.55, 0.55, 0.65),
    "volatile_young_business": (0.28, 0.45, 0.78, 0.42, 0.48, 0.38, 0.45, 0.50, 0.30, 0.25, 0.46, 0.43, 0.55, 0.42, 0.30, 0.55, 0.52, 0.72),
    "distressed_business": (0.50, 0.05, 0.62, 0.32, 0.38, 0.25, 0.65, 0.28, 0.18, 0.78, 0.25, 0.25, 0.35, 0.30, 0.45, 0.65, 0.62, 0.78),
    "strong_with_temporary_liquidity_pressure": (0.68, 0.25, 0.32, 0.30, 0.72, 0.68, 0.35, 0.68, 0.25, 0.35, 0.75, 0.76, 0.78, 0.74, 0.76, 0.35, 0.35, 0.70),
}


def choose_archetype(rng: Random) -> str:
    return rng.choice(ARCHETYPES)


def sample_latents(archetype: str, rng: Random) -> dict[str, float]:
    values = {}
    for index, name in enumerate((
        "business_scale", "revenue_growth", "revenue_volatility", "seasonality_strength",
        "gross_margin_quality", "operating_margin_quality", "cash_dependence", "digital_adoption",
        "liquidity_buffer", "existing_leverage", "repayment_discipline", "bureau_quality",
        "gst_compliance_quality", "financial_reporting_quality", "business_stability",
        "customer_concentration", "supplier_concentration", "working_capital_intensity",
    )):
        center = _BIAS[archetype][index]
        values[name] = max(0.0, min(1.0, center + rng.gauss(0.0, 0.12)))
    values["cash_dependence"] = max(0.0, min(1.0, values["cash_dependence"] - 0.28 * values["digital_adoption"] + rng.gauss(0, 0.04)))
    values["bureau_quality"] = max(0.0, min(1.0, 0.55 * values["repayment_discipline"] + 0.45 * values["business_stability"] + rng.gauss(0, 0.08)))
    values["revenue_volatility"] = max(0.0, min(1.0, values["revenue_volatility"] - 0.25 * values["business_stability"] + rng.gauss(0, 0.03)))
    return values
