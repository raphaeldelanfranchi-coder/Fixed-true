import requests
import asyncio
import os
from telegram import Bot
from flask import Flask
from threading import Thread

# ==============================
# CONFIG
# ==============================

API_KEY = os.getenv("ODDS_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

DROP_THRESHOLD = 12

bot = Bot(token=BOT_TOKEN)

PRICE_HISTORY = {}
ALERTED_MOVES = {}

# ==============================
# FLASK (OBLIGATOIRE POUR RENDER)
# ==============================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==============================
# FILTRE GRANDES LIGUES
# ==============================

BIG_LEAGUE_KEYWORDS = [
    "premier",
    "la liga",
    "bundesliga",
    "serie a",
    "ligue 1",
    "champions",
    "europa",
    "conference",
    "uefa",
    "world cup",
    "euro ",
    "copa america",
    "nations league"
]

# ==============================
# ANALYSE
# ==============================

async def analyze():

    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals"
    response = requests.get(url)
    data = response.json()

    for match in data:

        league = match["sport_title"]

        # ❌ EXCLURE GRANDES LIGUES
        if any(keyword in league.lower() for keyword in BIG_LEAGUE_KEYWORDS):
            continue

        home = match["home_team"]
        away = [t for t in match["teams"] if t != home][0]
        match_id = match["id"]

        for bookmaker in match["bookmakers"]:
            for market in bookmaker["markets"]:

                if market["key"] not in ["h2h", "totals"]:
                    continue

                market_type = "1X2" if market["key"] == "h2h" else "Totals"

                for outcome in market["outcomes"]:

                    label = outcome["name"]
                    line = outcome.get("point", "")
                    price = outcome["price"]

                    unique_key = f"{match_id}_{market_type}_{label}_{line}"

                    # -------- HISTORIQUE --------
                    if unique_key not in PRICE_HISTORY:
                        PRICE_HISTORY[unique_key] = []

                    PRICE_HISTORY[unique_key].append(price)

                    if len(PRICE_HISTORY[unique_key]) > 15:
                        PRICE_HISTORY[unique_key].pop(0)

                    history = PRICE_HISTORY[unique_key]

                    if len(history) < 2:
                        continue

                    old_price = history[0]
                    new_price = history[-1]

                    drop_percent = ((old_price - new_price) / old_price) * 100

                    # -------- GESTION MULTI-ALERTES --------
                    if unique_key not in ALERTED_MOVES:
                        last_alert_price = old_price
                    else:
                        last_alert_price = ALERTED_MOVES[unique_key]

                    additional_drop = ((last_alert_price - new_price) / last_alert_price) * 100

                    if additional_drop < DROP_THRESHOLD:
                        continue

                    ALERTED_MOVES[unique_key] = new_price

                    # -------- SCORE SUSPICION --------
                    suspicion_score = min(100, int(drop_percent * 5))

                    if suspicion_score < 40:
                        level = "🟢 Low"
                    elif suspicion_score < 70:
                        level = "🟠 Medium"
                    else:
                        level = "🔴 High"

                    # -------- HISTORIQUE FORMATÉ --------
                    history_text = ""
                    minute = len(history)

                    for h in history:
                        history_text += f"{minute:02d} | {line or '-'} | {h:.2f}\n"
                        minute -= 1

                    message = f"""
⚽️ {league}
🏟️ {home} vs {away}

📊 Marché : {market_type}
🎯 {label} {line}

📉 {drop_percent:.2f}% drop ({old_price:.2f} → {new_price:.2f})

🚨 Suspicion Score: {suspicion_score}/100 {level}

Min | Line | Price
{history_text}
"""

                    await bot.send_message(chat_id=CHAT_ID, text=message)

# ==============================
# LOOP PRINCIPALE
# ==============================

async def main_loop():
    while True:
        try:
            await analyze()
        except Exception as e:
            print("Erreur :", e)
        await asyncio.sleep(120)

def start_async_loop():
    asyncio.run(main_loop())

# ==============================
# START
# ==============================

if __name__ == "__main__":
    Thread(target=run_flask).start()
    Thread(target=start_async_loop).start()