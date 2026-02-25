import os
import time
import requests
import betfairlightweight
from telegram import Bot

# Variables environnement
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BETFAIR_USERNAME = os.getenv("BETFAIR_USERNAME")
BETFAIR_PASSWORD = os.getenv("BETFAIR_PASSWORD")
BETFAIR_APP_KEY = os.getenv("BETFAIR_APP_KEY")

bot = Bot(token=TELEGRAM_TOKEN)

# Connexion Betfair
trading = betfairlightweight.APIClient(
    username=BETFAIR_USERNAME,
    password=BETFAIR_PASSWORD,
    app_key=BETFAIR_APP_KEY
)

trading.login()

def get_markets():
    market_filter = {
        "eventTypeIds": ["1"],  # Football
        "marketCountries": ["GB", "ES", "FR", "IT", "DE"],
        "marketTypeCodes": ["MATCH_ODDS"]
    }

    return trading.betting.list_market_catalogue(
        filter=market_filter,
        max_results=10,
        market_projection=["RUNNER_METADATA"]
    )

def analyze_market(market_id):
    books = trading.betting.list_market_book(
        market_ids=[market_id],
        price_projection={"priceData": ["EX_BEST_OFFERS"]}
    )

    book = books[0]

    total_volume = book.total_matched

    price_changes = []
    for runner in book.runners:
        if runner.ex.available_to_back:
            price = runner.ex.available_to_back[0].price
            price_changes.append(price)

    anomaly_score = 0

    # Volume élevé
    if total_volume > 100000:
        anomaly_score += 2

    # Cotes très basses
    for p in price_changes:
        if p < 1.30:
            anomaly_score += 1

    return anomaly_score, total_volume, price_changes

def send_alert(message):
    bot.send_message(chat_id=CHAT_ID, text=message)

def main():
    while True:
        markets = get_markets()

        for market in markets:
            score, volume, prices = analyze_market(market.market_id)

            if score >= 3:
                msg = f"""
⚠️ Mouvement anormal détecté
Match: {market.market_name}
Volume: {volume}
Cotes: {prices}
Score anomalie: {score}
"""
                send_alert(msg)

        time.sleep(300)

if __name__ == "__main__":
    main()