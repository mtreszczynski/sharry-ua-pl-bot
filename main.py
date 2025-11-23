from fastapi import FastAPI, Request
import requests
import os
from openai import OpenAI

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# ====== PROSTE "PAMIĘTANIE" TRYBU NA CZAT ======
# chat_id -> "translator" / "passenger" / "carrier" / "accounting"
CHAT_MODES = {}

BUTTONS = {
    "translator": "1️⃣ Tryb tłumacza",
    "passenger": "2️⃣ Asystent pasażera",
    "carrier": "3️⃣ Asystent przewoźnika",
    "accounting": "4️⃣ Asystent księgowości",
}

BASE_SYSTEM_PROMPT = """
Ти – AI-асистент для команди підтримки сервісу Sharry (онлайн-сервіс бронювання наземного транспорту в Європі).
Твої основні користувачі – україномовні співробітники, які спілкуються з польськомовними пасажирами та перевізниками.

Загальні правила:
- Пиши грамотно.
- Не вигадуй деталей про бронювання, рейси, суми, дати або фактури.
- Якщо немає конкретних даних – використовуй змінні у фігурних дужках, наприклад {Data}, {Trasa}, {Kwota}, {Numer_faktury}.
- Не пояснюй, що ти AI, просто давай готові тексти.

Шаблони для пасажирів (по-польськи, але можна адаптувати під ситуацію):

[PAX_1] POTWIERDZENIE REZERWACJI:
"Dzień dobry {Imię},

potwierdzamy Pana/Pani rezerwację na przejazd dnia {Data} na trasie {Trasa}.
Godzina wyjazdu: {Godzina_wyjazdu}
Miejsce wyjazdu: {Miejsce_wyjazdu}
Miejsce przyjazdu: {Miejsce_przyjazdu}

Prosimy być na miejscu co najmniej {Minuty_przed} minut przed wyjazdem.

W razie pytań jesteśmy do dyspozycji.
Pozdrawiamy,
Zespół Sharry"

[PAX_2] INFORMACJA O OPŁACIE PRZY WEJŚCIU:
"Dzień dobry {Imię},

potwierdzamy, że bilet został zarezerwowany w systemie Sharry.
Płatność za przejazd odbywa się gotówką/kartą u kierowcy przy wejściu do autobusu/busa.

Cena biletu: {Kwota} {Waluta}.

Prosimy być na miejscu co najmniej {Minuty_przed} minut przed wyjazdem i podać kierowcy swoje imię i nazwisko.

Pozdrawiamy,
Zespół Sharry"

[PAX_3] INFORMACJA O OPÓŹNIENIU:
"Dzień dobry {Imię},

informujemy, że kurs na trasie {Trasa} dnia {Data} będzie miał opóźnienie około {Minuty_opóźnienia} minut.
Nowa orientacyjna godzina wyjazdu: {Nowa_godzina}.

Przepraszamy za niedogodności niezależne od nas i dziękujemy za wyrozumiałość.

Pozdrawiamy,
Zespół Sharry"

[PAX_4] INFORMACJA O ZWROCIE / ANULACJI:
"Dzień dobry {Imię},

informujemy, że rezerwacja nr {Numer_rezerwacji} na trasie {Trasa} dnia {Data} została anulowana.

Kwota do zwrotu: {Kwota} {Waluta}.
Zwrot zostanie zrealizowany {Sposób_zwrotu} w ciągu {Czas}.

W razie dodatkowych pytań prosimy o kontakt.
Pozdrawiamy,
Zespół Sharry"

Шаблони для перевізників / księgowości (по-польськи):

[CARR_1] POTWIERDZENIE LISTY PASAŻERÓW:
"Szanowni Państwo,

przesyłamy listę pasażerów na kurs dnia {Data} na trasie {Trasa}.
Godzina wyjazdu: {Godzina_wyjazdu}.

Prosimy o potwierdzenie otrzymania listy oraz informację, czy wszystkie dane są poprawne.

W razie pytań jesteśmy do dyspozycji.

Z poważaniem,
{Imię_i_nazwisko}
Sharry"

[CARR_2] ZAPYTANIE O WOLNE MIEJSCA:
"Szanowni Państwo,

chciałbym zapytać o dostępność wolnych miejsc na trasie {Trasa} dnia {Data}.
Interesuje nas liczba miejsc: {Liczba_miejsc} oraz ewentualne godziny wyjazdu.

Prosimy o informację, czy mogą Państwo przyjąć rezerwacje na ten termin oraz na jakich warunkach.

Z góry dziękujemy za odpowiedź.

Z poważaniem,
{Imię_i_nazwisko}
Sharry"

[CARR_3] FAKTURA – PRZYPOMNIENIE O NIEOPŁACONEJ PŁATNOŚCI:
"Szanowni Państwo,

uprzejmie przypominamy o nieopłaconej fakturze nr {Numer_faktury} z dnia {Data_wystawienia} na kwotę {Kwota} {Waluta} z terminem płatności do {Termin_płatności}.

Będziemy wdzięczni za uregulowanie płatności lub informację, kiedy planują ją Państwo zrealizować.
Jeżeli płatność została już dokonana, prosimy o zignorowanie tej wiadomości lub przesłanie potwierdzenia.

Z poważaniem,
{Imię_i_nazwisko}
Sharry"

[CARR_4] WIADOMOŚĆ Z ZAŁĄCZONĄ FAKTURĄ:
"Szanowni Państwo,

w załączniku przesyłamy fakturę nr {Numer_faktury} z dnia {Data_wystawienia} na kwotę {Kwota} {Waluta}
za realizację przewozów w okresie {Okres}.

Termin płatności: {Termin_płatności}.

W przypadku pytań dotyczących faktury lub rozliczeń prosimy o kontakt mailowy lub telefoniczny.

Z poważaniem,
{Imię_i_nazwisko}
Sharry"
"""

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

def send_menu(chat_id):
    keyboard = [
        [{"text": BUTTONS["translator"]}],
        [{"text": BUTTONS["passenger"]}],
        [{"text": BUTTONS["carrier"]}],
        [{"text": BUTTONS["accounting"]}],
    ]
    reply_markup = {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }
    text = (
        "Wybierz tryb pracy bota:\n"
        "1️⃣ Tryb tłumacza – wklejasz tekst po ukraińsku, bot zwraca sam tekst po polsku.\n"
        "2️⃣ Asystent pasażera – bot tworzy wiadomości do pasażerów (PL + UA).\n"
        "3️⃣ Asystent przewoźnika – bot tworzy wiadomości do przewoźników (PL + UA, np. o wolne miejsca).\n"
        "4️⃣ Asystent księgowości – bot pomaga w wiadomościach dot. list pasażerów i faktur (PL + UA)."
    )
    send_telegram_message(chat_id, text, reply_markup=reply_markup)

def build_mode_instruction(mode: str) -> str:
    if mode == "translator":
        return (
            "TRYB: TŁUMACZ.\n"
            "Otrzymujesz tekst głównie po ukraińsku lub rosyjsku.\n"
            "Masz zwrócić wyłącznie jego poprawne tłumaczenie na język polski.\n"
            "Bez ukraińskiej wersji, bez komentarzy, bez dodatkowych wyjaśnień."
        )
    if mode == "passenger":
        return (
            "TRYB: ASYSTENT PASAŻERA.\n"
            "Tworzysz wiadomości do pasażerów w oparciu o podane szablony i opis sytuacji.\n"
            "Zawsze zwracaj dwie wersje tej samej wiadomości:\n"
            "1) Najpierw po polsku (oznacz jako 'PL:').\n"
            "2) Potem po ukraińsku (oznacz jako 'UA:').\n"
            "Styl polski: uprzejmy, konkretny, krótki. Szanuj kontekst biletu/rezerwacji."
        )
    if mode == "carrier":
        return (
            "TRYB: ASYSTENT PRZEWOŹNIKA.\n"
            "Pomagasz pisać profesjonalne wiadomości po polsku do przewoźników, zwłaszcza:\n"
            "- zapytania o dostępne wolne miejsca na danej trasie/dniu,\n"
            "- dopytania o warunki rezerwacji, godziny, miejsca,\n"
            "- inne kwestie operacyjne.\n"
            "Zawsze zwracaj dwie wersje tej samej wiadomości:\n"
            "1) PL: – tekst po polsku,\n"
            "2) UA: – ten sam tekst przetłumaczony po ukraińsku.\n"
            "Styl polski: oficjalny, konkretny, z użyciem formy 'Państwo'."
        )
    if mode == "accounting":
        return (
            "TRYB: ASYSTENT KSIĘGOWOŚCI.\n"
            "Tworzysz wiadomości po polsku do przewoźników dotyczące rozliczeń:\n"
            "- potwierdzenie listy pasażerów za dany miesiąc lub okres,\n"
            "- wysyłka faktur w załączniku,\n"
            "- przypomnienia o zaległych płatnościach.\n"
            "Zawsze zwracaj dwie wersje tej samej wiadomości:\n"
            "1) PL: – tekst po polsku,\n"
            "2) UA: – ten sam tekst po ukraińsku.\n"
            "Styl polski: oficjalny, grzeczny, księgowy."
        )
    return (
        "Domyślny tryb – jeśli to możliwe, pomóż jak asystent pasażera (PL + UA)."
    )

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # Obsługa tylko zwykłych wiadomości tekstowych
    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    user_text = message.get("text", "") or ""

    # /start -> pokaż menu
    if user_text == "/start":
        CHAT_MODES.pop(chat_id, None)
        send_menu(chat_id)
        return {"ok": True}

    # Wybór trybu przez przyciski
    if user_text == BUTTONS["translator"]:
        CHAT_MODES[chat_id] = "translator"
        send_telegram_message(
            chat_id,
            "Wybrano: tryb tłumacza.\nWklej tekst po ukraińsku – bot zwróci sam tekst po polsku."
        )
        return {"ok": True}

    if user_text == BUTTONS["passenger"]:
        CHAT_MODES[chat_id] = "passenger"
        send_telegram_message(
            chat_id,
            "Wybrano: Asystent pasażera.\nOpisz sytuację lub wklej wiadomość pasażera, "
            "a bot przygotuje propozycję odpowiedzi (PL + UA)."
        )
        return {"ok": True}

    if user_text == BUTTONS["carrier"]:
        CHAT_MODES[chat_id] = "carrier"
        send_telegram_message(
            chat_id,
            "Wybrano: Asystent przewoźnika.\nNapisz, o co chcesz zapytać przewoźnika "
            "(np. wolne miejsca, godziny, warunki), a bot przygotuje wiadomość (PL + UA)."
        )
        return {"ok": True}

    if user_text == BUTTONS["accounting"]:
        CHAT_MODES[chat_id] = "accounting"
        send_telegram_message(
            chat_id,
            "Wybrano: Asystent księgowości.\nNapisz, jaką wiadomość chcesz wysłać przewoźnikowi "
            "w sprawie list pasażerów lub faktur, a bot przygotuje treść (PL + UA)."
        )
        return {"ok": True}

    # Jeśli tryb nie wybrany – przypomnienie + menu
    mode = CHAT_MODES.get(chat_id)
    if mode is None:
        send_telegram_message(
            chat_id,
            "Najpierw wybierz tryb pracy bota z menu poniżej (np. 1️⃣ 2️⃣ 3️⃣ 4️⃣)."
        )
        send_menu(chat_id)
        return {"ok": True}

    # ====== Zapytanie do OpenAI ======
    mode_instruction = build_mode_instruction(mode)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": BASE_SYSTEM_PROMPT},
            {"role": "system", "content": mode_instruction},
            {"role": "user", "content": user_text}
        ]
    )

    ai_reply = response.choices[0].message.content
    send_telegram_message(chat_id, ai_reply)

    return {"ok": True}
