from datetime import UTC, datetime
from datetime import date

from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.merchant_generator import generate_world
from msme_copilot.synthetic.models import SourceRecord
from msme_copilot.synthetic.slice_02c import (
    application_snapshot,
    generate_lending_world,
    lending_checksum,
)
from msme_copilot.synthetic.sources import generate_source_world


def _generated():
    config = GeneratorConfig(seed=314159, number_of_merchants=80, complex_cohort_size=12, deep_cohort_size=4)
    world = generate_world(config)
    source = generate_source_world(world)
    return world, source, generate_lending_world(world, source)


def test_02c_is_reproducible_and_has_bounded_population():
    world, source, lending = _generated()
    _, _, repeat = _generated()
    assert lending_checksum(lending) == lending_checksum(repeat)
    assert 20 <= len(lending.applications) <= 120
    assert lending.loans
    assert len(lending.outcomes) == len(lending.loans)


def test_application_snapshot_excludes_future_source_rows():
    world, source, _ = _generated()
    merchant_id = world.merchants[0].merchant_id
    assessment = datetime(2025, 1, 1, tzinfo=UTC)
    snapshot = application_snapshot("AP-TEST", merchant_id, assessment, source)
    assert all(row.values["available_at"] <= assessment for row in snapshot.banking)
    assert all(row.values["available_at"] <= assessment for row in snapshot.gst)
    assert all(row.values["available_at"] <= assessment for row in snapshot.digital)
    assert all(row.values["available_at"] <= assessment for row in snapshot.financials)
    assert all(row.values["available_at"] <= assessment for row in snapshot.bureau)


def test_loan_schedule_and_repayment_invariants():
    _, _, lending = _generated()
    loans = {row.values["loan_id"]: row for row in lending.loans}
    assert all(row.values["disbursed_amount"] <= row.values["sanctioned_amount"] for row in lending.loans)
    assert all(row.values["maturity_date"] > row.values["disbursement_date"] for row in lending.loans)
    assert all(row.values["total_due"] == row.values["principal_due"] + row.values["interest_due"] for row in lending.schedules)
    assert all(row.values["transaction_date"] >= loans[row.values["loan_id"]].values["disbursement_date"] for row in lending.repayments)
    assert {row.values["loan_id"] for row in lending.outcomes} == set(loans)


def test_ground_truth_spans_match_documents_and_insufficient_evidence_exists():
    _, _, lending = _generated()
    docs = {row.values["document_id"]: row.values for row in lending.documents}
    for span in lending.gt_spans:
        document = docs[span.values["document_id"]]["content"]
        assert document[span.values["char_start"] : span.values["char_end"]] == span.values["verbatim_text"]
    assert any(row.values["behaviour"] == "INSUFFICIENT_EVIDENCE" for row in lending.golden_questions)


def test_repeat_application_sees_only_prior_observed_history():
    _, source, _ = _generated()
    prior = SourceRecord(
        {
            "loan_id": "LN-PRIOR",
            "merchant_id": "M-TEST",
            "disbursement_date": date(2025, 1, 1),
            "repayment_history": [
                {"transaction_date": date(2025, 2, 1), "dpd": 0},
                {"transaction_date": date(2025, 5, 1), "dpd": 90},
            ],
        }
    )
    snapshot = application_snapshot(
        "AP-REPEAT", "M-TEST", datetime(2025, 3, 1, tzinfo=UTC), source, [prior]
    )
    assert snapshot.prior_loans[0].values["repayment_history"] == [
        {"transaction_date": date(2025, 2, 1), "dpd": 0}
    ]
