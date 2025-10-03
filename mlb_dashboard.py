import os
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import CellFormat, Color, format_cell_ranges

# ---------------- CONFIG ----------------
ODDS_API_KEY = "ac062d318b462f4a2efe7b5ce7bf8cdb"   # Your Odds API key
SPREADSHEET_ID = "1-VXr3AqIr7mRhoHEnIMU6aZSlQvFUpmoCVMmQUgZSko"  # Your sheet ID
SERVICE_ACCOUNT_JSON = "service_account.json"       # Path to your Google service account file

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_JSON, scopes=SCOPES)
client = gspread.authorize(creds)

# ---------------- FETCH MLB ODDS ----------------
url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"

params = {
    "apiKey": ODDS_API_KEY,
    "regions": "us",
    "markets": "h2h",
    "oddsFormat": "decimal"
}

response = requests.get(url, params=params)
if response.status_code != 200:
    raise Exception(f"Error {response.status_code}: {response.text}")

games = response.json()
if not games:
    print("No upcoming MLB games found.")
    exit()

# ---------------- PARSE DATA ----------------
rows = []
for game in games:
    home = game["home_team"]
    away = game["away_team"]
    commence = game["commence_time"]

    for bookmaker in game.get("bookmakers", []):
        book = bookmaker["title"]
        for market in bookmaker.get("markets", []):
            if market["key"] == "h2h":
                for out in market["outcomes"]:
                    odds = out["price"]
                    prob = round((1 / odds) * 100, 2)  # implied probability %
                    rows.append([commence, home, away, book, out["name"], odds, prob])

# Convert to DataFrame
df = pd.DataFrame(rows, columns=["Game Time", "Home Team", "Away Team", "Sportsbook", "Team", "Odds", "Win Probability %"])

# ---------------- WRITE TO GOOGLE SHEETS ----------------
try:
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet("MLB Moneyline")
except gspread.exceptions.WorksheetNotFound:
    sheet = client.open_by_key(SPREADSHEET_ID).add_worksheet("MLB Moneyline", rows="200", cols="10")

# Clear old content
sheet.clear()

# Write new data
sheet.update([df.columns.values.tolist()] + df.values.tolist())

# ---------------- COLOR FORMATTING ----------------
header = df.columns.tolist()
prob_col = header.index("Win Probability %") + 1  # 1-based index for column

formats = []
for i, row in df.iterrows():
    prob = row["Win Probability %"]
    if prob >= 50:
        fmt = CellFormat(backgroundColor=Color(0.6, 0.9, 0.6))  # green
    else:
        fmt = CellFormat(backgroundColor=Color(0.95, 0.6, 0.6))  # red
    cell = f"{chr(64+prob_col)}{i+2}"  # column letter + row number
    formats.append((cell, fmt))

for cell, fmt in formats:
    format_cell_ranges(sheet, [(cell, fmt)])

print("✅ MLB Moneyline odds updated to Google Sheets with probabilities and color coding.")
