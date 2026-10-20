from enum import StrEnum

class AnalystRole(StrEnum):
    ANALYST = "ANALYST"
    SUPERVISOR = "SUPERVISOR"
    ADMIN = "ADMIN"
class ProductType(StrEnum):
    TERM_LOAN = "TERM_LOAN"
    RECEIVABLE_BACKED_LOAN = "RECEIVABLE_BACKED_LOAN"
class BankDirection(StrEnum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
class GSTReturnType(StrEnum):
    GSTR1 = "GSTR1"
    GSTR3B = "GSTR3B"
class DigitalPaymentChannel(StrEnum):
    CARD_POS = "CARD_POS"
    UPI = "UPI"
    PAYMENT_GATEWAY = "PAYMENT_GATEWAY"
    OTHER_DIGITAL = "OTHER_DIGITAL"
class ReconciliationStatus(StrEnum):
    CONSISTENT = "CONSISTENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
