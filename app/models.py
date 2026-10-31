"""Database models for the supplied MediBuy fixture."""

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    material_code: Mapped[str] = mapped_column(String, nullable=False)
    material_name: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)

    agreements: Mapped[list["Agreement"]] = relationship(back_populates="supplier")
    purchase_order_lines: Mapped[list["PurchaseOrderLine"]] = relationship(back_populates="supplier")


class Agreement(Base):
    __tablename__ = "agreements"
    __table_args__ = (
        CheckConstraint("valid_from <= valid_to", name="ck_agreement_valid_dates"),
        CheckConstraint("annual_target_quantity > 0", name="ck_agreement_positive_target"),
        CheckConstraint(
            "annual_rebate_percent BETWEEN 0 AND 100",
            name="ck_agreement_rebate_percent",
        ),
    )

    agreement_id: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"), nullable=False)
    material_code: Mapped[str] = mapped_column(String, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    annual_target_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_rebate_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str] = mapped_column(String, nullable=False)

    supplier: Mapped[Supplier] = relationship(back_populates="agreements")
    versions: Mapped[list["AgreementVersion"]] = relationship(
        back_populates="agreement",
        cascade="all, delete-orphan",
        order_by="AgreementVersion.version_number",
    )


class AgreementVersion(Base):
    __tablename__ = "agreement_versions"
    __table_args__ = (
        UniqueConstraint("agreement_id", "version_number", name="uq_agreement_version_number"),
        CheckConstraint("version_number > 0", name="ck_version_positive_number"),
        CheckConstraint("effective_from <= effective_to", name="ck_version_effective_dates"),
        CheckConstraint("base_unit_price >= 0", name="ck_version_nonnegative_price"),
    )

    version_id: Mapped[str] = mapped_column(String, primary_key=True)
    agreement_id: Mapped[str] = mapped_column(ForeignKey("agreements.agreement_id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False)
    base_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    change_note: Mapped[str] = mapped_column(Text, nullable=False)

    agreement: Mapped[Agreement] = relationship(back_populates="versions")
    price_tiers: Mapped[list["PriceTier"]] = relationship(
        back_populates="agreement_version",
        cascade="all, delete-orphan",
        order_by="PriceTier.min_quantity_inclusive",
    )


class PriceTier(Base):
    __tablename__ = "price_tiers"
    __table_args__ = (
        UniqueConstraint("version_id", "min_quantity_inclusive", name="uq_tier_version_minimum"),
        CheckConstraint("min_quantity_inclusive >= 0", name="ck_tier_nonnegative_minimum"),
        CheckConstraint(
            "max_quantity_exclusive IS NULL OR max_quantity_exclusive > min_quantity_inclusive",
            name="ck_tier_valid_range",
        ),
        CheckConstraint("discount_percent BETWEEN 0 AND 100", name="ck_tier_discount_percent"),
    )

    tier_id: Mapped[str] = mapped_column(String, primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("agreement_versions.version_id"), nullable=False
    )
    min_quantity_inclusive: Mapped[int] = mapped_column(Integer, nullable=False)
    max_quantity_exclusive: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)

    agreement_version: Mapped[AgreementVersion] = relationship(back_populates="price_tiers")


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_po_positive_quantity"),
        CheckConstraint("entered_unit_price >= 0", name="ck_po_nonnegative_price"),
    )

    po_id: Mapped[str] = mapped_column(String, primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"), nullable=False)
    material_code: Mapped[str] = mapped_column(String, nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    entered_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)

    supplier: Mapped[Supplier] = relationship(back_populates="purchase_order_lines")
