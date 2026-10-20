from decimal import Decimal

import pytest

from msme_copilot.config import Settings
from msme_copilot.domain.money import money


def test_settings_load() -> None:
    settings = Settings(DB_HOST="db", DB_PORT=5433, DB_NAME="x", DB_USER="u", DB_PASSWORD="p")
    assert settings.db_host == "db"
    assert settings.database_url.startswith("postgresql+psycopg://u:p@db:5433/x")


def test_money_uses_decimal_and_rejects_float() -> None:
    assert money("12.30") == Decimal("12.30")
    with pytest.raises(TypeError):
        money(1.2)  # type: ignore[arg-type]
