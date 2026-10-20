from dataclasses import replace

from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.merchant_generator import generate_world
from msme_copilot.synthetic.validation import audit_world, checksum, statistical_sanity, validate_world


def test_world_is_reproducible_and_valid() -> None:
    config = GeneratorConfig(number_of_merchants=100, complex_cohort_size=10, deep_cohort_size=4)
    first = generate_world(config)
    second = generate_world(config)
    assert checksum(first) == checksum(second)
    report = validate_world(first, config)
    assert report["merchants"] == 100
    assert report["merchant_months"] == 2400
    assert checksum(first) != checksum(generate_world(replace(config, seed=314160)))


def test_latent_relationships_and_seasonality_are_non_degenerate() -> None:
    config = GeneratorConfig(number_of_merchants=600, complex_cohort_size=20, deep_cohort_size=5)
    world = generate_world(config)
    sanity = statistical_sanity(world)
    assert sanity["seasonal_strength_mean"] > sanity["stable_strength_mean"]
    assert sanity["distressed_liquidity_mean"] < 0.5
    assert sanity["digital_cash_correlation"] < -0.2
    assert sanity["stability_volatility_correlation"] < -0.2
    audit = audit_world(world)
    assert audit["realized_seasonality"]["seasonal_business"]["mean"] > audit["realized_seasonality"]["stable_established"]["mean"]
    assert audit["overlap"]["business_stability"]["distressed_business"]["p90"] > audit["overlap"]["business_stability"]["stable_established"]["p10"]
    assert audit["overlap"]["cash_dependence"]["digitally_mature"]["p90"] > audit["overlap"]["cash_dependence"]["cash_heavy_traditional"]["p10"]
    assert audit["shock_event_count"] > 0
    digital = [m.latent.values["digital_adoption"] for m in world.merchants]
    cash = [m.latent.values["cash_dependence"] for m in world.merchants]
    assert len(set(digital)) > 100
    assert sum(a * b for a, b in zip(digital, cash, strict=False)) / len(digital) < 0.45
