from datetime import timedelta

from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.merchant_generator import generate_world
from msme_copilot.synthetic.sources import generate_source_world, rows_usable_at


def test_as_of_filter_excludes_future_rows_for_all_source_families():
    world = generate_world(GeneratorConfig(number_of_merchants=20, complex_cohort_size=6, deep_cohort_size=3))
    source = generate_source_world(world)
    rows = [
        source.gst_returns,
        source.bureau_snapshots,
        source.banking_metrics,
        source.bank_transactions,
        source.digital_metrics,
        source.digital_daily,
        source.financial_statements,
    ]
    for family in rows:
        record = min(family, key=lambda item: item.values["available_at"])
        available = record.values["available_at"]
        assert record in rows_usable_at(family, available)
        assert record not in rows_usable_at(family, available - timedelta(microseconds=1))


def test_as_of_filter_has_explicit_amendment_and_bureau_cases():
    world = generate_world(GeneratorConfig(number_of_merchants=20, complex_cohort_size=6, deep_cohort_size=3))
    source = generate_source_world(world)
    amended = [row for row in source.gst_returns if row.values["source_version"] == "AMENDED"]
    assert amended
    amendment = amended[0]
    assert amendment not in rows_usable_at(source.gst_returns, amendment.values["available_at"] - timedelta(seconds=1))
    bureau = source.bureau_snapshots[0]
    as_of = bureau.values["available_at"] - timedelta(seconds=1)
    assert bureau not in rows_usable_at(source.bureau_snapshots, as_of)
