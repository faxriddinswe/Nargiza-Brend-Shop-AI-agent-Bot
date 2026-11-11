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
