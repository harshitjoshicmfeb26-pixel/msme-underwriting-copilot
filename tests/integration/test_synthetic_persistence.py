from sqlalchemy import text

import pytest

from msme_copilot.synthetic.config import GeneratorConfig
from msme_copilot.synthetic.merchant_generator import generate_world
from msme_copilot.synthetic.persistence import persist_merchants

pytestmark = pytest.mark.integration


def test_generator_persists_canonical_merchants_only(db_engine) -> None:
    config = GeneratorConfig(number_of_merchants=6, complex_cohort_size=2, deep_cohort_size=1)
    world = generate_world(config)
    persist_merchants(world)
    with db_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM core.merchants WHERE merchant_id LIKE 'M%'")).scalar_one() == 6
        assert connection.execute(text("SELECT count(*) FROM source.bank_transactions")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM source.gst_returns")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM lending.loan_outcomes")).scalar_one() == 0
