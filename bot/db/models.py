"""SQLAlchemy modellari — 1-bosqich poydevor jadvallari. Dizayn: docs/DATA_MODEL.md.

Eslatma: audit log va "DELETE taqiqi" Postgres trigger'larida (migratsiyada), bu yerda emas —
shunda ORM'dan tashqari yo'llar (bulk update, psql'da qo'lda tuzatish) ham audit'dan o'tadi.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Cheklov nomlari aniq bo'lsin — Alembic migratsiyalari barqaror bo'ladi.
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Telefon formati (E.164). Xodim yozgan raqamlar normalize_phone() bilan +998 ga keltiriladi.
PHONE_CHECK = r"phone ~ '^\+[0-9]{7,15}$'"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


class Role(StrEnum):
    ADMIN = "admin"
    STAFF = "staff"
    CUSTOMER = "customer"


class AddressForm(StrEnum):
    OPA = "opa"
    AKA = "aka"


class PendingStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


def _in(column: str, enum: type[StrEnum]) -> str:
    values = ", ".join(f"'{v.value}'" for v in enum)
    return f"{column} IN ({values})"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None]
    deleted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(_in("role", Role), name="role"),
        CheckConstraint("script_pref IN ('latn', 'cyrl')", name="script_pref"),
        CheckConstraint(PHONE_CHECK, name="phone_format"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    role: Mapped[str] = mapped_column(Text, server_default=Role.CUSTOMER.value)
    tg_first_name: Mapped[str | None] = mapped_column(Text)
    # Faqat o'zi ulashgan va tekshirilgan (contact.user_id == from_user.id) raqam
    phone: Mapped[str | None] = mapped_column(Text, unique=True)
    phone_verified_at: Mapped[datetime | None]
    is_blocked: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    bot_blocked_at: Mapped[datetime | None]
    ads_opt_out: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    script_pref: Mapped[str] = mapped_column(Text, server_default="latn")
    consent_at: Mapped[datetime | None]


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    card_number: Mapped[str | None] = mapped_column(Text)
    card_holder: Mapped[str | None] = mapped_column(Text)


class StaffProfile(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "staff_profiles"
    __table_args__ = (
        CheckConstraint(PHONE_CHECK, name="phone_format"),
        Index(
            "uq_staff_profiles_phone_active",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    phone: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))


class StaffSectionOwner(Base):
    __tablename__ = "staff_section_owners"

    staff_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("staff_profiles.id"), primary_key=True
    )
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sections.id"), primary_key=True)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        # 2-bosqichda debt_items (category_id, section_id) shu juftlikka FK qiladi —
        # tovar boshqa bo'lim yozuviga tushib qolishini DB o'zi to'xtatadi (BR-021).
        UniqueConstraint("id", "section_id", name="uq_categories_id_section"),
        CheckConstraint(
            "low_stock_threshold IS NULL OR low_stock_threshold >= 0", name="threshold"
        ),
        Index("uq_categories_name_lower", text("lower(name)"), unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sections.id"))
    name: Mapped[str] = mapped_column(Text)
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class CategorySynonym(Base):
    __tablename__ = "category_synonyms"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"))
    # search_key() ko'rinishida; bitta so'z faqat bitta turga tegishli
    synonym: Mapped[str] = mapped_column(Text, unique=True)


class Customer(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(_in("address_form", AddressForm), name="address_form"),
        CheckConstraint(PHONE_CHECK, name="phone_format"),
        Index(
            "uq_customers_phone_active",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_customers_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_customers_search_name_trgm",
            "search_name",
            postgresql_using="gin",
            postgresql_ops={"search_name": "gin_trgm_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    search_name: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    phone_missing: Mapped[bool] = mapped_column(Boolean, Computed("phone IS NULL", persisted=True))
    address_form: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class PendingAction(Base):
    """Tasdiqlash kartasi (BR-100…103). Idempotentlik: kalit faqat bir marta `done` bo'ladi."""

    __tablename__ = "pending_actions"
    __table_args__ = (CheckConstraint(_in("status", PendingStatus), name="status"),)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=PendingStatus.OPEN.value)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]


class AuditLog(Base):
    """Faqat trigger yozadi. UPDATE/DELETE trigger bilan taqiqlangan."""

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "action IN ('insert', 'update', 'soft_delete', 'restore', 'delete')", name="action"
        ),
        CheckConstraint("actor_kind IN ('user', 'system', 'migration')", name="actor_kind"),
        Index("ix_audit_log_table_record", "table_name", "record_id"),
        Index("ix_audit_log_at", "at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    actor_kind: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    table_name: Mapped[str] = mapped_column(Text)
    record_id: Mapped[str] = mapped_column(Text)
    old: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(server_default=func.now())


# ============================================================ Stage 2: debt ledger
class LedgerStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class PaymentKind(StrEnum):
    PAYMENT = "payment"  # cash came into the till
    WRITE_OFF = "write_off"  # forgiven — reported separately as a loss (BR-057)


class CancelMixin:
    status: Mapped[str] = mapped_column(Text, server_default=LedgerStatus.ACTIVE.value)
    cancelled_at: Mapped[datetime | None]
    cancel_reason: Mapped[str | None] = mapped_column(Text)


class Debt(CancelMixin, Base):
    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="amount_positive"),
        CheckConstraint("kind IN ('regular', 'sale_remainder')", name="kind"),
        CheckConstraint("(kind = 'sale_remainder') = (sale_id IS NOT NULL)", name="sale_link"),
        CheckConstraint("source IN ('manual', 'import')", name="source"),
        CheckConstraint("status IN ('active', 'cancelled')", name="status"),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancel_fields"
        ),
        CheckConstraint("due_date IS NULL OR due_date >= debt_date", name="due_after_date"),
        UniqueConstraint("sale_id", name="uq_debts_sale_id"),
        UniqueConstraint("id", "section_id", name="uq_debts_id_section"),
        UniqueConstraint("id", "section_id", "customer_id", name="uq_debts_id_section_customer"),
        Index(
            "uq_debts_import_ref",
            "source",
            "import_ref",
            unique=True,
            postgresql_where=text("import_ref IS NOT NULL"),
        ),
        Index(
            "ix_debts_open_fifo",
            "customer_id",
            "section_id",
            "debt_date",
            "id",
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "ix_debts_due",
            "due_date",
            postgresql_where=text("status = 'active' AND due_date IS NOT NULL"),
        ),
        Index(
            "ix_debts_no_due",
            "customer_id",
            postgresql_where=text("status = 'active' AND due_date IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customers.id"))
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sections.id"))
    kind: Mapped[str] = mapped_column(Text, server_default="regular")
    sale_id: Mapped[int | None] = mapped_column(BigInteger)
    debt_date: Mapped[date]
    due_date: Mapped[date | None]
    total_amount: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(Text, server_default="manual")
    import_ref: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class DebtItem(Base):
    __tablename__ = "debt_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price > 0", name="price_positive"),
        ForeignKeyConstraint(
            ["debt_id", "section_id"],
            ["debts.id", "debts.section_id"],
            name="fk_debt_items_debt_section",
        ),
        ForeignKeyConstraint(
            ["category_id", "section_id"],
            ["categories.id", "categories.section_id"],
            name="fk_debt_items_category_section",
        ),
        Index("ix_debt_items_debt", "debt_id"),
        Index("ix_debt_items_category", "category_id", "section_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    debt_id: Mapped[int] = mapped_column(BigInteger)
    section_id: Mapped[int] = mapped_column(BigInteger)
    category_id: Mapped[int] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(Text)


class Payment(CancelMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("kind IN ('payment', 'write_off')", name="kind"),
        CheckConstraint("(kind = 'payment') = (method IS NOT NULL)", name="method_only_for_cash"),
        CheckConstraint("method IS NULL OR method IN ('cash', 'card')", name="method"),
        CheckConstraint("source IN ('manual', 'import')", name="source"),
        CheckConstraint("status IN ('active', 'cancelled')", name="status"),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="cancel_fields"
        ),
        UniqueConstraint("id", "section_id", "customer_id", name="uq_payments_id_section_customer"),
        Index(
            "uq_payments_import_ref",
            "source",
            "import_ref",
            unique=True,
            postgresql_where=text("import_ref IS NOT NULL"),
        ),
        Index(
            "ix_payments_customer_open",
            "customer_id",
            "section_id",
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_payments_section_day", "section_id", "paid_on"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    customer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("customers.id"))
    section_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sections.id"))
    kind: Mapped[str] = mapped_column(Text)
    method: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(BigInteger)
    paid_on: Mapped[date]
    source: Mapped[str] = mapped_column(Text, server_default="manual")
    import_ref: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        UniqueConstraint("payment_id", "debt_id", name="uq_payment_allocations_payment_debt"),
        ForeignKeyConstraint(
            ["payment_id", "section_id", "customer_id"],
            ["payments.id", "payments.section_id", "payments.customer_id"],
            name="fk_payment_allocations_payment",
        ),
        ForeignKeyConstraint(
            ["debt_id", "section_id", "customer_id"],
            ["debts.id", "debts.section_id", "debts.customer_id"],
            name="fk_payment_allocations_debt",
        ),
        Index(
            "ix_payment_allocations_debt", "debt_id", postgresql_include=["payment_id", "amount"]
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    payment_id: Mapped[int] = mapped_column(BigInteger)
    debt_id: Mapped[int] = mapped_column(BigInteger)
    section_id: Mapped[int] = mapped_column(BigInteger)
    customer_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(BigInteger)
