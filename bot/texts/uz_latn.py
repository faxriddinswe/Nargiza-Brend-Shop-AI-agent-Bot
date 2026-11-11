"""Barcha bot matnlari (o'zbek, lotin). Kodda foydalanuvchi matni yozilmaydi — faqat shu yerdan.

Har bir yangi matn ux-copy-reviewer agentidan o'tadi. Apostrof: oddiy `'`.
"""

from __future__ import annotations

from typing import Final

from bot.services.settings import ShopInfo

# ------------------------------------------------------------------ umumiy
GENERIC_ERROR: Final = "Kechirasiz, nimadir xato ketdi. Birozdan keyin qayta urinib ko'ring 🙏"


def blocked(shop_phone: str) -> str:
    return f"Kechirasiz, bot siz uchun vaqtincha yopilgan. Do'kon bilan bog'laning: {shop_phone}"


CMD_START: Final = "Bosh menyu"
COMING_SOON: Final = "Bu bo'lim tez orada ishga tushadi 🙂"
UNKNOWN_INPUT: Final = "Tushunmadim. Iltimos, pastdagi tugmalardan birini tanlang 👇"
PLEASE_START: Final = "Boshlash uchun /start ni bosing 👇"

# ------------------------------------------------------------------ start / ro'yxatdan o'tish (BR-150…153)
BTN_REGISTER: Final = "📝 Ro'yxatdan o'tish"


def welcome(shop: ShopInfo) -> str:
    return (
        f"Assalomu alaykum! {shop.name} do'koniga xush kelibsiz 🌸\n\n"
        "👗 Ayollar kiyimlari, oyoq kiyimlari va ichki kiyimlar\n"
        f"📍 {shop.address}\n"
        f"🕖 Ish vaqti: {shop.hours}\n"
        f"📞 {shop.phone}\n"
        f"📸 Instagram: {shop.instagram}\n\n"
        "Yangi kolleksiyalar, chegirmalar va do'kon yangiliklaridan birinchi bo'lib "
        "xabardor bo'lish uchun ro'yxatdan o'ting 👇"
    )


ASK_NAME: Final = "Ismingiz nima? Pastdagi tugmani bosing yoki ismingizni yozing ✍️"
NAME_INVALID: Final = "Ismingizni harflar bilan yozib yuboring, iltimos. Masalan: Umida"
ASK_ADDRESS_FORM: Final = "Sizga qanday murojaat qilaylik? 👇"
BTN_OPA: Final = "Opa"
BTN_AKA: Final = "Aka"
ASK_PHONE: Final = (
    "Telefon raqamingizni ulashing 👇\n\n"
    "🔒 Raqamingiz faqat do'kon xabarlari va xaridlaringiz hisobi uchun saqlanadi."
)
BTN_SHARE_PHONE: Final = "📱 Raqamni ulashish"
PHONE_USE_BUTTON: Final = (
    "Raqamni yozish shart emas — pastdagi «📱 Raqamni ulashish» tugmasini bosing 👇"
)
CONTACT_NOT_OWN: Final = (
    "Bu raqam boshqa odamniki ekan. "
    "O'z raqamingizni «📱 Raqamni ulashish» tugmasi bilan yuboring 👇"
)
ALREADY_REGISTERED: Final = "Siz allaqachon ro'yxatdan o'tgansiz ✅"


def registered_customer(display_name: str) -> str:
    return f"✅ Rahmat, {display_name}! Siz ro'yxatdan o'tdingiz."


def registered_staff(display_name: str) -> str:
    return f"✅ Xush kelibsiz, {display_name}! Siz xodim sifatida ulandingiz."


def registered_admin(display_name: str) -> str:
    return f"✅ Xush kelibsiz, {display_name}! Siz admin sifatida ulandingiz."


STAFF_RELINK_WAIT: Final = (
    "Raqamingiz boshqa Telegram'da xodim sifatida turibdi. Tasdiqlash uchun so'rov yubordik — "
    "tasdiqlansa, darhol xabar beramiz 🙏"
)

# ------------------------------------------------------------------ mijoz menyusi (BR-154)
BTN_MY_DEBT: Final = "💰 Mening qarzim"
BTN_NEWS: Final = "📢 E'lonlar"
BTN_ABOUT: Final = "🏪 Do'kon haqida"
BTN_CONTACT: Final = "📞 Bog'lanish"
BTN_SETTINGS: Final = "⚙️ Sozlamalar"
BTN_ADS_OFF: Final = "🔕 Reklamani o'chirish"
BTN_ADS_ON: Final = "🔔 Reklamani yoqish"
BTN_BACK: Final = "⬅️ Orqaga"

MENU_HINT: Final = "Kerakli bo'limni tanlang 👇"
NO_DEBT: Final = "Sizda qarz yo'q ✅"
ACCOUNT_CHECKING: Final = (
    "Ma'lumotlaringiz tekshirilmoqda. Tez orada tayyor bo'ladi 🙏\n"
    "Savolingiz bo'lsa, do'konga qo'ng'iroq qiling."
)
NO_NEWS: Final = "Hozircha yangi e'lonlar yo'q. Yangilik bo'lsa, birinchi bo'lib sizga yozamiz 🌸"
SETTINGS_TITLE: Final = "⚙️ Sozlamalar"
ADS_OFF_DONE: Final = (
    "🔕 Reklama xabarlari o'chirildi.\nQarz eslatmalari va shaxsiy xabarlar kelaveradi."
)
ADS_ON_DONE: Final = "🔔 Reklama xabarlari yoqildi."


def about(shop: ShopInfo) -> str:
    return (
        f"🏪 {shop.name}\n\n"
        f"📍 Manzil: {shop.address}\n"
        f"🕖 Ish vaqti: {shop.hours} (har kuni)\n"
        f"📞 Telefon: {shop.phone}\n"
        f"📸 Instagram: {shop.instagram}"
    )


def contact_us(shop: ShopInfo) -> str:
    return (
        "📞 Biz bilan bog'lanish:\n\n"
        f"Telefon: {shop.phone}\n"
        f"Instagram: {shop.instagram_url}\n\n"
        f"Do'konimizga keling: {shop.address} 🌸"
    )


# ------------------------------------------------------------------ xodim menyusi (master 13)
BTN_STAFF_DEBT: Final = "➕ Qarz"
BTN_STAFF_SALE: Final = "🛍 Savdo"
BTN_STAFF_PAYMENT: Final = "💵 To'lov"
BTN_STAFF_SEARCH: Final = "🔍 Qidirish"
BTN_STAFF_REPORT: Final = "📊 Hisobot"
BTN_STAFF_STOCK: Final = "📦 Ombor"
BTN_STAFF_BROADCAST: Final = "📢 E'lon"
BTN_STAFF_MORE: Final = "⚙️ Boshqa"
STAFF_MENU_HINT: Final = "Asosiy menyu 👇"

# ------------------------------------------------------------------ admin (BR-012, BR-014)
ADMIN_PANEL: Final = "🛠 Admin paneli"
BTN_ADMIN_STAFF: Final = "👥 Xodimlar"
BTN_ADMIN_ADD_STAFF: Final = "➕ Xodim qo'shish"
BTN_ADMIN_STATS: Final = "📊 Statistika"
BTN_ADMIN_SHOP_PHOTO: Final = "🖼 Do'kon rasmi"
BTN_ADMIN_SHOP_LOCATION: Final = "📍 Xaritadagi joy"

ADD_STAFF_ASK_PHONE: Final = "Xodimning telefon raqamini yozing.\nMasalan: 90 123 45 67"
ADD_STAFF_BAD_PHONE: Final = (
    "Raqam noto'g'ri ko'rinadi. 9 xonali raqamni yozing, masalan: 90 123 45 67"
)
ADD_STAFF_ASK_NAME: Final = "Botda unga qanday murojaat qilinsin?\nMasalan: Nodira opa"
ADD_STAFF_ASK_SECTIONS: Final = (
    "Bu xodim qaysi bo'limga javobgar? Belgilang va «✅ Tayyor» ni bosing.\n"
    "Boshqalar shu bo'limga yozsa, unga xabar boradi."
)
BTN_DONE: Final = "✅ Tayyor"
BTN_CONFIRM: Final = "✅ Tasdiqlash"
BTN_CANCEL: Final = "❌ Bekor qilish"
CANCELLED: Final = "❌ Bekor qilindi."
CARD_EXPIRED: Final = "⌛️ Bu so'rovning vaqti o'tdi. Iltimos, qaytadan boshlang."
CARD_NOT_YOURS: Final = "Buni faqat boshlagan odam tasdiqlay oladi."
CARD_ALREADY_DONE: Final = "✅ Bu allaqachon saqlangan."
STAFF_EXISTS: Final = "Bu raqam bilan xodim allaqachon bor."
SECTION_NAMES: Final = {"shop": "Do'kon", "lingerie": "Ichki kiyim"}


def staff_card(display_name: str, phone: str, sections: list[str]) -> str:
    owned = ", ".join(SECTION_NAMES[c] for c in sections) or "—"
    return (
        "👤 Yangi xodim\n\n"
        f"Ism: {display_name}\n"
        f"Telefon: {phone}\n"
        f"Bo'lim egasi: {owned}\n\n"
        "Tasdiqlaysizmi?"
    )


def staff_added(display_name: str, linked: bool) -> str:
    tail = (
        "U botga allaqachon ulangan — darhol xodim bo'ldi."
        if linked
        else "U botni ochib, «Start» ni bosib, raqamini ulashganda o'zi xodim bo'ladi."
    )
    return f"✅ {display_name} xodim sifatida qo'shildi.\n{tail}"


NO_STAFF: Final = "Hozircha xodimlar yo'q."


def staff_line(name: str, phone: str, sections: list[str], linked: bool, blocked: bool) -> str:
    owned = ", ".join(SECTION_NAMES[c] for c in sections) or "—"
    status = "🚫 bloklangan" if blocked else ("✅ ulangan" if linked else "⏳ hali ulanmagan")
    return f"👤 {name}\n📞 {phone}\n🏷 {owned}\n{status}"


BTN_BLOCK: Final = "🚫 Bloklash"
BTN_UNBLOCK: Final = "✅ Blokdan chiqarish"
BTN_REMOVE_STAFF: Final = "❌ Xodimlikdan olish"
STAFF_BLOCKED: Final = "🚫 Bloklandi. U endi botda hech narsa qila olmaydi."
STAFF_UNBLOCKED: Final = "✅ Blokdan chiqarildi."
STAFF_REMOVED: Final = "Xodimlikdan olindi. U endi oddiy mijoz."
STAFF_NOT_LINKED: Final = "Xodim hali botga ulanmagan."


STAFF_ACTION_QUESTIONS: Final = {
    "block_staff": "{name}ni bloklaysizmi?",
    "unblock_staff": "{name}ni blokdan chiqarasizmi?",
    "remove_staff": "{name}ni xodimlikdan olasizmi?",
}


def confirm_staff_action(action: str, name: str) -> str:
    return STAFF_ACTION_QUESTIONS[action].format(name=name)


def stats(counts: dict[str, int], customers: int, customers_linked: int) -> str:
    return (
        "📊 Statistika\n\n"
        f"👑 Admin: {counts.get('admin', 0)}\n"
        f"👥 Xodimlar: {counts.get('staff', 0)}\n"
        f"🙋 Botdagi mijozlar: {counts.get('customer', 0)}\n"
        f"📒 Daftardagi mijozlar: {customers} (botga ulangan: {customers_linked})"
    )


ASK_SHOP_PHOTO: Final = "Do'kon rasmini yuboring (xush kelibsiz xabarida ko'rinadi)."
SHOP_PHOTO_SAVED: Final = "✅ Rasm saqlandi."
ASK_SHOP_LOCATION: Final = "Do'kon joylashuvini yuboring: 📎 → Joylashuv."
SHOP_LOCATION_SAVED: Final = "✅ Joylashuv saqlandi."


def relink_request(staff_name: str, phone_masked: str) -> str:
    return (
        f"⚠️ {staff_name} raqami ({phone_masked}) boshqa Telegram'dan ulashildi.\n"
        "Eski Telegram'dan xodim huquqlari olindi.\n\n"
        "Yangisini xodim qilib tasdiqlaysizmi?"
    )


def customer_move_request(name: str, phone_masked: str) -> str:
    return (
        f"⚠️ Mijoz {name} ({phone_masked}) raqami boshqa Telegram'dan ulashildi.\n"
        "Raqam boshqa odamga o'tgan bo'lishi mumkin. Shu odamga mijozning qarz ma'lumotlarini "
        "ko'rsataylikmi?\n\nShubha bo'lsa — mijozga qo'ng'iroq qilib tekshiring."
    )


CUSTOMER_MOVED: Final = "✅ Tasdiqlandi. Mijoz ma'lumotlari yangi Telegram'ga ulandi."
RELINK_APPROVED: Final = "✅ Tasdiqlandi. Endi u yangi Telegram'dan xodim sifatida ishlaydi."
RELINK_REJECTED: Final = "Rad etildi. Bu Telegram oddiy mijoz bo'lib qoladi."


def relink_approved_for_staff(display_name: str) -> str:
    return f"✅ {display_name}, tasdiqlandi! Siz xodim sifatida ulandingiz."


ROLE_NAMES: Final = {"admin": "Admin", "staff": "Xodim", "customer": "Mijoz"}


def phone_moved_alert(role: str, phone_masked: str) -> str:
    return (
        f"⚠️ Diqqat: {ROLE_NAMES.get(role, role)} raqami ({phone_masked}) boshqa Telegram'ga o'tdi. "
        "Eski Telegram'dan huquqlar olindi."
    )


# ============================================================ Stage 2: customers, debts, payments
from datetime import date  # noqa: E402

from bot.utils.dates import format_date  # noqa: E402
from bot.utils.money import format_amount as money  # noqa: E402
from bot.utils.phone import format_phone  # noqa: E402

MAX_DEBT_LINES: Final = 5  # Telegram messages are limited to 4096 characters
ASK_CUSTOMER_DEBT: Final = "Kimga qarz yozamiz? Ismini yoki telefon raqamini yozing 👇"
ASK_CUSTOMER_PAYMENT: Final = "Kim to'lov qildi? Ismini yoki telefon raqamini yozing 👇"
ASK_CUSTOMER_SEARCH: Final = (
    "Kimni qidiramiz? Ismini yoki telefon raqamini (oxirgi raqamlarini) yozing 👇"
)
SEARCH_EMPTY: Final = "Hech kim topilmadi. Boshqacha yozib ko'ring yoki yangi mijoz qo'shing 👇"
SEARCH_TOO_SHORT: Final = "Yana bir-ikki harf yozing, iltimos."
BTN_NEW_CUSTOMER: Final = "➕ Yangi mijoz"
BTN_MORE_RESULTS: Final = "🔽 Yana ko'rsatish"
CUSTOMER_NOT_FOUND: Final = "Bu mijoz topilmadi (o'chirilgan bo'lishi mumkin)."


def search_header(total: int) -> str:
    return f"Topildi: {total} ta. Kimni tanlaysiz?"


def customer_button(name: str, note: str | None, balance: int) -> str:
    parts = [name]
    if note:
        parts.append(note[:18])
    parts.append(money(balance) if balance else "qarz yo'q")
    return " · ".join(parts)


# ---- new customer
NEWC_ASK_NAME: Final = "Yangi mijozning ismi nima?"
NEWC_ASK_FORM: Final = "Unga qanday murojaat qilamiz?"
NEWC_ASK_PHONE: Final = (
    "Telefon raqamini yozing (masalan: 90 123 45 67).\nRaqami bo'lmasa, pastdagi tugmani bosing."
)
BTN_NO_PHONE: Final = "📵 Raqami yo'q"
NEWC_ASK_NOTE: Final = (
    "Eslatma yozing, bir xil ismlarni ajratish uchun (masalan: «Shahlo opaning qizi»)."
)
BTN_SKIP: Final = "⏭ O'tkazib yuborish"
PHONE_TAKEN: Final = "Bu raqam bilan mijoz bor, uni pastda ko'rsatdim 👇"
NEWC_BAD_PHONE: Final = "Raqamni to'liq o'qiy olmadim. 9 ta raqamni yozing, masalan: 90 123 45 67"


def new_customer_card(name: str, form: str, phone: str | None, note: str | None) -> str:
    lines = ["👤 Yangi mijoz", "", f"Ism: {name} {form}"]
    lines.append(f"Telefon: {format_phone(phone)}" if phone else "Telefon: ⚠️ kerak (hozircha yo'q)")
    if note:
        lines.append(f"Eslatma: {note}")
    lines += ["", "Saqlaymizmi?"]
    return "\n".join(lines)


def customer_created(name: str, form: str) -> str:
    return f"✅ {name} {form} mijozlar ro'yxatiga qo'shildi."


# ---- customer card
BTN_C_DEBT: Final = "➕ Qarz yozish"
BTN_C_PAY: Final = "💵 To'lov"
BTN_C_WRITEOFF: Final = "🤝 Kechish"
BTN_C_DELETE: Final = "🗑 O'chirish"


def customer_card(
    name: str,
    form: str,
    phone: str | None,
    note: str | None,
    sections: list[tuple[str, int, list[str]]],
) -> str:
    """sections: (section code, balance, open debt lines)."""
    head = f"👤 {name} {form}"
    lines = [head]
    lines.append(f"📞 {format_phone(phone)}" if phone else "📞 ⚠️ telefon kerak")
    if note:
        lines.append(f"📝 {note}")
    if not sections:
        lines += ["", "Qarzi yo'q ✅"]
    for code, balance, debts in sections:
        lines += ["", f"💰 {SECTION_NAMES[code]}: {money(balance)}"]
        lines += [f"  {d}" for d in debts[:MAX_DEBT_LINES]]
        if len(debts) > MAX_DEBT_LINES:
            lines.append(f"  {more_debts(len(debts) - MAX_DEBT_LINES)}")
    return "\n".join(lines)


def debt_line(debt_date: date, due: date | None, remaining: int, items: str) -> str:
    from bot.utils.dates import today_tashkent

    if due is None:
        tail = "muddatsiz"
    elif due < today_tashkent():
        tail = f"⏰ muddati o'tgan ({format_date(due)})"
    else:
        tail = f"{format_date(due)} gacha"
    return f"• {format_date(debt_date)} · {items} — {money(remaining)} ({tail})"


def items_short(items: list[tuple[str, int, int, str | None]]) -> str:
    return ", ".join(f"{n} ×{q}" if q > 1 else n for n, q, _p, _note in items) or "qarz"


# ---- debt flow
DEBT_ASK_CATEGORY: Final = "Qaysi tovar? Tanlang 👇"
DEBT_ASK_QTY: Final = "Nechta? Tugmani bosing yoki raqam yozing."
DEBT_BAD_QTY: Final = "Sonni tushunmadim. Raqam bilan yozing, masalan: 2"
DEBT_ASK_PRICE: Final = "Bittasining narxi qancha? Masalan: 175 ming"
DEBT_PRICE_UNCLEAR: Final = (
    "Narxni tushunmadim. Yana bir aytib bering, masalan: 175 ming yoki 175000"
)
DEBT_ASK_NOTE: Final = "Rangi yoki o'lchami bormi? Yo'q bo'lsa, «⏭ O'tkazib yuborish» ni bosing."
BTN_ADD_ITEM: Final = "➕ Yana tovar"
BTN_ITEMS_DONE: Final = "✅ Tayyor"
DEBT_ASK_DUE: Final = "Qarz muddati qachon?"
BTN_DUE_1W: Final = "📅 1 hafta"
BTN_DUE_2W: Final = "📅 2 hafta"
BTN_DUE_1M: Final = "📅 1 oy"
BTN_DUE_DATE: Final = "🗓 Sanani yozish"
BTN_DUE_NONE: Final = "♾ Muddatsiz"
DEBT_ASK_DUE_DATE: Final = "Sanani yozing, masalan: 25.12 yoki 25-dekabr"
DEBT_BAD_DUE: Final = "Sanani tushunmadim yoki u o'tib ketgan. Masalan: 25.12 yoki 25-dekabr"
DEBT_NO_CUSTOMER_STATE: Final = "Boshidan boshlaymiz. Menyudan «➕ Qarz» ni bosing."


def price_assumed(amount: int) -> str:
    return f"Tushundim: {money(amount)}. Noto'g'ri bo'lsa, «❌ Bekor qilish» ni bosing."


def items_summary(rows: list[tuple[str, int, int, str | None]]) -> str:
    lines = []
    for name, qty, price, note in rows:
        extra = f" ({note})" if note else ""
        lines.append(f"• {name}{extra}: {qty} × {money(price)} = {money(qty * price)}")
    return "\n".join(lines)


def debt_card(
    customer: str,
    groups: list[tuple[str, list[tuple[str, int, int, str | None]], int]],
    due: date | None,
    total_debt_after: dict[str, int],
) -> str:
    lines = ["➕ Qarz yozish", f"👤 {customer}"]
    for code, rows, subtotal in groups:
        lines += [
            "",
            f"📂 Bo'lim: {SECTION_NAMES[code]}",
            items_summary(rows),
            f"Jami: {money(subtotal)}",
        ]
    lines += ["", f"📅 Muddat: {format_date(due)}" if due else "📅 Muddatsiz"]
    after = ", ".join(f"{SECTION_NAMES[c]} {money(v)}" for c, v in total_debt_after.items())
    lines += [f"Qarzi keyin: {after}", "", "To'g'rimi?"]
    return "\n".join(lines)


def debt_saved(customer: str) -> str:
    return f"✅ Qarz saqlandi: {customer}."


# ---- payment flow
PAY_NO_DEBT: Final = "Bu mijozning qarzi yo'q ✅"
PAY_ASK_SECTION: Final = "Qaysi bo'lim qarzidan?"
PAY_ASK_AMOUNT: Final = "Qancha berdi? Masalan: 100 ming"
WO_ASK_AMOUNT: Final = "Qancha summani kechamiz? Masalan: 50 ming"
BTN_WO_ALL: Final = "🤝 Hammasini kechish"
BTN_PICK_DEBT: Final = "📋 Qarzni tanlash"
BTN_FIFO: Final = "↩️ Eng eskisidan"
PAY_PICK_DEBT: Final = "Qaysi qarzdan ayiramiz?"
PAY_AMOUNT_UNCLEAR: Final = "Summani tushunmadim. Yana bir aytib bering, masalan: 100 ming"
DUE_PASSED: Final = "Tanlangan muddat o'tib ketdi. Iltimos, qarzni qaytadan yozing."
PAY_CHANGED: Final = (
    "Hisob yangilandi, shuning uchun yozuv saqlanmadi. Iltimos, to'lovni qaytadan yozing."
)


def overpay(name: str, owed: int, amount: int) -> str:
    return f"{name}ning qarzi {money(owed)}. Siz {money(amount)} yozdingiz — bu qarzdan ko'p. Summani qayta yozing, iltimos."


def payment_card(
    customer: str,
    section: str,
    kind: str,
    amount: int,
    lines: list[tuple[date, int, str]],
    owed_before: int,
    owed_after: int,
) -> str:
    title = "💵 To'lov" if kind == "payment" else "🤝 Qarzdan kechish"
    out = [
        title,
        f"👤 {customer}",
        f"📂 Bo'lim: {SECTION_NAMES[section]}",
        f"Summa: {money(amount)}",
        "",
        "Qarzlardan ayiriladi:",
    ]
    out += [f"• {format_date(d)} · {item}: −{money(a)}" for d, a, item in lines]
    out += ["", f"Qarz: {money(owed_before)} → {money(owed_after)}", "", "To'g'rimi?"]
    return "\n".join(out)


def payment_saved(customer: str, kind: str) -> str:
    what = "To'lov" if kind == "payment" else "Kechish"
    return f"✅ {what} saqlandi: {customer}."


# ---- cancel recent
BTN_RECENT: Final = "🚫 Yozuvni bekor qilish"
RECENT_EMPTY: Final = "Hozircha yozuvlar yo'q."
RECENT_HEADER: Final = "Oxirgi yozuvlar. Bekor qilmoqchi bo'lganingizni tanlang 👇"
CANCEL_HAS_PAYMENTS: Final = (
    "Bu qarzga to'lov yozilgan, shuning uchun avval to'lovni bekor qilish kerak."
)
CANCEL_ALREADY: Final = "Bu yozuv allaqachon bekor qilingan."
KIND_NAMES: Final = {"debt": "Qarz", "payment": "To'lov", "write_off": "Kechish"}


def recent_button(kind: str, name: str, amount: int, when: date) -> str:
    return f"{KIND_NAMES[kind]} · {name} · {money(amount)} · {format_date(when)}"


def cancel_card(kind: str, name: str, amount: int, when: date) -> str:
    return (
        f"↩️ Bekor qilamizmi?\n\n{KIND_NAMES[kind]}: {name}\nSumma: {money(amount)}\nSana: {format_date(when)}\n\n"
        "Yozuv o'chmaydi — «bekor qilingan» deb tarixda qoladi."
    )


def cancelled_ok(kind: str, name: str) -> str:
    return f"✅ Bekor qilindi: {KIND_NAMES[kind].lower()} · {name}."


# ---- delete / restore customer
def delete_card(name: str, balances: dict[str, int]) -> str:
    out = [f"🗑 {name} mijozlar ro'yxatidan o'chirilsinmi?"]
    if balances:
        owed = ", ".join(f"{SECTION_NAMES[c]} {money(v)}" for c, v in balances.items())
        out += [
            "",
            f"⚠️ Qarzi bor: {owed}.",
            "Avval qarzni yopgan ma'qul. O'chirsangiz ham qarz hisobda saqlanadi.",
        ]
    out += ["", "Mijoz butunlay yo'qolmaydi, admin uni qaytara oladi."]
    return "\n".join(out)


def customer_deleted(name: str) -> str:
    return f"✅ {name} o'chirildi."


BTN_ADMIN_DELETED: Final = "♻️ O'chirilgan mijozlar"
DELETED_EMPTY: Final = "O'chirilgan mijozlar yo'q."
DELETED_HEADER: Final = "O'chirilgan mijozlar. Qaytarmoqchi bo'lganingizni tanlang 👇"
RESTORE_PHONE_TAKEN: Final = "Qaytarib bo'lmaydi: bu raqam endi boshqa mijozda."


def customer_restored(name: str) -> str:
    return f"✅ {name} qaytarildi."


# ---- notifications
def customer_debt_notice(
    name: str, section: str, rows: str, total: int, due: date | None, owed: int
) -> str:
    due_txt = f"\n📅 Muddat: {format_date(due)}" if due else ""
    return (
        f"Assalomu alaykum, {name} 🌸\n\n"
        f"{SECTION_NAMES[section]} bo'limidan nasiya yozildi:\n{rows}\n"
        f"Jami: {money(total)}{due_txt}\n\n"
        f"Hozir {SECTION_NAMES[section]} bo'yicha qarzingiz: {money(owed)}.\n"
        "Xaridingiz uchun rahmat!"
    )


def customer_payment_notice(name: str, section: str, amount: int, left: int) -> str:
    tail = f"Qolgan qarz: {money(left)}." if left else "Qarzingiz to'liq yopildi 🎉"
    return f"{name}, {SECTION_NAMES[section]} bo'limi bo'yicha {money(amount)} to'lovingiz qabul qilindi ✅\n{tail}\nRahmat!"


def customer_writeoff_notice(name: str, section: str, amount: int, left: int) -> str:
    tail = f"Qolgan qarz: {money(left)}." if left else "Qarzingiz to'liq yopildi."
    return (
        f"{name}, {SECTION_NAMES[section]} bo'limi bo'yicha qarzingizdan {money(amount)} "
        f"hisobdan chiqarildi 🤝\n{tail}\nRahmat!"
    )


def customer_correction_notice(name: str, what: str) -> str:
    return (
        f"{name}, avvalgi xabarimizda adashibmiz: {what} hisobdan olib tashlandi.\n"
        "Hisobingiz yangilandi. Noqulaylik uchun uzr so'raymiz 🙏"
    )


def owner_notice(actor: str, what: str, customer: str, amount: int) -> str:
    return f"🔔 {actor} sizning bo'limingizga {what}: {customer}, {money(amount)}."


def owner_cancel_notice(actor: str, what: str, customer: str, amount: int) -> str:
    return f"🔔 {actor} sizning bo'limingizdagi yozuvni bekor qildi ({what}): {customer}, {money(amount)}."


# ---- customer: "Mening qarzim"
def my_debt(sections: list[tuple[str, int, list[str], list[str]]]) -> str:
    """sections: (code, balance, debt lines, recent payment lines)."""
    out: list[str] = []
    for code, balance, debts, pays in sections:
        out += [f"💰 {SECTION_NAMES[code]}", f"Qoldiq: {money(balance)}", ""]
        out += debts[:MAX_DEBT_LINES]
        if len(debts) > MAX_DEBT_LINES:
            out.append(more_debts(len(debts) - MAX_DEBT_LINES))
        if pays:
            out += ["", "So'nggi to'lovlar:", *pays]
        out.append("")
    return "\n".join(out).strip()


def my_payment_line(paid_on: date, kind: str, amount: int) -> str:
    mark = "to'lov" if kind == "payment" else "kechildi"
    return f"• {format_date(paid_on)} — {money(amount)} ({mark})"


def result_line(
    i: int,
    name: str,
    form: str,
    note: str | None,
    phone: str | None,
    balance: int,
    last: date | None,
) -> str:
    head = f"{i}. {name} {form}" + (f" — {note}" if note else "")
    phone_txt = format_phone(phone) if phone else "⚠️ telefon kerak"
    debt_txt = money(balance) if balance else "qarz yo'q"
    last_txt = f" · oxirgi xarid: {format_date(last)}" if last else ""
    return f"{head}\n   📞 {phone_txt} · 💰 {debt_txt}{last_txt}"


def restore_card() -> str:
    return "♻️ Mijozni qaytaramizmi?\n\nU yana qidiruvda chiqadi."


NO_DEBT_FOR: Final = "{who}: qarzi yo'q ✅"


def no_debt_for(who: str) -> str:
    return NO_DEBT_FOR.format(who=who)


def debt_start(who: str) -> str:
    return f"👤 {who}\n\n{DEBT_ASK_CATEGORY}"


def pay_header(who: str, owed: int) -> str:
    return f"👤 {who} — qarzi: {money(owed)}\n\n"


def items_total(rows: list[tuple[str, int, int, str | None]], total: int) -> str:
    return f"{items_summary(rows)}\n\nJami: {money(total)}"


def more_debts(n: int) -> str:
    return f"… yana {n} ta qarz"


# ============================================================ Stage 3: AI agent (staff)
AI_NOT_CONFIGURED: Final = "AI hali sozlanmagan. Hozircha pastdagi tugmalardan foydalaning 👇"
AI_DOWN: Final = (
    "Hozir tinglay olmayapman, kechirasiz 🙏 Pastdagi tugmalar orqali ishlashingiz mumkin, "
    "men tez orada tuzalaman."
)
AI_VOICE_TOO_LONG: Final = (
    "Ovozli xabar juda uzun. Iltimos, qisqaroq qilib yuboring (1,5 daqiqagacha)."
)
AI_SLOW_DOWN: Final = "Biroz sekinroq, iltimos 🙏 Bir daqiqadan keyin yana yuboring."
AI_NOT_UNDERSTOOD: Final = "Tushunmadim. Yana bir aytib bering, iltimos."
AI_LISTENING: Final = "🎧 Tinglayapman…"
AI_CHOICE_EXPIRED: Final = "Bu savol eskirdi. Iltimos, qaytadan ayting."
AI_NO_DEBT_ITEM: Final = "Bu mijozning bunday tovardan qarzi yo'q."
AI_SECTION_QUESTION: Final = "Qaysi bo'lim qarzidan?"
AI_DEBT_QUESTION: Final = "Qaysi qarzdan ayiramiz?"
AI_DUE_QUESTION: Final = "Qarz muddati qachon?"
AI_WHO_QUESTION: Final = "Qaysi mijoz haqida? Ismini ayting."
AI_NOTHING_TO_CANCEL: Final = "Bekor qiladigan yozuv topilmadi."
AI_NO_DEBTORS: Final = "Hozir qarzdor yo'q ✅"
AI_NO_OVERDUE: Final = "Muddati o'tgan qarz yo'q ✅"
AI_NO_RESULTS: Final = "Hech kim topilmadi."


def ai_customer_question(query: str) -> str:
    return f"«{query}» degan bir nechta mijoz bor. Qaysi biri?"


def ai_customer_missing(query: str) -> str:
    return f"«{query}» degan mijoz topilmadi. 🔍 Qidirish orqali tekshiring yoki ➕ Yangi mijoz qo'shing."


def ai_item_question(item: str) -> str:
    return f"«{item}» qaysi tovar turiga kiradi?"


def ai_price_question(item: str) -> str:
    return f"«{item}» narxini tushunmadim. Bittasi necha so'm? Masalan: 175 ming."


def ai_amount_question() -> str:
    return "Summani tushunmadim. Qancha? Masalan: 100 ming."


def ai_due_question() -> str:
    return "Muddatni tushunmadim. Masalan: 2 hafta, 25-dekabr yoki muddatsiz."


def ai_phone_question() -> str:
    return "Telefon raqamini tushunmadim. 9 ta raqam ayting, masalan: 90 123 45 67."


def ai_debtors(rows: list[tuple[str, str, int, date | None]], totals: dict[str, int]) -> str:
    """rows: (who, section code, owed, next due)."""
    lines = ["💰 Qarzdorlar", ""]
    for i, (who, code, owed, due) in enumerate(rows[:20], 1):
        due_txt = f", muddat {format_date(due)}" if due else ""
        lines.append(f"{i}. {who} — {SECTION_NAMES[code]}: {money(owed)}{due_txt}")
    if len(rows) > 20:
        lines.append(more_debts(len(rows) - 20))
    lines.append("")
    lines += [f"Jami {SECTION_NAMES[c]}: {money(v)}" for c, v in totals.items()]
    return "\n".join(lines)


def ai_overdue(rows: list[tuple[str, str, int, int]]) -> str:
    """rows: (who, section code, remaining, days overdue)."""
    lines = ["⏰ Muddati o'tganlar", ""]
    for i, (who, code, rem, days) in enumerate(rows[:20], 1):
        lines.append(f"{i}. {who} — {SECTION_NAMES[code]}: {money(rem)} ({days} kun o'tgan)")
    if len(rows) > 20:
        lines.append(more_debts(len(rows) - 20))
    return "\n".join(lines)


def ai_down_alert(error: str) -> str:
    return f"⚠️ AI vaqtincha ishlamayapti ({error}). Xodimlar tugmalar bilan ishlayapti."


BTN_YES: Final = "✅ Ha"
BTN_NO: Final = "❌ Yo'q"
AI_ABORTED: Final = "Xo'p. Mijozning to'liq ismini ayting yoki 🔍 Qidirish tugmasidan foydalaning."


def ai_customer_confirm(who: str) -> str:
    return f"Shu odamni nazarda tutdingizmi: {who}?"


def ai_assumed_thousands(raw: str, value: int) -> str:
    return (
        f"⚠️ «{raw}» ni {money(value)} deb tushundim. Noto'g'ri bo'lsa, ❌ Bekor qilish ni bosing."
    )


def ai_all_or_amount(spoken: str) -> str:
    return f"Hammasini kechamizmi yoki faqat {spoken}ni?"


def ai_skipped(n: int) -> str:
    return f"ℹ️ Qolgan {n} ta ishni hali bajarmadim — avval yuqoridagini tasdiqlang yoki javob bering, keyin qayta ayting."


def cancel_card_by(kind: str, name: str, amount: int, when: date, by: str, at: str) -> str:
    return (
        f"↩️ Bekor qilamizmi?\n\n{KIND_NAMES[kind]}: {name}\nSumma: {money(amount)}\n"
        f"Sana: {format_date(when)}, soat {at}\nYozgan: {by}\n\n"
        "Yozuv o'chmaydi — «bekor qilingan» deb tarixda qoladi."
    )
