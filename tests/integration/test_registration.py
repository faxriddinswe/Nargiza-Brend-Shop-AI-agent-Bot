"""Ro'yxatdan o'tish, rollar, xodimlar (BR-011…BR-015, BR-047, BR-152). Faqat soxta ma'lumot."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import AddressForm, Customer, Role, StaffProfile, User
from bot.db.session import read_session, uow
from bot.services import staff as staff_svc
from bot.services import users as users_svc
from bot.services.users import ContactNotOwnError, verify_own_contact

SM = async_sessionmaker[AsyncSession]
ADMIN_PHONE = "+998900000099"
ADMINS = {ADMIN_PHONE}


async def _register(
    sm: SM, tg_id: int, phone: str, name: str = "Umida", form: AddressForm = AddressForm.OPA
) -> users_svc.RegistrationResult:
    async with uow(sm, actor_kind="system") as s:
        user = await users_svc.get_or_create_user(s, tg_id, name)
        return await users_svc.register(
            s, user, raw_phone=phone, name=name, address_form=form, admin_phones=ADMINS
        )


async def _user(sm: SM, tg_id: int) -> User:
    async with read_session(sm) as s:
        u = await s.scalar(select(User).where(User.telegram_id == tg_id))
        assert u is not None
        return u


async def _admin(sm: SM) -> User:
    await _register(sm, 1, ADMIN_PHONE, "Faxriddin", AddressForm.AKA)
    return await _user(sm, 1)


# ---------------------------------------------------------------- BR-152
@pytest.mark.parametrize(("contact_uid", "sender"), [(None, 10), (11, 10)])
def test_foreign_contact_rejected(contact_uid: int | None, sender: int) -> None:
    """BR-152: boshqaning kontakti yoki user_id'siz kontakt rad etiladi."""
    with pytest.raises(ContactNotOwnError):
        verify_own_contact(contact_uid, sender)


def test_own_contact_accepted() -> None:
    verify_own_contact(10, 10)


# ---------------------------------------------------------------- BR-011, BR-047
async def test_new_person_becomes_customer_with_new_record(sm: SM) -> None:
    r = await _register(sm, 100, "998900000001")
    assert r.role == Role.CUSTOMER
    assert r.customer_created is True
    assert r.display_name == "Umida opa"
    async with read_session(sm) as s:
        c = await s.get(Customer, r.customer_id)
        assert c is not None and c.phone == "+998900000001" and c.user_id is not None


async def test_existing_notebook_customer_is_linked_not_duplicated(sm: SM) -> None:
    """BR-047: daftardagi mijoz (xodim yozgan) raqami mos kelsa — bog'lanadi."""
    admin = await _admin(sm)
    async with uow(sm, actor_id=admin.id) as s:
        s.add(
            Customer(
                name="Umida",
                search_name="umida",
                phone="+998900000002",
                address_form="opa",
                note="Shahlo opaning qizi",
            )
        )
    r = await _register(sm, 101, "+998900000002", name="Umidaxon")
    assert r.customer_created is False
    assert r.display_name == "Umida opa"  # daftardagi ism
    async with read_session(sm) as s:
        rows = (await s.scalars(select(Customer).where(Customer.phone == "+998900000002"))).all()
    assert len(rows) == 1 and rows[0].user_id is not None


async def test_reregistration_is_idempotent(sm: SM) -> None:
    r1 = await _register(sm, 102, "+998900000003")
    r2 = await _register(sm, 102, "+998900000003")
    assert r1.customer_id == r2.customer_id
    assert r2.customer_created is False


# ---------------------------------------------------------------- BR-013 admin
async def test_admin_phone_gets_admin_role_and_no_customer_record(sm: SM) -> None:
    r = await _register(sm, 1, ADMIN_PHONE, "Faxriddin", AddressForm.AKA)
    assert r.role == Role.ADMIN
    assert r.customer_id is None


async def test_sync_admins_demotes_removed_admin(sm: SM) -> None:
    await _admin(sm)
    async with uow(sm, actor_kind="system") as s:
        promoted, demoted = await users_svc.sync_admins(
            s, admin_phones=set(), admin_telegram_ids=set()
        )
    assert demoted and not promoted
    assert (await _user(sm, 1)).role == Role.CUSTOMER


async def test_sync_admins_promotes_by_telegram_id(sm: SM) -> None:
    await _register(sm, 555, "+998900000055")
    async with uow(sm, actor_kind="system") as s:
        await users_svc.sync_admins(s, admin_phones=set(), admin_telegram_ids={555})
    assert (await _user(sm, 555)).role == Role.ADMIN


# ---------------------------------------------------------------- BR-012 staff
async def test_staff_added_before_registration_becomes_staff_on_contact(sm: SM) -> None:
    admin = await _admin(sm)
    async with uow(sm, actor_id=admin.id) as s:
        await staff_svc.add_staff(
            s, admin, raw_phone="90 000 00 10", display_name="Nodira opa", section_codes=["shop"]
        )
    r = await _register(sm, 200, "+998900000010", name="Nargiza")
    assert r.role == Role.STAFF
    assert r.display_name == "Nodira opa"
    assert r.customer_id is None  # xodim uchun mijoz yozuvi yaratilmaydi


async def test_staff_added_after_registration_is_promoted_immediately(sm: SM) -> None:
    admin = await _admin(sm)
    await _register(sm, 201, "+998900000011", name="Nilufar")
    async with uow(sm, actor_id=admin.id) as s:
        view = await staff_svc.add_staff(
            s,
            admin,
            raw_phone="+998900000011",
            display_name="Nilufar opa",
            section_codes=["lingerie"],
        )
    assert view.section_codes == ("lingerie",)
    assert (await _user(sm, 201)).role == Role.STAFF


async def test_only_admin_can_add_staff(sm: SM) -> None:
    """BR-012: bot hech qachon o'zi xodim qilmaydi; xodim ham xodim qo'sha olmaydi."""
    await _register(sm, 300, "+998900000020")
    customer = await _user(sm, 300)
    with pytest.raises(staff_svc.NotAdminError):
        async with uow(sm, actor_id=customer.id) as s:
            await staff_svc.add_staff(
                s, customer, raw_phone="+998900000021", display_name="X", section_codes=[]
            )


async def test_duplicate_staff_phone_rejected(sm: SM) -> None:
    admin = await _admin(sm)
    async with uow(sm, actor_id=admin.id) as s:
        await staff_svc.add_staff(
            s, admin, raw_phone="+998900000012", display_name="A opa", section_codes=[]
        )
    with pytest.raises(staff_svc.StaffExistsError):
        async with uow(sm, actor_id=admin.id) as s:
            await staff_svc.add_staff(
                s, admin, raw_phone="900000012", display_name="B opa", section_codes=[]
            )


async def test_staff_phone_from_new_account_needs_admin_approval(sm: SM) -> None:
    """BR-012a: yangi akkaunt avtomatik xodim bo'lmaydi; eski akkaunt darhol huquqdan mahrum."""
    admin = await _admin(sm)
    async with uow(sm, actor_id=admin.id) as s:
        view = await staff_svc.add_staff(
            s, admin, raw_phone="+998900000013", display_name="Nodira opa", section_codes=["shop"]
        )
    await _register(sm, 210, "+998900000013", name="Nargiza")  # eski akkaunt
    r = await _register(sm, 211, "+998900000013", name="Nargiza")  # yangi akkaunt
    assert r.role == Role.CUSTOMER
    assert r.staff_relink_profile_id == view.id
    assert r.previous_holder_role == Role.STAFF
    assert (await _user(sm, 210)).role == Role.CUSTOMER  # eski akkaunt endi xodim emas

    new_user = await _user(sm, 211)
    async with uow(sm, actor_id=admin.id) as s:
        await staff_svc.approve_relink(s, admin, view.id, new_user.id)
    assert (await _user(sm, 211)).role == Role.STAFF


async def test_removed_staff_loses_role(sm: SM) -> None:
    admin = await _admin(sm)
    async with uow(sm, actor_id=admin.id) as s:
        view = await staff_svc.add_staff(
            s, admin, raw_phone="+998900000014", display_name="X opa", section_codes=["shop"]
        )
    await _register(sm, 220, "+998900000014")
    async with uow(sm, actor_id=admin.id) as s:
        await staff_svc.remove_staff(s, admin, view.id)
    assert (await _user(sm, 220)).role == Role.CUSTOMER
    async with read_session(sm) as s:
        p = await s.get(StaffProfile, view.id)
        assert p is not None and p.deleted_at is not None  # soft delete
    # qayta ro'yxatdan o'tsa ham xodim bo'lmaydi
    r = await _register(sm, 220, "+998900000014")
    assert r.role == Role.CUSTOMER


async def test_block_staff(sm: SM) -> None:
    """BR-015"""
    admin = await _admin(sm)
    async with uow(sm, actor_id=admin.id) as s:
        view = await staff_svc.add_staff(
            s, admin, raw_phone="+998900000015", display_name="Y opa", section_codes=[]
        )
    await _register(sm, 230, "+998900000015")
    async with uow(sm, actor_id=admin.id) as s:
        await staff_svc.set_blocked(s, admin, view.id, True)
    assert (await _user(sm, 230)).is_blocked is True


async def test_section_owner_ids(sm: SM) -> None:
    """BR-026 uchun: bo'lim egalari."""
    admin = await _admin(sm)
    async with uow(sm, actor_id=admin.id) as s:
        await staff_svc.add_staff(
            s,
            admin,
            raw_phone="+998900000016",
            display_name="Nilufar opa",
            section_codes=["lingerie"],
        )
        await staff_svc.add_staff(
            s, admin, raw_phone="+998900000017", display_name="Nodira opa", section_codes=["shop"]
        )
    await _register(sm, 240, "+998900000016")
    await _register(sm, 241, "+998900000017")
    async with read_session(sm) as s:
        assert await staff_svc.section_owner_telegram_ids(s, "lingerie") == [240]
        assert await staff_svc.section_owner_telegram_ids(s, "shop") == [241]
