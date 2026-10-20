from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    seed: int = 314159
    number_of_merchants: int = 6000
    number_of_months: int = 24
    complex_cohort_size: int = 200
    deep_cohort_size: int = 40
    reference_date: date = date(2026, 9, 1)
    artifact_path: Path = Path("data/synthetic")
    tenant_id: str = "T001"

    def __post_init__(self) -> None:
        if self.number_of_merchants <= 0 or self.number_of_months <= 0:
            raise ValueError("merchant and month counts must be positive")
        if not 0 <= self.deep_cohort_size <= self.complex_cohort_size <= self.number_of_merchants:
            raise ValueError("cohort sizes must be nested and within the population")
