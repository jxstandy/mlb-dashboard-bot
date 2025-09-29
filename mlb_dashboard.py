import os
import requests
import pandas as pd
import datetime as dt
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import *
from gspread_dataframe import set_with_dataframe

# -------------------------
# CONFIG
# -------------------------
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")

if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID is missing. Please set it in GitHub Secrets.")

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open_by_key(SPREADSHEET_ID)
print(f"✅ Using Spreadsheet ID: {SPREADSHEET_ID}")

# -------------------------
# Helper to fetch odds
# -------------------------
def fetch_odds(sport_key, sport_name):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
    params = {
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "decimal",
        "apiKey": ODDS_API_KEY
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        print(f"❌ Error fetching {sport_name}: {r.text}")
        return pd.DataFrame()

    data = r.json()
    games = []
    for game in data:
        home = game.get("home_team")
        away = game.get("away_team")
        bookmakers = game.get("bookmakers", [])
        if not bookmakers:
            continue

        try:
            markets = {m["key"]: m for m in bookmakers[0]["markets"]}
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
            "Run/Spread Home": spreads[0]["price"] if len(spreads) > 0 else "N/A",
            "Run/Spread Away": spreads[1]["price"] if len(spreads) > 1 else "N/A",
            "Total Over": totals[0]["price"] if len(totals) > 0 else "N/A",
            "Total Under": totals[1]["price"] if len(totals) > 1 else "N/A",
            "Last Updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return pd.DataFrame(games)

# -------------------------
# Update sheet
# -------------------------
def update_sheet(df, tab_name):
    try:
        ws = sheet.worksheet(tab_name)
        sheet.del_worksheet(ws)
    except:
        pass

    ws = sheet.add_worksheet(title=tab_name, rows="200", cols="20")
    set_with_dataframe(ws, df.fillna("N/A"))

    # Apply formatting
    fmt_fav = CellFormat(backgroundColor=Color(0.8, 1, 0.8))   # light green
    fmt_dog = CellFormat(backgroundColor=Color(1, 0.8, 0.8))   # light red
    fmt_finished = CellFormat(textFormat=TextFormat(strikethrough=True, foregroundColor=Color(0.7, 0.7, 0.7)))

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

    print(f"✅ Updated tab: {tab_name}")
    return ws

# -------------------------
# Main Sports to Track
# -------------------------
major_sports = {
    "baseball_mlb": "MLB",
    "basketball_nba": "NBA",
    "americanfootball_nfl": "NFL",
    "icehockey_nhl": "NHL",
    "americanfootball_ncaaf": "NCAAF",
    "basketball_ncaab": "NCAAB",
    "mma_mixed_martial_arts": "UFC/MMA",
    "soccer_usa_mls": "Soccer (MLS)",
    "soccer_epl": "Soccer (EPL)",
    "golf_pga": "Golf (PGA)",
    "tennis_atp": "Tennis (ATP)",
    "tennis_wta": "Tennis (WTA)"
}

# -------------------------
# Run all sports
# -------------------------
for key, name in major_sports.items():
    print(f"📊 Updating {name}...")
    df = fetch_odds(key, name)
    if not df.empty:
        update_sheet(df, name)

print("🎉 All sports updated with odds and formatting.")
