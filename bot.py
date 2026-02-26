PRICE_HISTORY = {}
ALERTED_MOVES = {}

DROP_THRESHOLD = 12


async def analyze():
    url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals"

    response = requests.get(url)
    data = response.json()

    for match in data:

        league = match["sport_title"]
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

                    # Historique
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

                    # Gestion multi-alertes
                    if unique_key not in ALERTED_MOVES:
                        last_alert_price = old_price
                    else:
                        last_alert_price = ALERTED_MOVES[unique_key]

                    additional_drop = ((last_alert_price - new_price) / last_alert_price) * 100

                    if additional_drop < DROP_THRESHOLD:
                        continue

                    ALERTED_MOVES[unique_key] = new_price

                    # Simulation volume
                    base_volume = 3000
                    simulated_volume = base_volume * (1 + drop_percent/10)
                    volume_change = drop_percent * 8

                    # Construire historique formaté
                    history_text = ""
                    minute = len(history)

                    for h in history:
                        simulated_row_volume = int(base_volume * (1 + (minute/10)))
                        history_text += f"{minute:02d} | {line or '-'} | {h:.2f} | €{simulated_row_volume/1000:.2f}k\n"
                        minute -= 1

                    message = f"""
⚽️ {league}
🏟️ {home} vs {away}

📉 {market_type} | {drop_percent:.2f}% drop ({old_price:.2f} → {new_price:.2f})
💰 Volume up {volume_change:.2f}%

💶 Volume ({market_type}): €{simulated_volume/1000:.2f}k

Min | Line | Price | Volume
{history_text}
"""

                    await bot.send_message(chat_id=CHAT_ID, text=message)