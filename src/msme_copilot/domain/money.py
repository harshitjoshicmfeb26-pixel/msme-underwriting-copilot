from decimal import Decimal

def money(value: str | int | Decimal) -> Decimal:
    """Convert money without routing through binary floating point."""
    if isinstance(value, float):
        raise TypeError("money values must not be constructed from float")
    return Decimal(str(value)).quantize(Decimal("0.01"))
