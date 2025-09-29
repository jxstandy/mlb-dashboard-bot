import os
import requests
import pandas as pd
import datetime as dt
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import *

# -------------------------
# CONFIG
# -------------------------
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID is missing. Please set it in GitHub Secrets.")

# Google Sheets setup
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)

print(f"✅ Using Spreadsheet ID: {SPREADSHEET_ID}")
sheet = client.open_by_key(SPREADSHEET_ID)

# -------------------------
# Get all available sports from Odds API
# -------------------------
def fetch_sports():
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_API_KEY}"
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"❌ Error fetching sports list: {r.text}")
    sports_data = r.json()
    sports = {s["title"]: s["key"] for s in sports_data}
    return sports

# -------------------------
# Fetch Odds for a given sport
# -------------------------
def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?regions=us&markets=h2h,totals,spreads&oddsFormat=decimal&apiKey={ODDS_API_KEY}"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"❌ Error fetching {sport_key}: {r.text}")
        return pd.DataFrame()
    data = r.json()

    games = []
    for game in data:
        home = game["home_team"]
        away = game["away_team"]

        try:
            markets = {m["key"]: m for m in game["bookmakers"][0]["markets"]}
        except:
            continue

        moneyline = markets.get("h2h", {}).get("outcomes", [])
        spreads = markets.get("spreads", {}).get("outcomes", [])
        totals = markets.get("totals", {}).get("outcomes", [])

        games.append({
            "Game": f"{home} vs {away}",
            "Home Team": home,
            "Away Team": away,
            "Home ML": moneyline[0]["price"] if len(moneyline) > 0 else "N/A",
            "Away ML": moneyline[1]["price"] if len(moneyline) > 1 else "N/A",
            "Spread Home": spreads[0]["price"] if len(spreads) > 0 else "N/A",
            "Spread Away": spreads[1]["price"] if len(spreads) > 1 else "N/A",
            "Total Over": totals[0]["price"] if len(totals) > 0 else "N/A",
            "Total Under": totals[1]["price"] if len(totals) > 1 else "N/A",
            "Last Updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return pd.DataFrame(games)

# -------------------------
# Update Google Sheets tab
# -------------------------
def update_sheet(df, tab_name):
    try:
        ws = sheet.worksheet(tab_name)
        sheet.del_worksheet(ws)
    except:
        pass

    ws = sheet.add_worksheet(title=tab_name[:99], rows="200", cols="20")
    if not df.empty:
        ws.update([df.columns.values.tolist()] + df.values.tolist())
    return ws

# -------------------------
# Formatting rules
# -------------------------
fmt_fav = CellFormat(backgroundColor=Color(0.8, 1, 0.8))   # light green
fmt_dog = CellFormat(backgroundColor=Color(1, 0.8, 0.8))   # light red
fmt_finished = CellFormat(
    textFormat=TextFormat(strikethrough=True, foregroundColor=Color(0.7, 0.7, 0.7))
)  # gray strike-through

def apply_formatting(ws):
    game_data = ws.get_all_records()
    for i, row in enumerate(game_data, start=2):
        home_ml = row.get("Home ML")
        away_ml = row.get("Away ML")

        try:
            if home_ml != "N/A" and away_ml != "N/A":
                if float(home_ml) < float(away_ml):
                    format_cell_range(ws, f"D{i}", fmt_fav)
                    format_cell_range(ws, f"E{i}", fmt_dog)
                else:
                    format_cell_range(ws, f"D{i}", fmt_dog)
                    format_cell_range(ws, f"E{i}", fmt_fav)
        except:
            pass

        if "Final" in row["Game"]:
            format_cell_range(ws, f"A{i}:J{i}", fmt_finished)

# -------------------------
# Run for all sports
# -------------------------
sports = fetch_sports()
print(f"📊 Found {len(sports)} sports")

for sport_name, sport_key in sports.items():
    print(f"➡️ Updating {sport_name} ({sport_key})...")
    df = fetch_odds(sport_key)
    ws = update_sheet(df, sport_name)
    if not df.empty:
        apply_formatting(ws)

print("✅ All available sports updated in Google Sheets with formatting")
