"""Tool schemas (Pydantic v2). The model only *requests* these; code validates and executes them.

Rules baked into the schemas (master §8.4):
- the model never converts numbers: amounts, prices, dates and phones are passed as the user said them
  (`*_text`) and parsed by our own strict parsers;
- the model never invents a customer id: it passes the name/phone words, code resolves them;
- when anything is unclear the model must call `ask` instead of guessing.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from bot.ai.base import ToolSpec

Section = Literal["shop", "lingerie"]


class _Args(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class ItemArg(_Args):
    item: Annotated[
        str,
        Field(
            min_length=1,
            max_length=60,
            description="Tovar turi, aytilganidek (masalan: ko'ylak, tufli, ichki kiyim)",
        ),
    ]
    quantity: Annotated[int, Field(ge=1, le=1000, description="Nechta. Aytilmasa 1")] = 1
    unit_price_text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=40,
            description="BITTASINING narxi, aytilganidek, o'zgartirmasdan (masalan: '350 ming', 'uch yuz ellik ming')",
        ),
    ]
    note: Annotated[
        str | None, Field(max_length=80, description="Rang, o'lcham, model — faqat aytilgan bo'lsa")
    ] = None


class AddDebt(_Args):
    customer_query: Annotated[
        str | None,
        Field(
            max_length=60,
            description="Mijoz ismi yoki telefon oxiri. 'unga' desa va oxirgi mijoz berilgan bo'lsa — o'sha ism",
        ),
    ] = None
    items: Annotated[list[ItemArg], Field(min_length=1, max_length=30)]
    due_text: Annotated[
        str | None,
        Field(
            max_length=30,
            description="Muddat aytilganidek ('2 hafta', '25-dekabr', 'muddatsiz'). Aytilmagan bo'lsa BO'SH QOLDIRING",
        ),
    ] = None
    heard: Annotated[
        str | None,
        Field(max_length=300, description="Xodim aytganining aniq matni (ovozda — transkripsiya)"),
    ] = None


class AddPayment(_Args):
    customer_query: Annotated[str | None, Field(max_length=60)] = None
    amount_text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=40,
            description="Summa aytilganidek, o'zgartirmasdan ('100 ming', 'yarim million')",
        ),
    ]
    section: Annotated[Section | None, Field(description="Faqat xodim aniq aytgan bo'lsa")] = None
    item: Annotated[
        str | None,
        Field(
            max_length=60,
            description="Xodim aniq qarzni aytsa: 'oyoq kiyim qarzidan ayir' → 'oyoq kiyim'",
        ),
    ] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class WriteOff(_Args):
    customer_query: Annotated[str | None, Field(max_length=60)] = None
    amount_text: Annotated[
        str | None,
        Field(
            max_length=40,
            description="Kechiladigan summa; hammasi bo'lsa bo'sh qoldiring va all=true",
        ),
    ] = None
    all: Annotated[bool, Field(description="Butun qoldiqni kechish")] = False
    section: Annotated[Section | None, Field()] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class AddSale(_Args):
    customer_query: Annotated[
        str | None,
        Field(
            max_length=60, description="Mijoz — faqat aytilgan bo'lsa. Mijozsiz naqd savdoda BO'SH"
        ),
    ] = None
    items: Annotated[list[ItemArg], Field(min_length=1, max_length=30)]
    total_text: Annotated[
        str | None,
        Field(
            max_length=40,
            description="Kelishilgan YAKUNIY narx butun savdo uchun, aytilganidek ('500 minglik ko'ylakni 450 ga sotdim' → '450'). Chegirma aytilmasa BO'SH",
        ),
    ] = None
    paid_text: Annotated[
        str | None,
        Field(
            max_length=40,
            description="Hozir qancha pul berdi ('200 berdi'). To'liq naqd bo'lsa BO'SH; qolgani nasiya bo'lsa shu yerga to'langan qismini yoz",
        ),
    ] = None
    due_text: Annotated[
        str | None,
        Field(max_length=30, description="Nasiya qismi uchun muddat; aytilmagan bo'lsa BO'SH"),
    ] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class AddStockIn(_Args):
    item: Annotated[str, Field(min_length=1, max_length=60, description="Tovar turi")]
    quantity: Annotated[int, Field(ge=1, le=100000, description="Nechta keldi")]
    heard: Annotated[str | None, Field(max_length=300)] = None


class CountItem(_Args):
    item: Annotated[str, Field(min_length=1, max_length=60)]
    counted: Annotated[
        int, Field(ge=0, le=100000, description="Sanalgan (omborda haqiqatda bor) soni")
    ]


class StockCount(_Args):
    counts: Annotated[
        list[CountItem],
        Field(min_length=1, max_length=30, description="Sanoq: «ko'ylak 45 ta, yubka 30 ta»"),
    ]
    heard: Annotated[str | None, Field(max_length=300)] = None


class GetStock(_Args):
    item: Annotated[
        str | None, Field(max_length=60, description="Aniq tur so'ralsa; hammasi bo'lsa BO'SH")
    ] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class ListLowStock(_Args):
    heard: Annotated[str | None, Field(max_length=300)] = None


class RegisterReturn(_Args):
    customer_query: Annotated[
        str | None, Field(max_length=60, description="Kim qaytardi (aytilgan bo'lsa)")
    ] = None
    item: Annotated[
        str,
        Field(
            min_length=1,
            max_length=60,
            description="QAYTARILGAN tovar turi ('ko'ylakni qaytardi' → 'ko'ylak')",
        ),
    ]
    quantity: Annotated[
        int | None, Field(ge=1, le=1000, description="Nechta qaytardi. Aytilmagan bo'lsa BO'SH")
    ] = None
    new_items: Annotated[
        list[ItemArg] | None,
        Field(
            max_length=30,
            description="ALMASHTIRISH: o'rniga olingan yangi tovar(lar) ('o'rniga oyoq kiyim oldi'). Faqat qaytarish bo'lsa BO'SH",
        ),
    ] = None
    total_text: Annotated[
        str | None,
        Field(
            max_length=40,
            description="Yangi tovar uchun kelishilgan yakuniy narx (chegirma bo'lsa)",
        ),
    ] = None
    paid_text: Annotated[
        str | None,
        Field(
            max_length=40,
            description="Yangi tovarga hozir qancha pul berdi; to'liq naqd bo'lsa BO'SH",
        ),
    ] = None
    due_text: Annotated[
        str | None, Field(max_length=30, description="Yangi tovarning nasiya qismi muddati")
    ] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class CreateCustomer(_Args):
    name: Annotated[str, Field(min_length=2, max_length=40)]
    form: Annotated[Literal["opa", "aka"], Field(description="Murojaat: ayol — opa, erkak — aka")]
    phone_text: Annotated[str | None, Field(max_length=30, description="Telefon aytilganidek")] = (
        None
    )
    note: Annotated[
        str | None, Field(max_length=80, description="Masalan: 'Shahlo opaning qizi'")
    ] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class DeleteCustomer(_Args):
    customer_query: Annotated[str | None, Field(max_length=60)] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class CancelLast(_Args):
    customer_query: Annotated[
        str | None,
        Field(max_length=60, description="Qaysi mijozniki. Aytilmasa — eng oxirgi yozuv"),
    ] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class GetCustomerDebt(_Args):
    customer_query: Annotated[str | None, Field(max_length=60)] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class SearchCustomer(_Args):
    query: Annotated[str, Field(min_length=1, max_length=60)]
    heard: Annotated[str | None, Field(max_length=300)] = None


class ListDebtors(_Args):
    section: Annotated[Section | None, Field()] = None
    heard: Annotated[str | None, Field(max_length=300)] = None


class ListOverdue(_Args):
    heard: Annotated[str | None, Field(max_length=300)] = None


class Ask(_Args):
    question: Annotated[
        str,
        Field(
            min_length=3, max_length=300, description="Xodimga bitta aniq savol, oddiy o'zbekcha"
        ),
    ]
    heard: Annotated[str | None, Field(max_length=300)] = None


class Say(_Args):
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=400,
            description="Qisqa javob: salomlashish yoki botda yo'q narsa haqida",
        ),
    ]
    heard: Annotated[str | None, Field(max_length=300)] = None


# name → (model, description, writes)
REGISTRY: dict[str, tuple[type[_Args], str, bool]] = {
    "add_debt": (
        AddDebt,
        "Mijozga qarz (nasiya) yozish. Faqat 'qarz' yoki 'nasiya' deyilganda.",
        True,
    ),
    "add_payment": (AddPayment, "Mijoz pul berdi (to'lov). 'berdi', 'to'ladi', 'tushdi'.", True),
    "write_off": (
        WriteOff,
        "Qarzni kechish (pul tushmagan, hisobdan chiqarish). 'kechdim', 'kechib yubordim'.",
        True,
    ),
    "add_sale": (
        AddSale,
        "Naqd yoki aralash savdo: 'sotildi', 'sotdim'. Nasiyaga (hech narsa to'lanmagan) bo'lsa add_debt.",
        True,
    ),
    "add_stock_in": (AddStockIn, "Omborga kirim: 'keldi', '20 ta yubka keldi'.", True),
    "stock_count": (
        StockCount,
        "Ombor sanog'i yoki boshlang'ich qoldiq: 'ko'ylak 45 ta, yubka 30 ta'.",
        True,
    ),
    "get_stock": (GetStock, "Omborda nechta qoldi.", False),
    "list_low_stock": (ListLowStock, "Nima kam qoldi.", False),
    "register_return": (
        RegisterReturn,
        "Tovar qaytarildi yoki almashtirildi: 'qaytardi', 'o'rniga ... oldi'.",
        True,
    ),
    "create_customer": (CreateCustomer, "Yangi mijoz qo'shish.", True),
    "delete_customer": (DeleteCustomer, "Mijozni ro'yxatdan o'chirish.", True),
    "cancel_last_entry": (CancelLast, "Oxirgi yozuvni bekor qilish.", True),
    "get_customer_debt": (GetCustomerDebt, "Mijozning qarzi qancha, nima olgan, muddati.", False),
    "search_customer": (SearchCustomer, "Mijozni qidirish.", False),
    "list_debtors": (ListDebtors, "Kimlarning qarzi bor, jami qarz.", False),
    "list_overdue": (ListOverdue, "Muddati o'tgan qarzlar kimda.", False),
    "ask": (
        Ask,
        "Tushunmagan yoki yetishmayotgan narsani so'rash. HECH QACHON taxmin qilmang — so'rang.",
        False,
    ),
    "say": (
        Say,
        "Qisqa javob: salom, rahmat, yoki bot qila olmaydigan narsa (savdo, ombor, hisobot — keyingi bosqichlarda).",
        False,
    ),
}


def _inline(schema: dict[str, Any], defs: dict[str, Any]) -> Any:
    """Resolve $ref, drop titles and collapse Optional → plain type (vendor-neutral, simple JSON schema)."""
    if isinstance(schema, dict):
        if "$ref" in schema:
            return _inline(defs[schema["$ref"].split("/")[-1]], defs)
        if "anyOf" in schema:
            branches = [b for b in schema["anyOf"] if b.get("type") != "null"]
            merged = {k: v for k, v in schema.items() if k != "anyOf"}
            return _inline({**merged, **branches[0]}, defs) if branches else merged
        return {
            k: _inline(v, defs)
            for k, v in schema.items()
            if k not in {"title", "$defs", "default", "additionalProperties"}
        }
    if isinstance(schema, list):
        return [_inline(v, defs) for v in schema]
    return schema


def tool_specs() -> list[ToolSpec]:
    specs = []
    for name, (model, desc, _writes) in REGISTRY.items():
        raw = model.model_json_schema()
        specs.append(ToolSpec(name, desc, _inline(raw, raw.get("$defs", {}))))
    return specs


class UnknownToolError(Exception):
    pass


def validate(name: str, args: dict[str, Any]) -> _Args:
    """Code, not the model, decides whether the arguments are acceptable."""
    if name not in REGISTRY:
        raise UnknownToolError(name)
    return REGISTRY[name][0].model_validate(args)
