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
# FLASK (POUR RENDER)
# ==============================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ==============================
# FILTRE LIGUES AUTORISÉES
# ==============================

ALLOWED_KEYWORDS = [
    "myanmar", "burma",
    "israel",
    "mexico",
    "macedonia",
    "bangladesh",
    "bosnia",
    "india",
    "vietnam",
    "malaysia",
    "albania",
    "bolivia",
    "jordan",
    "friendly",
    "u21", "u20", "u19", "u18"
]

# Exclusion spécifique premières divisions
BLOCK_SPECIFIC = [
    "brazil_serie_a",
    "brazil serie a",
    "liga_mx",
    "liga mx",
    "bosnia_premier",
    "bosnia premier",
    "premier league bosnia"
]

# Exclusion compétitions majeures mondiales
BLOCK_MAJOR = [
    "champions",
    "europa",
    "conference",
    "uefa",
    "world cup",
    "euro",
    "copa america",
    "nations league"
]

def is_allowed_league(match):
    sport_key = match.get("sport_key", "").lower()
    sport_title = match.get("sport_title", "").lower()

    combined = sport_key + " " + sport_title

    # Doit contenir pays autorisé
    if not any(keyword in combined for keyword in ALLOWED_KEYWORDS):
        return False

    # Bloquer divisions spécifiques
    if any(block in combined for block in BLOCK_SPECIFIC):
        return False

    # Bloquer compétitions majeures
    if any(block in combined for block in BLOCK_MAJOR):
        return False

    return True

# ==============================
# ANALYSE
# ==============================

async def analyze():

    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals"
    response = requests.get(url)
    data = response.json()

    for match in data:

        if not is_allowed_league(match):
            continue

        league = match.get("sport_title", "")
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

                    # Détermination du pari exact
                    if market_type == "1X2":
                        if label == home:
                            bet_label = "🏠 Home (1) – Victoire domicile"
                        elif label == away:
                            bet_label = "🚗 Away (2) – Victoire extérieur"
                        else:
                            bet_label = "🤝 Draw (X) – Match nul"
                    else:
                        if label.lower() == "over":
                            bet_label = f"🔼 Over {line} – Plus de {line} buts"
                        else:
                            bet_label = f"🔽 Under {line} – Moins de {line} buts"

                    unique_key = f"{match_id}_{market_type}_{label}_{line}"

                    # Historique des cotes
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

                    # Multi-alerte seulement si nouveau drop ≥ 12%
                    if unique_key not in ALERTED_MOVES:
                        last_alert_price = old_price
                    else:
                        last_alert_price = ALERTED_MOVES[unique_key]

                    additional_drop = ((last_alert_price - new_price) / last_alert_price) * 100

                    if additional_drop < DROP_THRESHOLD:
                        continue

                    ALERTED_MOVES[unique_key] = new_price

                    # Score de suspicion
                    suspicion_score = min(100, int(drop_percent * 5))

                    if suspicion_score < 40:
                        level = "Faible"
                    elif suspicion_score < 70:
                        level = "Moyen"
                    else:
                        level = "Élevé"

                    # Historique formaté
                    history_text = ""
                    minute = len(history)

                    for h in history:
                        history_text += f"{minute:02d} min | {h:.2f}\n"
                        minute -= 1

                    message = f"""
🚨 ALERTE BAISSE DE COTE 🚨

⚽ {league}
🏟 {home} vs {away}

🎯 PARI IMPACTÉ :
{bet_label}

📉 La cote a chuté :
Ancienne cote : {old_price:.2f}
Nouvelle cote : {new_price:.2f}
Baisse totale : {drop_percent:.2f}%

🚨 Score de suspicion : {suspicion_score}/100 ({level})

📈 Évolution minute par minute :
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