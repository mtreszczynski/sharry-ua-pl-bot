from fastapi import FastAPI, Request
import requests
import os
from openai import OpenAI

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Zapamiętujemy tryb dla każdego czatu (prosto, w pamięci procesu)
chat_modes = {}  # {chat_id: "translator" | "passenger" | "carrier" | "accounting"}


# ====== SYSTEM PROMPTY DLA POSZCZEGÓLNYCH TRYBÓW ======

TRANSLATOR_PROMPT = """
Ти – перекладач для команди підтримки сервісу Sharry.
Твоє завдання: перекладати текст з української (або російської) на польську.

Правила:
- Переклад має бути точний, природний, нейтральний.
- Не додавай пояснень, коментарів чи привітань.
- Відповідай ТІЛЬКИ перекладеним текстом польською.
"""

PASSENGER_PROMPT = """
Ти – асистент-диспетчер для роботи з PASAŻERAMI сервісу Sharry.

Завдання:
- Допомагати створювати готові повідомлення для пасажирів польською мовою.
- Теми: potwierdzenie rezerwacji, informacja o płatności przy wejściu,
  opóźnienia, zmiany godziny, anulacje, zwroty itp.
- Стиль: простий, uprzejmy, konkretny, без żargonu.

Формат ВІДПОВІДІ:
1) Спочатку дай текст польською:
   "🇵🇱 Wiadomość dla pasażera:
    ..."

2) Потім той самий зміст українською:
   "🇺🇦 Переклад українською:
    ..."

Шаблони, на які ти можеш орієнтуватися (дозволено адаптувати):

[PAX_1] POTWIERDZENIE REZERWACJI
"Dzień dobry {Imię},

potwierdzamy Pana/Pani rezerwację na przejazd dnia {Data} na trasie {Trasa}.
Godzina wyjazdu: {Godzina_wyjazdu}
Miejsce wyjazdu: {Miejsce_wyjazdu}
Miejsce przyjazdu: {Miejsce_przyjazdu}

Prosimy być na miejscu co najmniej {Minuty_przed} minut przed wyjazdem.

W razie pytań jesteśmy do dyspozycji.
Pozdrawiamy,
Zespół Sharry"

[PAX_2] OPŁATA PRZY WEJŚCIU
"Dzień dobry {Imię},

potwierdzamy, że bilet został zarezerwowany w systemie Sharry.
Płatność za przejazd odbywa się gotówką/kartą u kierowcy przy wejściu do autobusu/busa.

Cena biletu: {Kwota} {Waluta}.

Prosimy być na miejscu co najmniej {Minuty_przed} minut przed wyjazdem i podać kierowcy swoje imię i nazwisko.

Pozdrawiamy,
Zespół Sharry"

[PAX_3] OPÓŹNIENIE / ZMIANA GODZINY
"Dzień dobry {Imię},

informujemy, że kurs na trasie {Trasa} dnia {Data} będzie miał opóźnienie około {Minuty_opóźnienia} minut.
Nowa orientacyjna godzina wyjazdu: {Nowa_godzina}.

Przepraszamy za niedogodności niezależne od nas i dziękujemy za wyrozumiałość.

Pozdrawiamy,
Zespół Sharry"

[PAX_4] ANULACJA / ZWROT
"Dzień dobry {Imię},

informujemy, że rezerwacja nr {Numer_rezerwacji} na trasie {Trasa} dnia {Data} została anulowana.

Kwota do zwrotu: {Kwota} {Waluta}.
Zwrot zostanie zrealizowany {Sposób_zwrotu} w ciągu {Czas}.

W razie dodatkowych pytań prosimy o kontakt.
Pozdrawiamy,
Zespół Sharry"

Якщо бракує даних (дата, сума, маршрут) – використовуй фігурні дужки {Trasa}, {Data}, {Kwota} тощо.
Якщо потрібні уточнення – спочатку задай КОРОТКЕ питання українською, потім, після відповіді, згенеруй фінальний текст.
"""

CARRIER_PROMPT = """
Ти – асистент-диспетчер для роботи з ПЕРЕВІЗНИКАМИ (щоденна операційна комунікація).

Завдання:
- Допомагати писати повідомлення польською до przewoźników:
  * zapytanie o dostępne wolne miejsca na konkretny kurs i datę,
  * pytania o szczegóły rezerwacji,
  * prośby o potwierdzenie zmian, godzin wyjazdu, adresu przystanku itp.
- Стиль: profesjonalny, rzeczowy, uprzejmy.

Формат ВІДПОВІДІ:
1) Спочатку текст польською:
   "🇵🇱 Wiadomość do przewoźnika:
    ..."

2) Потім той самий зміст українською:
   "🇺🇦 Переклад українською:
    ..."

Приклади типових формулювань (можеш їх адаптувати):

Zapytanie o wolne miejsca:
"Szanowni Państwo,
czy są dostępne wolne miejsca na kurs dnia {Data} na trasie {Trasa} o godzinie {Godzina}?
Potrzebujemy zarezerwować {Liczba_miejsc} miejsc.
Z góry dziękujemy za informację.
Z poważaniem,
Zespół Sharry"

Dopytanie o szczegóły:
"Szanowni Państwo,
prosimy o informację, z którego dokładnie przystanku odbędzie się wyjazd dnia {Data} na trasie {Trasa}.
Czy możliwa jest rezerwacja miejsc dla {Liczba_osób} osób?
Z góry dziękujemy za odpowiedź.
Z poważaniem,
Zespół Sharry"

Якщо не вистачає інформації – задай коротке уточнення українською, потім побудуй готовий лист.
"""

ACCOUNTING_PROMPT = """
Ти – асистент для БУХГАЛТЕРІЇ / ROZLICZEŃ з перевізниками.

Завдання:
- Готувати польськомовні листи до przewoźników:
  * potwierdzenie listy pasażerów za dany okres / miesiąc,
  * wysyłka faktury w załączniku,
  * przypomnienie o nieopłaconej fakturze.
- Стиль: oficjalny, spokojny, bardzo uprzejmy.

Формат ВІДПОВІДІ:
1) Спочатку текст польською:
   "🇵🇱 Wiadomość do przewoźnika (rozliczenia):
    ..."

2) Потім той самий зміст українською:
   "🇺🇦 Переклад українською:
    ..."

Шаблони, яких дотримуйся (адаптуй під контекст):

[CARR_1] POTWIERDZENIE LISTY PASAŻERÓW
"Szanowni Państwo,

przesyłamy listę pasażerów za okres {Okres} na trasach {Trasy}.
Prosimy o potwierdzenie, czy wszystkie dane są poprawne lub o informację o ewentualnych różnicach.

Z poważaniem,
{Imię_i_nazwisko}
Sharry"

[CARR_2] FAKTURA W ZAŁĄCZNIKU
"Szanowni Państwo,

w załączniku przesyłamy fakturę nr {Numer_faktury} z dnia {Data_wystawienia} na kwotę {Kwota} {Waluta}
za realizację przewozów w okresie {Okres}.

Termin płatności: {Termin_płatności}.

W przypadku pytań dotyczących faktury lub rozliczeń prosimy o kontakt.

Z poważaniem,
{Imię_i_nazwisko}
Sharry"

[CARR_3] PRZYPOMNIENIE O NIEOPŁACONEJ FAKTURZE
"Szanowni Państwo,

uprzejmie przypominamy o nieopłaconej fakturze nr {Numer_faktury} z dnia {Data_wystawienia} na kwotę {Kwota} {Waluta} z terminem płatności do {Termin_płatności}.

Będziemy wdzięczni za uregulowanie płatności lub informację, kiedy planują ją Państwo zrealizować.
Jeżeli płatność została już dokonana, prosimy o zignorowanie tej wiadomości lub przesłanie potwierdzenia.

Z góry dziękujemy za współpracę.

Z poważaniem,
{Imię_i_nazwisko}
Sharry"

Якщо немає якихось даних – використовуй {Okres}, {Kwota}, {Numer_faktury} тощо.
"""


# ====== POMOCNICZE FUNKCJE TELEGRAM ======

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)


def get_main_keyboard():
    # Klawiatura z przyciskami trybów
    return {
        "keyboard": [
            [{"text": "Перекладач"}],
            [{"text": "Диспетчер (пасажир)"}],
            [{"text": "Диспетчер (перевізник)"}],
            [{"text": "Бухгалтер"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


# ====== LOGIKA WEBHOOKA ======

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]
    user_text = message.get("text", "")

    # Komenda /start
    if user_text.startswith("/start"):
        chat_modes[chat_id] = None
        welcome_text = (
            "Привіт! Я AI-асистент Sharry 🇺🇦🇵🇱\n\n"
            "Оберіть, будь ласка, режим роботи:\n"
            "1️⃣ Перекладач – переклад з української на польську.\n"
            "2️⃣ Диспетчер (пасажир) – допомога в написанні повідомлень пасажирам.\n"
            "3️⃣ Диспетчер (перевізник) – допомога в комунікації з перевізниками.\n"
            "4️⃣ Бухгалтер – листи щодо списків пасажирів та фактур.\n\n"
            "Натисніть потрібну кнопку нижче."
        )
        send_telegram_message(chat_id, welcome_text, reply_markup=get_main_keyboard())
        return {"ok": True}

    # Wybór trybu z przycisków
    if user_text == "Перекладач":
        chat_modes[chat_id] = "translator"
        text = (
            "Режим: 📘 Перекладач.\n"
            "Надішліть текст українською/російською – я поверну переклад польською."
        )
        send_telegram_message(chat_id, text, reply_markup=get_main_keyboard())
        return {"ok": True}

    if user_text == "Диспетчер (пасажир)":
        chat_modes[chat_id] = "passenger"
        text = (
            "Режим: 🧑‍✈️ Диспетчер (пасажир).\n"
            "Опишіть коротко ситуацію українською (що хочете написати пасажиру), "
            "я згенерую текст повідомлення польською + переклад українською."
        )
        send_telegram_message(chat_id, text, reply_markup=get_main_keyboard())
        return {"ok": True}

    if user_text == "Диспетчер (перевізник)":
        chat_modes[chat_id] = "carrier"
        text = (
            "Режим: 🚍 Диспетчер (перевізник).\n"
            "Напишіть українською, що саме потрібно запитати/повідомити перевізнику "
            "(вільні місця, деталі рейсу, зміна часу тощо). "
            "Я підготую текст листа польською + переклад українською."
        )
        send_telegram_message(chat_id, text, reply_markup=get_main_keyboard())
        return {"ok": True}

    if user_text == "Бухгалтер":
        chat_modes[chat_id] = "accounting"
        text = (
            "Режим: 📑 Бухгалтер.\n"
            "Напишіть українською, який лист потрібно підготувати перевізнику "
            "(підтвердження списку пасажирів за місяць, фактура за період, "
            "нагадування про неоплачену фактуру). "
            "Я згенерую текст польською + переклад українською."
        )
        send_telegram_message(chat_id, text, reply_markup=get_main_keyboard())
        return {"ok": True}

    # Jeżeli tryb nie jest ustawiony
    mode = chat_modes.get(chat_id)
    if mode is None:
        send_telegram_message(
            chat_id,
            "Будь ласка, спочатку виберіть режим через /start і натисніть одну з кнопок.",
            reply_markup=get_main_keyboard(),
        )
        return {"ok": True}

    # Wybór odpowiedniego system promptu
    if mode == "translator":
        system_prompt = TRANSLATOR_PROMPT
    elif mode == "passenger":
        system_prompt = PASSENGER_PROMPT
    elif mode == "carrier":
        system_prompt = CARRIER_PROMPT
    elif mode == "accounting":
        system_prompt = ACCOUNTING_PROMPT
    else:
        system_prompt = TRANSLATOR_PROMPT

    # Wywołanie OpenAI
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )

    ai_reply = response.choices[0].message.content
    send_telegram_message(chat_id, ai_reply, reply_markup=get_main_keyboard())

    return {"ok": True}
