import requests
import pandas as pd
import numpy as np
import sqlite3
import time
import os

# ===== CONFIGURATION =====
ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SPORT = "soccer"
CHECK_INTERVAL = 600  # 10 minutes

DB_NAME = "odds.db"

# ===== TELEGRAM FUNCTION =====
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    })

# ===== DATABASE SETUP =====
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS odds (
    match TEXT,
    team TEXT,
    odds REAL,
    volume REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# ===== GET ODDS FROM API =====
def get_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    response = requests.get(url, params=params)
    return response.json()

# ===== SAVE DATA =====
def save_data(match, team, odds, volume):
    cursor.execute(
        "INSERT INTO odds (match, team, odds, volume) VALUES (?, ?, ?, ?)",
        (match, team, odds, volume)
    )
    conn.commit()

# ===== ANALYZE DATA =====
def analyze(match, team, current_odds, current_volume):

    df = pd.read_sql_query(
        "SELECT odds, volume FROM odds WHERE match=? AND team=?",
        conn, params=(match, team)
    )

    if len(df) < 10:
        return

    mean_odds = df['odds'].mean()
    std_odds = df['odds'].std()
    mean_volume = df['volume'].mean()

    variation = abs((current_odds - mean_odds) / mean_odds)

    volume_spike = current_volume > (3 * mean_volume)

    z_score = 0
    if std_odds != 0:
        z_score = abs((current_odds - mean_odds) / std_odds)

    # ===== RISK SCORE =====
    score = 0

    if variation > 0.20:
        score += 40

    if volume_spike:
        score += 40

    if z_score > 3:
        score += 20

    if score >= 60:
        send_telegram(
            f"🚨 ANOMALIE DETECTÉE\n"
            f"Match: {match}\n"
            f"Équipe: {team}\n"
            f"Variation: {round(variation*100,2)}%\n"
            f"Volume Spike: {volume_spike}\n"
            f"Z-score: {round(z_score,2)}\n"
            f"Score: {score}/100"
        )

# ===== MAIN LOOP =====
while True:
    try:
        data = get_odds()

        for match in data:
            for bookmaker in match["bookmakers"]:
                for outcome in bookmaker["markets"][0]["outcomes"]:

                    match_name = match["home_team"] + " vs " + match["away_team"]
                    team = outcome["name"]
                    odds = outcome["price"]

                    # ⚠️ Volume simulé (remplacer par Betfair API pour vrai volume)
                    volume = np.random.randint(10000, 200000)

                    save_data(match_name, team, odds, volume)
                    analyze(match_name, team, odds, volume)

        print("Scan terminé...")
        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Erreur:", e)
        time.sleep(60)
