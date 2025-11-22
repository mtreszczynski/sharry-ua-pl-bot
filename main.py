from fastapi import FastAPI, Request
import requests
import os
from openai import OpenAI

app = FastAPI()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Ти – AI-асистент для команди підтримки сервісу Sharry, який допомагає україномовним співробітникам спілкуватися з польськомовними пасажирами та перевізниками.

Твої задачі:
1) Перекладати між польською та українською.
2) Давати готові відповіді польською у бізнесовому, ввічливому стилі.
3) Скорочувати довгі повідомлення та пропонувати варіанти відповідей.
4) Не вигадуй даних про бронювання.

Формат:
- Якщо написано “переклади” → даєш переклад.
- Якщо написано “запропонуй відповідь” → даєш відповідь польською.
- Пиши чітко і коротко.
"""

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    if "message" not in data:
        return {"ok": True}

    chat_id = data["message"]["chat"]["id"]
    user_text = data["message"].get("text", "")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ]
    )

    ai_reply = response.choices[0].message.content
    send_telegram_message(chat_id, ai_reply)

    return {"ok": True}
