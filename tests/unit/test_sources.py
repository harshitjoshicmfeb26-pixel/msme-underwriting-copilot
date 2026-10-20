from datetime import UTC, datetime

from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.merchant_generator import generate_world
from msme_copilot.synthetic.source_validation import validate_source_world
from msme_copilot.synthetic.sources import generate_source_world, source_checksum


def _world():
    return generate_world(GeneratorConfig(seed=314159, number_of_merchants=80, complex_cohort_size=12, deep_cohort_size=4))


def test_sources_are_reproducible_and_have_expected_population():
    first = generate_source_world(_world())
    second = generate_source_world(_world())
    assert source_checksum(first) == source_checksum(second)
    other = generate_source_world(generate_world(GeneratorConfig(seed=314160, number_of_merchants=80, complex_cohort_size=12, deep_cohort_size=4)))
    assert source_checksum(first) != source_checksum(other)
    assert len(first.banking_metrics) == 80 * 24
    assert len(first.digital_metrics) == 80 * 24
    assert len(first.bank_transactions) > 0
    assert len(first.digital_daily) > 0


def test_source_temporality_and_deep_bank_reconciliation():
    source = generate_source_world(_world())
    now = datetime(2020, 1, 1, tzinfo=UTC)
    assert all(row.values["available_at"] > now for row in source.banking_metrics)
    by_month: dict[tuple[str, object], float] = {}
    for row in source.bank_transactions:
        if row.values["credit_category"] == "BUSINESS_RECEIPT":
            key = (str(row.values["merchant_id"]), row.values["value_date"].replace(day=1))
            by_month[key] = by_month.get(key, 0.0) + float(row.values["amount"])
    assert by_month


def test_source_audit_reports_non_deterministic_relationships():
    source = generate_source_world(_world())
    report = validate_source_world(_world(), source)
    assert report["row_counts"]["banking_metrics"] == 80 * 24
    assert report["suspicious_correlations"] == {}
