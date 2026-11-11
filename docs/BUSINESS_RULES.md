# Business Rules

> **Status:** PARTIALLY APPROVED (2026-11-11). `✅ Decision:` — settled by Faxriddin; the remaining ❓ questions will be asked before the relevant phase.
> Source: `NARGIZA_BREND_MASTER_PROMPT.md`, sections 2–7 and 13.
> Every rule is numbered (`BR-xxx`) — code, tests and reviews refer to rules by this number.
> `❓ Q-n` — a question not yet resolved (see the list at the end). A rule without an answer is not implemented in code.
> `💡` — not in the master prompt; a rule proposed by Claude. Please confirm or change it.
> `✅` — answered/decided by the owner.
>
> **Note on forms of address:** *opa* (elder sister) and *aka* (elder brother) are respectful forms of address placed after a first name, used much like "Ms." / "Mr." (e.g. "Nodira opa", "Botir aka").

---

## 1. Shop information

- **BR-001** Name: Nargiza Brend. Address: Sherbaraka bazaar, shop no. 82. Opening hours: 07:00–18:00. Phone: +998 95 511 17 00. Instagram: @nargiza_17_00_.
- **BR-002** Time zone — `Asia/Tashkent`. "Today", "this month" and all other periods are based on Tashkent time (a day starts at 00:00). Times are stored in the DB as `timestamptz`.
- **BR-003** ✅ There is no day off — the shop is open every day (this remains changeable in settings). Map location and shop photo/logo — entered by the admin in settings. ❓ Q-3
- **BR-004** All money is in whole so'm. No tiyin, no fractions.

## 2. Users and roles

- **BR-010** Roles: `admin`, `staff`, `customer`.
- **BR-011** Everyone who opens the bot automatically becomes a `customer`.
- **BR-012** Only the admin grants and revokes the `staff` role. The bot never makes anyone staff on its own.
  ✅ Decision: the admin adds a staff member inside the bot by **phone number** (with name, form of address and section ownership). When that person presses /start and shares their number (with the BR-152 check), they automatically become `staff`. If they have already registered — immediately.
- **BR-012a** ✅ If a staff member's number is shared from a different (new) Telegram account, it is not switched over automatically: the admin receives an [Tasdiqlash] [Rad etish] (*[Approve] [Reject]*) request; until approved, the account remains a `customer`. A blocked staff member's number is not re-linked.
- **BR-013** The first admin is identified by `ADMIN_PHONES` (phone) in `.env`: whoever owns that number becomes `admin` when they share it. `ADMIN_TELEGRAM_IDS` is also supported (fallback path).
- **BR-014** The admin sees and can change all users, their count, their phone numbers and all data. The admin has every capability a staff member has. Admin-only: assigning/removing staff, blocking staff, bot settings, restoring deleted records.
- **BR-015** A blocked staff member (e.g. if their phone is lost) immediately loses the ability to perform any action — 💡 starting from their next message.
- **BR-016a** Admin panel: bot status, errors, restart. Updating the bot (new code) — only via deployment to the server, not from inside the bot.
- **BR-016** System messages (backups, errors, AI spend, integrity checks) go to the admin only.
- **BR-017** Staff work fully in both sections: read, write, edit, add/delete customers, announcements — without asking the admin.
- **BR-018** A customer sees only their own data. This is enforced in code, by Telegram ID. No AI for customers — buttons only.
- **BR-019** Forms of address for staff: Faxriddin aka, Botir aka, Nodira opa, Nilufar opa. For customers: "<Name> opa" / "<Name> aka".
- **BR-019a** Staff may write in Cyrillic or Latin script; bot replies are in Latin script (later, Cyrillic via a user setting).

## 3. Sections and routing

- **BR-020** Two sections: `shop` ("Do'kon" = Shop; owners: Botir aka, Nodira opa) and `lingerie` ("Ichki kiyim" = Underwear; owner: Nilufar opa).
- **BR-021** A record's section is determined by the **product category**, not by who reported it.
- **BR-022** If one message contains products from both sections — two separate records, on a single confirmation card.
- **BR-023** If the section is unclear (product category unknown) — the bot asks: "Qaysi bo'lim: Do'konmi yoki Ichki kiyimmi?" (*"Which section: Shop or Underwear?"*). It does not guess.
- **BR-024** The section is always shown on the confirmation card, along with a [Bo'limni almashtirish] (*[Change section]*) button.
- **BR-025** Each section's money is kept separate. Reports always break figures down by section; a combined total appears only on a row explicitly labelled "both sections total".
- **BR-026** Section-owner notification: when someone (a staff member who is not an owner) records a sale, debt, payment, return or stock receipt in a section, that section's owners are notified immediately.
  Example: Nodira opa sells underwear → to Nilufar opa: "🔔 Nodira opa sizning bo'limingizga savdo qo'shdi: ichki kiyim, 80 000 so'm." (*"🔔 Nodira opa added a sale to your section: underwear, 80 000 so'm."*)
- **BR-027** Between owners of the same section (Botir aka ↔ Nodira opa) no notification is sent for each action — it appears in the evening report.
- **BR-028** 💡 BR-026 applies even when the admin (Faxriddin aka) records something (the admin owns no section). ❓ Q-7: should the admin also receive section notifications?

### 3.1. Product categories (initial list; editable by the admin)

| Section | Categories |
|---|---|
| shop | ko'ylak (dress), yubka (skirt), shim (trousers), kofta (cardigan/sweater), bluzka (blouse), kurtka/palto (jacket/coat), oyoq kiyim (footwear), sumka (bag), aksessuar (accessories) |
| lingerie | ichki kiyim (underwear) |
| shop | ✅ pijama (pyjamas), xalat (robe), kostyum (suit) |
| lingerie | ✅ paypoq (socks), kolgotka (tights) |

✅ Headscarves (ro'mol) are not sold — not added as a category.

- **BR-030** Each category has a list of synonyms (Latin and Cyrillic): e.g. "туфли", "tufli", "poyabzal", "krossovka" → oyoq kiyim. The admin fills in the synonyms.
- **BR-031** 💡 If a category is deactivated (`is_active=false`), old records are kept, but it cannot be chosen for new records.

## 4. Customers

- **BR-040** The phone number is the customer's unique key. It is normalised to the `+998XXXXXXXXX` format: "90 123 45 67", "901234567", "+998 90 123-45-67", "998901234567" → `+998901234567`.
- **BR-041** Phone numbers are not duplicated among non-deleted customers.
- **BR-042** A customer can be saved without a phone, but with `phone_missing=true` and a "⚠️ telefon kerak" (*"⚠️ phone needed"*) flag. They appear in the daily 08:00 list. ❓ Q-35: all customers without a phone (master 4.1), or only debtors without a phone (master 7)?
- **BR-043** Fields: name, phone, form of address (opa/aka), note ("Shahlo opaning qizi" — *"Shahlo opa's daughter"*), linked Telegram user.
- **BR-044** Search: Cyrillic↔Latin ("Умида" = "Umida"), fuzzy matching, partial phone number.
- **BR-045** If several customers match — a list: name + note, full phone (staff only), current debt (with section), last purchase and its date. Selection: buttons [1][2][3] or text/voice ("birinchisi" — *"the first one"*, "Shahlo opaning qizi" — *"Shahlo opa's daughter"*, "45 67 dagisi" — *"the one ending 45 67"*). If more than 5 — [Yana ko'rsatish] (*[Show more]*) or ask for the last digits of the phone. [➕ Yangi mijoz] (*[➕ New customer]*) is always present.
- **BR-046** Staff can delete a customer. If the customer has a debt — the bot first warns and offers to close the debt. Deletion = soft delete; the admin can restore. ❓ Q-8: may a customer with debt be deleted without closing the debt?
- **BR-047** ✅ Everyone who registers becomes a customer. If their phone matches an existing (non-deleted) customer record, they are linked to that record and can see their debts; if not, a new customer record is created. "💰 Mening qarzim" (*"💰 My debt"*) when there is no debt: "Sizda qarz yo'q" (*"You have no debt"*). No separate notification is sent to staff on linking (the number of new customers appears in the 20:00 report).
  💡 Exception (security): if the notebook's customer record is already linked to **another** Telegram account (the number may have passed to someone else) — it is not moved automatically; the admin receives a [✅ Tasdiqlash] (*[✅ Approve]*) request; until approved: "Ma'lumotlaringiz tekshirilmoqda" (*"Your details are being verified"*).

## 5. Debt notebook

- **BR-050** Debt: customer (required), section, products (category + note + quantity + price), amount, date, due date, who recorded it.
- **BR-051** The words "qarz", "nasiya" (*"debt", "on credit"*) → a debt record.
- **BR-052** ✅ If no due date is given, the bot asks while recording: "Muddati qachon?" (*"When is it due?"*); the answer "muddatsiz" (*"no due date"*) is also accepted. Debts without a due date appear every day in the 08:00 list under "📅 Muddati belgilanmagan qarzlar" (*"📅 Debts with no due date"*) with a [📅 Muddat belgilash] (*[📅 Set due date]*) button. Due-date reminders (BR-161…163) are not sent for debts without a due date.
- **BR-053** 💡 A regular debt's amount = sum of products (quantity × price). Exception: the linked debt in a mixed sale (BR-071) — its amount is the unpaid remainder, and the products live on the sale record. Amount > 0.
- **BR-054** When a debt is recorded, the customer is automatically messaged (if registered in the bot): what they took, amount, due date, total debt.
- **BR-055** The balance is not stored. It is always computed: `debts − payments − write-offs ± adjustments` (excluding deleted and cancelled records).
- **BR-056** The balance is computed separately for each section.
- **BR-057** When someone says "Qarzini o'chir/yop" (*"Delete/close their debt"*), the bot asks: [💵 To'ladi] (*[💵 Paid]*) [🤝 Kechib yuborildi] (*[🤝 Forgiven]*) [❌ Bekor] (*[❌ Cancel]*).
  - "To'ladi" (*Paid*) = a payment (money came into the till).
  - "Kechib yuborildi" (*Forgiven*) = a write-off (shown separately in reports as a loss).
  - These two types are never mixed. ✅ Decision: any staff member and the admin can forgive a debt (with confirmation; the audit log records who did it).

## 6. Payments

- **BR-060** "Umida 100 ming berdi" (*"Umida paid 100k"*) → a payment.
- **BR-061** By default, allocation is FIFO — the oldest debt is closed first. 💡 Debts with the same timestamp — in ID order (stable). ✅ Decision: "oldest" = by debt date (for imported debts — the original date from the notebook).
- **BR-062** If the staff member names a specific debt ("oyoq kiyim qarzidan ayir" — *"take it off the footwear debt"*) — it is applied to that debt.
- **BR-063** The confirmation card shows how much is being closed from which debt(s).
- **BR-064** Partial payments are allowed.
- **BR-065** ✅ If a payment exceeds the balance — it is rejected. The bot shows the balance and asks for the amount to be corrected: "Umida opaning qarzi 250 000 so'm. 300 000 dan ko'p — summani tekshirib bering." (*"Umida opa's debt is 250 000 so'm. 300 000 is more than that — please check the amount."*)
- **BR-066** ✅ If the customer has debt in both sections and no section is specified — the bot asks: "Qaysi bo'lim qarzidan?" (*"From which section's debt?"*) (showing each section's balance). It does not guess.
- **BR-067** Card numbers and receipt submission — `ENABLE_CARD_PAYMENTS=false`. The code is ready but does not appear in menus or reminders.

## 7. Sales

- **BR-070** "sotildi" (*"sold"*) → a cash sale. Customer name is optional.
- **BR-071** Mixed sale: "Ko'ylak 500 ming, 200 berdi, qolgani qarz" (*"Dress 500k, paid 200, the rest on debt"*) → sale 500 000 + linked debt 300 000, on a single card. 💡 In a mixed sale the customer is required (for the debt).
  ❓ Q-10: in a mixed sale 200 000 went into the till. Should the report show "sales" as 500 000 (the product price) and "cash received" separately as 200 000? (Proposal: yes — sale 500 000, cash received 200 000, on debt 300 000; if the debt is paid later — recorded as a payment.)
- **BR-072** If the payment type is unclear: "Naqd sotildimi yoki nasiyagami?" (*"Sold for cash or on credit?"*)
- **BR-073** Discount: "500 minglik ko'ylakni 450 ga sotdim" (*"I sold the 500k dress for 450"*) → sale 450 000; the 50 000 discount is stored in a separate field (master: "in the note"; 💡 a separate field — so it can be totalled in reports). Monthly report shows total discounts.
- **BR-074** A sale automatically reduces stock. ✅ Goods given on credit (as debt) are also deducted from stock.
- **BR-075** Cost price and profit are not calculated.

## 8. Returns and exchanges

- **BR-080** The bot finds the original record; if there are several — it asks the user to choose.
- **BR-081** The card shows: old product, new product, difference, debt/sale "before → after".
- **BR-082** If a product taken on debt is exchanged — the debt changes by the difference (💡 via an adjustment record; the original debt is not modified. Adjustments table — to be designed with the architect in phase 1).
- **BR-083** If a cash sale is exchanged — the bot asks whether the customer pays the difference or is refunded it.
- **BR-077** 💡 Amount limits: an amount below 10 000 so'm or above 1 000 000 000 so'm — the bot asks (it may have been misspoken). "1.500 mln" (separator or decimal?), "350-400 ming" (a range), "500 ming 450" — the bot asks.
- **BR-076** ✅ A small number with no unit (< 1000, e.g. "350") is taken as thousands (350 000 so'm), shown explicitly on the card. A unitless number between 1000 and 9999 ("1500") — the bot asks.
- **BR-084** Return only: if taken on debt — deducted from the debt; if cash — the sale is reversed (a return record). Stock increases.
  ❓ Q-11: if part of the debt has already been paid and the product is returned (e.g. debt 300 000, 200 000 paid, a 300 000 product returned) — is the customer refunded 100 000 in cash?
- **BR-085** Cross-section exchange (ko'ylak → ichki kiyim) — the amount leaves one section and enters the other; the relevant section owner is notified (BR-026).
- **BR-086** The original record is not deleted — it moves to the `returned` status. Returns are shown separately in reports.
- **BR-087** ❓ Q-12: is there a time limit on returns (e.g. 14 days)?

## 9. Stock (level 1)

- **BR-090** Stock is tracked only by product category (ko'ylak: 45 pcs). Size, colour, model — as a note; not asked for if not mentioned.
- **BR-091** Stock receipt: "20 ta yubka keldi" (*"20 skirts arrived"*) or a photo of the delivery note → a receipt record (with confirmation).
- **BR-092** Sale → stock decreases; return → stock increases.
- **BR-093** If stock goes negative — 💡 the record is saved, but with a warning: "Yubka qoldig'i −2, kirim yozilmagan bo'lishi mumkin" (*"Skirt stock is −2, a receipt may not have been recorded"*).
- **BR-094** Low-stock warning; the threshold is set per category. ❓ Q-13
- **BR-095** Opening stock is entered once. ❓ Q-14
- **BR-096** Monthly stocktake: the counted quantity is entered; the difference is stored as an adjustment record.

## 10. Confirmation and cancellation (all records)

- **BR-100** Every action that writes to the database first shows a confirmation card: [✅ Tasdiqlash] (*[✅ Confirm]*) [✏️ Tuzatish] (*[✏️ Edit]*) [❌ Bekor qilish] (*[❌ Cancel]*).
- **BR-101** Queries (reads) run immediately, without confirmation.
- **BR-102** Idempotency: even if a button is pressed twice, the record is written only once.
- **BR-103** ✅ A confirmation card is valid for 30 minutes (configurable in settings). After that: "Bu karta eskirdi, qaytadan ayting" (*"This card has expired, please say it again"*). Only the staff member who received the card can confirm it.
- **BR-104** "Oxirgi yozuvni bekor qil" (*"Cancel the last record"*) — with confirmation; the record is not deleted, it moves to the `cancelled` status and stays in the history. ❓ Q-16: can a staff member cancel only records they wrote themselves? Is there a time limit?
- **BR-105** Each business action is a single transaction: either everything is written or nothing is.
- **BR-106** Every write, edit and deletion goes into the audit log (who, when, old value, new value).

## 11. Ongoing conversation (staff)

- **BR-110** The bot remembers the last customer/record discussed ("unga yana 20 ming qo'sh" — *"add another 20k to her"*).
- **BR-111** The context resets after a period of silence (e.g. 15 minutes, configurable) or when a different customer is mentioned.

## 12. Queries and reports

- **BR-120** Debtors list: amount, due date, sorted largest to smallest; total (by section).
- **BR-121** Customer debt: balance, purchases, payments, due date, phone.
- **BR-122** Overdue debts: with the number of days overdue.
- **BR-123** Sales report by period (today, this week, this month, this year, last month, "mart" (*"March"*), "1–15 noyabr" (*"1–15 November"*)): total amount, number of items, sections shown separately.
  ❓ Q-17: does "this week" start on Monday?
  ❓ Q-18: if someone says "mart" (March) and it is currently November — should it be taken as March of the current year (already past)?
- **BR-124** Sales by category: quantity and amount.
- **BR-125** Debt statistics: total debt; debt issued and repaid in the period; who paid.
- **BR-126** Stock: stock per category; low-stock items.
- **BR-127** Comparison: two periods side by side, difference (so'm) and percentage.
- **BR-128** Any report, if requested as Excel — a .xlsx file is sent.
- **BR-129** Long lists are paginated. Yearly report — from the day the bot went live.
- **BR-130** Report categories: sales, returns, discounts, payments, forgiven debts — each separate, never mixed.

## 13. Migrating the old notebook

- **BR-140** A staff member turns on "Eski daftarni kiritish" (*"Enter old notebook"*) mode and sends voice messages or photos of pages.
- **BR-141** Result: ✅ clear, ⚠️ no phone, ❓ unreadable/unclear. Unclear entries are not guessed.
- **BR-142** Only the outstanding debt is entered, with its original date (`source=import`).
- **BR-143** [✅ Hammasini saqlash] (*[✅ Save all]*) [✏️ Tuzatish] (*[✏️ Edit]*) — editing is per row.
- **BR-144** Duplicate check by phone. ❓ Q-19: how is the section determined for imported debts if the notebook does not record the product category? (Is the notebook kept separately per section?)

## 14. Customer side

- **BR-150** /start → welcome message (with a photo, if uploaded) + [📝 Ro'yxatdan o'tish] (*[📝 Register]*).
- **BR-151** Registration: name (Telegram name offered as a button) → form of address [Opa]/[Aka] → phone (only via the "share contact" button) → consent text → "✅ Rahmat, Umida opa! Siz ro'yxatdan o'tdingiz." (*"✅ Thank you, Umida opa! You are registered."*)
- **BR-152** Security: the `user_id` of the shared contact must equal the sender's ID. Otherwise it is rejected.
- **BR-153** Consent text is mandatory: "Raqamingiz faqat do'kon xabarlari va xaridlaringiz hisobi uchun saqlanadi." (*"Your number is stored only for shop messages and for keeping track of your purchases."*)
- **BR-154** Customer menu: [💰 Mening qarzim] (*[💰 My debt]*) [📢 E'lonlar] (*[📢 Announcements]*) [🏪 Do'kon haqida] (*[🏪 About the shop]*) [📞 Bog'lanish] (*[📞 Contact]*); in settings: [🔕 Reklamani o'chirish] (*[🔕 Turn off promotions]*).
- **BR-154a** "Do'kon haqida" (*"About the shop"*): address, location (if set), opening hours, phone, Instagram, photo (if set).
- **BR-155** "Mening qarzim" (*"My debt"*): sections shown separately — balance, what was taken, payments, due date.

### 14.1. Automatic messages to customers

- **BR-160** When a debt is recorded — immediately (BR-054).
- **BR-161** 2 days before the due date — "due date approaching".
- **BR-162** On the due date — "today is payment day".
- **BR-163** After the due date, every 3 days, at most 5 times — a polite reminder.
- **BR-164** Debt reminders are delivered even if promotions are turned off.
- **BR-165** The bot can only message people who have pressed /start; the rest go on the 08:00 call list.
- **BR-166** Every reminder is written to `reminders_log` — no duplicates.
- **BR-167** ❓ Q-20: at what time are reminders sent (proposal: 10:00)? Should they also be sent on a day off?
- **BR-168** ❓ Q-21: if a customer has debt in both sections — should it be sent as one message (sections on separate lines)?

## 15. Announcements

- **BR-170** Any staff member can send an announcement: text and/or photo.
- **BR-171** Recipients: everyone / debtors / overdue debtors / one selected person.
- **BR-172** Preview: "87 kishiga boradi" (*"Will go to 87 people"*) → [Yuborish] (*[Send]*) [Bekor] (*[Cancel]*).
- **BR-173** Result: "82 tasiga yetdi, 5 tasi botni bloklagan" (*"Delivered to 82, 5 have blocked the bot"*).
- **BR-174** Promotional announcements are not sent to those who turned off promotions; personal messages and debt reminders are.
- **BR-175** A general announcement never shows anyone's debt.
- **BR-176** Messages are sent in a queue within Telegram's rate limits (limits to be verified against the official documentation in phase 7).
- **BR-177** Recommendation to staff: 1–2 promotions per week.
- **BR-178** ❓ Q-22: is an announcement to "debtors" / "overdue debtors" considered promotional (i.e. is it withheld from those who turned off promotions)?

## 16. Scheduled tasks (Asia/Tashkent)

| Rule | Time | Recipient | Task |
|---|---|---|---|
| BR-180 | Daily 08:00 | Staff | Call list: overdue debtors (amount, tappable phone) + debtors without a phone + debts with no due date (BR-052). No day off — every day |
| BR-181 | Daily 20:00 | Staff | Daily report: sections separately, product categories, returns, discounts, payments, number of new customers + "compare with the cash in the till" |
| BR-182 | Daily | Customers | Due-date reminders (BR-161…163) |
| BR-183 | Hourly | — | Backup (kept for 48 hours) |
| BR-184 | Daily 03:00 | Admin | Daily backup + encrypted file to Telegram (30 days) |
| BR-185 | Nightly | Admin | Integrity check |
| BR-186 | Weekly | Admin | Debts Excel file + backup restore test |
| BR-187 | Monthly | Staff | Monthly report, stocktake reminder |

- **BR-188** ❓ Q-23: should the 20:00 report also be sent on a day off? On which day and at what time do the weekly/monthly tasks run (proposal: weekly — Monday 09:00, monthly — 1st of the month 09:00)?

---

## ❓ Open questions

| # | Question | Rule |
|---|---|---|
| Q-1 | **✅ shop** — Which section do pijama (pyjamas) and xalat (robe) belong to? Is the category list correct; should anything be added (e.g. kostyum, scarf/ro'mol, paypoq, kolgotka)? | 3.1 |
| Q-2 | **✅ no day off** — Which day is the day off (or is there none)? | BR-003 |
| Q-3 | Is there a map location and a shop photo/logo? | BR-003 |
| Q-4 | **✅ BR-052** — If no due date is given for a debt — what is the default number of days? Can a debt have no due date? | BR-052 |
| Q-5 | **✅ rejected** — Overpayment: reject it or keep it as an advance? | BR-065 |
| Q-6 | **✅ the bot asks** — If there is debt in both sections, how is a payment with no section specified allocated? | BR-066 |
| Q-7 | Should the admin also receive section notifications (🔔)? | BR-028 |
| Q-8 | **✅ yes, allowed** — Can a customer with debt be deleted without closing the debt? | BR-046 |
| Q-9 | **✅ any staff member** — Forgiving a debt — any staff member, or only the admin? | BR-057 |
| Q-10 | How does a mixed sale appear in reports (sale 500 000 / cash 200 000 / debt 300 000)? | BR-071 |
| Q-11 | If a product on a partially paid debt is returned, is the excess refunded to the customer? | BR-084 |
| Q-12 | Is there a time limit on returns? | BR-087 |
| Q-13 | "Low stock" threshold for each category | BR-094 |
| Q-14 | Opening stock (per category) | BR-095 |
| Q-15 | **✅ 30 minutes** — After how many minutes does a confirmation card expire? | BR-103 |
| Q-16 | "Cancel the last record" — own records only? Is there a time limit? | BR-104 |
| Q-17 | Does "this week" start on Monday? | BR-123 |
| Q-18 | "Mart" (March) — take it as the past March of the current year? | BR-123 |
| Q-19 | How is the section determined when importing the old notebook? | BR-144 |
| Q-20 | Time of customer reminders, and whether they are sent on a day off | BR-167 |
| Q-21 | Debt in both sections — in a single reminder? | BR-168 |
| Q-22 | Is an announcement to debtors considered promotional? | BR-178 |
| Q-23 | 20:00 report on a day off; timing of weekly/monthly tasks | BR-188 |
| Q-24 | Is a Google Drive backup needed? | DATA_SAFETY |
| Q-25 | When, and which, production server? | DEPLOY |
| Q-26 | **✅ deducted from stock** — Does it appear in the sales report (e.g. a "sold on credit" row)? | BR-050, BR-074 |
| Q-27 | **✅ by debt date** — In FIFO, is "oldest" the recorded date or the due date? Is the original date used for imported debts? | BR-061 |
| Q-28 | Forgiveness: the whole balance or a partial amount? One debt or all debts in the section? | BR-057 |
| Q-29 | If one product is returned from a multi-product record (partial return) — do the rest stay as they are? | BR-084 |
| Q-30 | In a cross-section exchange, do payments already made against the old debt carry over to the new section's debt? | BR-085 |
| Q-31 | Can a debt also have a discount ("500 lik ko'ylakni 450 ga nasiyaga berdim" — *"I gave the 500 dress on credit for 450"*)? | BR-073 |
| Q-32 | Are reminders per debt or per customer? If the due date is extended, does the 5-reminder counter restart? | BR-163 |
| Q-33 | **✅ yes, it stays** — Does a deleted customer's debt remain in the "total debt" report? | BR-046, BR-055 |
| Q-34 | If a payment is cancelled or edited, how is the allocation recalculated? (Proposal: the old payment becomes `cancelled`, the new payment is allocated afresh) | BR-104 |
| Q-35 | In the 08:00 list — all customers without a phone, or only debtors without a phone? | BR-042 |
