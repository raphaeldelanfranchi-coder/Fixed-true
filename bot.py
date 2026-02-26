import os
import time
import requests
import asyncio
import threading
from flask import Flask
from telegram import Bot

# ==============================
# CONFIG
# ==============================

API_KEY = os.getenv("ODDS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BASE_URL = "https://api.the-odds-api.com/v4/sports/soccer/odds"
ALERT_THRESHOLD = 12  # % minimum drop

alerted_matches = set()
previous_data = {}

# ==============================
# TELEGRAM
# ==============================

async def send_alert(message):
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message)

# ==============================
# ANALYSE
# ==============================

def fetch_data():
    params = {
        "apiKey": API_KEY,
        "regions": "eu",
        "markets": "totals",
        "oddsFormat": "decimal"
    }
    response = requests.get(BASE_URL, params=params)
    return response.json()

def calculate_suspicion(var_price, books):
    score = 0

    if var_price >= 12:
        score += 40
    if var_price >= 15:
        score += 20
    if books <= 3:
        score += 20

    return min(score, 100)

async def analyze():
    while True:
        matches = fetch_data()

        for match in matches:
            league = match["sport_title"]
            home = match["home_team"]
            away = match["away_team"]
            books_count = len(match["bookmakers"])

            for book in match["bookmakers"]:
                for market in book["markets"]:
                    if market["key"] == "totals":
                        for outcome in market["outcomes"]:
                            if outcome["name"] == "Over":
                                price = outcome["price"]
                                key = f"{home}_{away}"

                                if key in previous_data:
                                    old_price = previous_data[key]
                                    variation = ((old_price - price) / old_price) * 100
                                    suspicion = calculate_suspicion(variation, books_count)

                                    if variation >= ALERT_THRESHOLD and key not in alerted_matches:
                                        message = f"""
⚽ {league}
🏟 {home} vs {away}

📉 Drop: {variation:.2f}% ({old_price} → {price})
📊 Books actifs: {books_count}

🚨 Suspicion Score: {suspicion}/100
"""
                                        await send_alert(message)
                                        alerted_matches.add(key)

                                previous_data[key] = price

        await asyncio.sleep(120)

# ==============================
# FLASK SERVER (pour Render)
# ==============================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_bot():
    asyncio.run(analyze())

if __name__ == "__main__":
    # Lancer bot en arrière-plan
    threading.Thread(target=run_bot).start()

    # Ouvrir port pour Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)