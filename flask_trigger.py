import os
import json
import time
import base64
import requests
from flask import Flask, jsonify
import telegram
from telegram import ParseMode

# Flask app
app = Flask(__name__)

# ========= ENV VARIABLES =========
TOKEN = os.getenv("8525986458:AAEMJePRyoVrT-myhIuOp2uA1jYXdLUmX7w")               # Telegram Bot Token
CHAT_ID = int(os.getenv("-1001535659036"))      # Telegram CHAT_ID (group)
API_KEY = os.getenv("AIzaSyB7vBBbvK1HSZPzGt1cxLuU1d0lQaHnpTg")           # Gemini API Key
# =================================

# Файл історії цін
PRICE_HISTORY_FILE = "btc_history.json"


# ============================
# ФУНКЦІЇ ДЛЯ BTC ІСТОРІЇ
# ============================
def load_last_price():
    if os.path.exists(PRICE_HISTORY_FILE):
        try:
            with open(PRICE_HISTORY_FILE, "r") as f:
                data = json.load(f)
                return data.get("last_btc_usd", 0.0)
        except:
            os.remove(PRICE_HISTORY_FILE)
            return 0.0
    return 0.0


def save_current_price(price):
    try:
        with open(PRICE_HISTORY_FILE, "w") as f:
            json.dump({"last_btc_usd": price}, f)
        return True
    except:
        return False


# ============================
# ОТРИМАННЯ ЦІН
# ============================
def get_crypto_prices():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,solana,binancecoin,tether",
        "vs_currencies": "usd,uah",
    }

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, params=params, timeout=10, headers=headers)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("CoinGecko Error:", e)
        return None


# ============================
# AI ТЕКСТ
# ============================
def generate_ai_text_analysis(btc_usd, last_price, market_mood, price_change_percent, other_prices):

    is_first_run = market_mood.startswith("СИНІЙ")

    if is_first_run:
        prompt = f"""
        Створи привітальний пост для крипто-каналу.

        BTC: {btc_usd}
        Інші ціни: {other_prices}

        Напиши:
        Title: (до 10 слів, з емодзі)
        Conclusion: (2–3 речення)
        """
    else:
        prompt = f"""
        Зроби короткий аналітичний пост про ринок.

        Динаміка: {market_mood}
        BTC: {btc_usd}
        Вчора: {last_price}
        Зміна: {price_change_percent}%
        Інші: {other_prices}

        Формат:
        Title: ...
        Conclusion: ...
        """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]

        title = ""
        conclusion = ""

        for line in text.split("\n"):
            if line.startswith("Title:"):
                title = line.replace("Title:", "").strip()
            elif line.startswith("Conclusion:"):
                conclusion = line.replace("Conclusion:", "").strip()

        if not title:
            title = "🔥 Огляд крипторинку"
        if not conclusion:
            conclusion = "ШІ не зміг згенерувати висновок."

        return title, conclusion

    except Exception as e:
        print("AI TEXT ERROR:", e)
        return "🔥 Огляд ринку", "Помилка генерації тексту."


# ============================
# AI ЗОБРАЖЕННЯ
# ============================
def generate_ai_image(mood, change):
    prompt = f"Сгенеруй криптовалютне зображення у стилі неонового кіберпанку. Динаміка: {mood}, зміна {change}%."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-2.0:predict?key={API_KEY}"

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1}
    }

    try:
        r = requests.post(url, json=payload, timeout=40)
        r.raise_for_status()
        data = r.json()

        img_b64 = data["predictions"][0]["bytesBase64Encoded"]

        filename = "ai_image.png"
        with open(filename, "wb") as f:
            f.write(base64.b64decode(img_b64))

        return filename

    except Exception as e:
        print("IMAGE ERROR:", e)
        return None


# ============================
# АНАЛІЗ РИНКУ
# ============================
def get_market_analysis(btc_now, btc_old):

    if btc_old == 0:
        return "СИНІЙ (СТАРТ)", 0.0

    diff = btc_now - btc_old
    percent = (diff / btc_old) * 100

    if percent >= 0.5:
        mood = "ЗЕЛЕНИЙ (РІСТ)"
    elif percent <= -0.5:
        mood = "ЧЕРВОНИЙ (ПАДІННЯ)"
    else:
        mood = "ЖОВТИЙ (ФЛЕТ)"

    return mood, percent


# ============================
# ГОЛОВНА ФУНКЦІЯ
# ============================
def send_scheduled_post():

    bot = telegram.Bot(token=TOKEN)

    prices = get_crypto_prices()
    if prices is None:
        bot.send_message(chat_id=CHAT_ID, text="❌ Помилка отримання цін CoinGecko.")
        return "COINGECKO ERROR"

    btc = prices["bitcoin"]["usd"]

    last_price = load_last_price()
    mood, percent = get_market_analysis(btc, last_price)

    other_prices = {
        "ETH": prices["ethereum"]["usd"],
        "SOL": prices["solana"]["usd"],
        "BNB": prices["binancecoin"]["usd"]
    }

    title, conclusion = generate_ai_text_analysis(btc, last_price, mood, percent, other_prices)

    img = generate_ai_image(mood, percent)

    caption = f"""
{title}

💰 *Актуальні ціни:*
• BTC: ${btc}
• ETH: ${other_prices['ETH']}
• SOL: ${other_prices['SOL']}
• BNB: ${other_prices['BNB']}

{conclusion}

#крипто #аналіз
"""

    try:
        if img:
            with open(img, "rb") as f:
                bot.send_photo(chat_id=CHAT_ID, caption=caption, photo=f, parse_mode=ParseMode.MARKDOWN)
        else:
            bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        print("TELEGRAM ERROR:", e)

    save_current_price(btc)
    return "OK"


# ============================
# FLASK ROUTE
# ============================
@app.route("/send_crypto_post")
def trigger():
    res = send_scheduled_post()
    return jsonify({"status": res})
