import os
import time
import requests
import asyncio
from telegram import Bot

API_KEY = os.getenv("ODDS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BASE_URL = "https://api.the-odds-api.com/v4/sports/soccer/odds"

ALERT_THRESHOLD = 12
alerted_matches = set()
previous_data = {}

LOWER_LEAGUE_KEYWORDS = [
    "2", "II", "III",
    "Reserve",
    "U19", "U21",
    "Primera B",
    "Serie B",
    "Liga 2",
    "National League",
    "Division 2",
    "Division 3"
]

EXCLUDED_LEAGUES = [
    "Premier League",
    "La Liga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
    "Champions League",
    "Europa League",
    "World Cup"
]

def fetch_data():
    params = {
        "apiKey": API_KEY,
        "regions": "eu",
        "markets": "totals",
        "oddsFormat": "decimal"
    }
    response = requests.get(BASE_URL, params=params)
    return response.json()

def calculate_suspicion(var_price, var_volume, books):
    score = 0

    if var_price >= 10:
        score += 30
    if var_price >= 15:
        score += 20
    if var_volume >= 50:
        score += 20
    if var_volume >= 100:
        score += 20
    if books <= 3:
        score += 10

    return min(score, 100)

async def send_alert(message):
    bot = Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=CHAT_ID, text=message)

async def analyze():
    while True:
        matches = fetch_data()

        for match in matches:
            league = match["sport_title"]

            if any(ex.lower() in league.lower() for ex in EXCLUDED_LEAGUES):
                continue

            if not any(keyword.lower() in league.lower() for keyword in LOWER_LEAGUE_KEYWORDS):
                continue

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
                                    old_price, old_volume = previous_data[key]

                                    variation_price = ((old_price - price) / old_price) * 100
                                    volume_index = (books_count * 10) + abs(variation_price * 5)
                                    variation_volume = ((volume_index - old_volume) / old_volume) * 100 if old_volume != 0 else 0

                                    suspicion_score = calculate_suspicion(
                                        variation_price,
                                        variation_volume,
                                        books_count
                                    )

                                    if variation_price >= ALERT_THRESHOLD and key not in alerted_matches:
                                        message = f"""
⚽️ {league}
🏟️ {home} vs {away}

📉 Totals | {variation_price:.2f}% drop ({old_price} → {price})
💰 Volume up {variation_volume:.2f}% ({old_volume:.0f} → {volume_index:.0f})

💶 Market Strength Index: {volume_index:.0f}
📊 Active Books: {books_count}

🚨 Suspicion Score: {suspicion_score}/100
"""
                                        await send_alert(message)
                                        alerted_matches.add(key)

                                    previous_data[key] = (price, volume_index)

                                else:
                                    volume_index = books_count * 10
                                    previous_data[key] = (price, volume_index)

        await asyncio.sleep(120)

if __name__ == "__main__":
    asyncio.run(analyze())