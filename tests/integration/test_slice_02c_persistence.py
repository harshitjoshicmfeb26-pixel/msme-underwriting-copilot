import pytest
from sqlalchemy import text

from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.merchant_generator import generate_world
from msme_copilot.synthetic.slice_02c import generate_lending_world
from msme_copilot.synthetic.slice_02c_persistence import persist_lending_world
from msme_copilot.synthetic.sources import generate_source_world


@pytest.mark.integration
def test_slice_02c_persists_fk_safe_rows(db_engine):
    config = GeneratorConfig(seed=314159, number_of_merchants=50, complex_cohort_size=10, deep_cohort_size=4)
    world = generate_world(config)
    source = generate_source_world(world)
    lending = generate_lending_world(world, source)
    persist_lending_world(world, lending)
    with db_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM core.applications WHERE application_id LIKE 'AP%'")).scalar_one() == len(lending.applications)
        assert connection.execute(text("SELECT count(*) FROM lending.historical_loans WHERE loan_id LIKE 'LN%'")).scalar_one() == len(lending.loans)
        assert connection.execute(text("SELECT count(*) FROM lending.loan_outcomes WHERE outcome_id LIKE 'OC%'")).scalar_one() == len(lending.outcomes)
        assert connection.execute(text("SELECT count(*) FROM truth.gt_spans WHERE span_id LIKE 'GS%'")).scalar_one() == len(lending.gt_spans)
    # The shared session-scoped database fixture needs explicit isolation for the
    # next integration test; this is the disposable local test database only.
    with db_engine.begin() as connection:
        connection.execute(text("TRUNCATE authz.tenants CASCADE"))
