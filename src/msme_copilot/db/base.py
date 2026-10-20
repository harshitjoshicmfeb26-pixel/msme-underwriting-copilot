from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "authz"}
    tenant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Merchant(Base):
    __tablename__ = "merchants"
    __table_args__ = {"schema": "core"}
    merchant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(32), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    incorporation_date: Mapped[date | None] = mapped_column(Date)
    digital_share: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
