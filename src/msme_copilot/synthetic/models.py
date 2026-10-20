from dataclasses import dataclass
from datetime import date
from decimal import Decimal


LATENT_NAMES = (
    "business_scale", "revenue_growth", "revenue_volatility", "seasonality_strength",
    "gross_margin_quality", "operating_margin_quality", "cash_dependence", "digital_adoption",
    "liquidity_buffer", "existing_leverage", "repayment_discipline", "bureau_quality",
    "gst_compliance_quality", "financial_reporting_quality", "business_stability",
    "customer_concentration", "supplier_concentration", "working_capital_intensity",
)


@dataclass(frozen=True, slots=True)
class LatentProfile:
    values: dict[str, float]


@dataclass(frozen=True, slots=True)
class MerchantProfile:
    merchant_id: str
    tenant_id: str
    legal_name: str
    trade_name: str
    constitution: str
    sector_code: str
    sector_name: str
    incorporation_date: date
    city: str
    state: str
    udyam_category: str
    digital_share: Decimal
    archetype: str
    latent: LatentProfile
    intended_gstin_count: int
    intended_bank_account_count: int
    product_affinity: str
    complex_cohort: bool
    deep_cohort: bool
    scenario_tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MonthlyState:
    merchant_id: str
    month: date
    base_revenue: Decimal
    trend_component: float
    seasonal_component: float
    shock_component: float
    shock_type: str | None
    canonical_revenue: Decimal
    liquidity_condition: float
    operating_condition: float


@dataclass(frozen=True, slots=True)
class ShockEvent:
    merchant_id: str
    shock_type: str
    start_offset: int
    duration_months: int
    severity: float


@dataclass(frozen=True, slots=True)
class SyntheticWorld:
    merchants: tuple[MerchantProfile, ...]
    monthly_states: tuple[MonthlyState, ...]
    shocks: tuple[ShockEvent, ...]
    seed: int


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """A source-system row represented without leaking 02A latent state."""

    values: dict[str, object]


@dataclass(frozen=True, slots=True)
class SourceWorld:
    """Observable 02B evidence generated independently from the canonical world."""

    merchants: tuple[SourceRecord, ...]
    bank_accounts: tuple[SourceRecord, ...]
    bank_transactions: tuple[SourceRecord, ...]
    banking_metrics: tuple[SourceRecord, ...]
    gstins: tuple[SourceRecord, ...]
    gst_returns: tuple[SourceRecord, ...]
    digital_metrics: tuple[SourceRecord, ...]
    digital_daily: tuple[SourceRecord, ...]
    financial_statements: tuple[SourceRecord, ...]
    bureau_snapshots: tuple[SourceRecord, ...]
    seed: int

    def table_rows(self) -> dict[str, tuple[SourceRecord, ...]]:
        return {
            "merchant_bank_accounts": self.bank_accounts,
            "bank_transactions": self.bank_transactions,
            "banking_metrics": self.banking_metrics,
            "merchant_gstins": self.gstins,
            "gst_returns": self.gst_returns,
            "digital_payment_metrics": self.digital_metrics,
            "digital_sales_daily": self.digital_daily,
            "financial_statements": self.financial_statements,
            "bureau_snapshots": self.bureau_snapshots,
        }
