import os
import requests
import pandas as pd
import datetime as dt
from pybaseball import pitching_stats, batting_stats
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import *

# -------------------------
# CONFIG (from GitHub secrets)
# -------------------------
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)

# 🔎 Debug prints
print("🔑 Using Sheet ID:", SPREADSHEET_ID)
print("👤 Service account email:", creds.service_account_email)

# Always open by ID (no auto-create)
sheet = client.open_by_key(SPREADSHEET_ID)
print("✅ Connected successfully to Google Sheet")

# -------------------------
# 1. Fetch MLB Odds
# -------------------------
def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?regions=us&markets=h2h,totals,spreads&oddsFormat=decimal&apiKey={ODDS_API_KEY}"
    r = requests.get(url)
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
            "Run Line Home": spreads[0]["price"] if len(spreads) > 0 else "N/A",
            "Run Line Away": spreads[1]["price"] if len(spreads) > 1 else "N/A",
            "Total Over": totals[0]["price"] if len(totals) > 0 else "N/A",
            "Total Under": totals[1]["price"] if len(totals) > 1 else "N/A",
            "Last Updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    return pd.DataFrame(games)

games_df = fetch_odds()

# -------------------------
# 2. Pitcher + Hitter Stats
# -------------------------
pitching_df = pitching_stats(2024)[["Name", "Team", "ERA", "WHIP", "FIP", "IP"]]
hitting_df = batting_stats(2024)[["Name", "Team", "AVG", "OBP", "SLG", "OPS", "HR", "RBI", "SO", "BB"]]

# -------------------------
# 3. Push to Google Sheets
# -------------------------
def update_sheet(df, tab_name):
    try:
        ws = sheet.worksheet(tab_name)
        sheet.del_worksheet(ws)
    except:
        pass
    ws = sheet.add_worksheet(title=tab_name, rows="100", cols="20")
    ws.update([df.columns.values.tolist()] + df.values.tolist())
    return ws

ws_games = update_sheet(games_df, "Games")
update_sheet(pitching_df, "Pitcher Stats")
update_sheet(hitting_df, "Hitter Stats")

# -------------------------
# 4. Formatting (Color + Strike-through)
# -------------------------
fmt_fav = CellFormat(backgroundColor=Color(0.8, 1, 0.8))   # light green
fmt_dog = CellFormat(backgroundColor=Color(1, 0.8, 0.8))   # light red
fmt_finished = CellFormat(textFormat=TextFormat(strikethrough=True, foregroundColor=Color(0.7, 0.7, 0.7)))  # gray strike-through

# Apply formatting
game_data = ws_games.get_all_records()
for i, row in enumerate(game_data, start=2):  # row 2 onwards (row 1 is headers)
    home_ml = row.get("Home ML")
    away_ml = row.get("Away ML")

    # Moneyline logic: lower odds = favorite
    try:
        if home_ml != "N/A" and away_ml != "N/A":
            if float(home_ml) < float(away_ml):
                format_cell_range(ws_games, f"D{i}", fmt_fav)
                format_cell_range(ws_games, f"E{i}", fmt_dog)
            else:
                format_cell_range(ws_games, f"D{i}", fmt_dog)
                format_cell_range(ws_games, f"E{i}", fmt_fav)
    except:
        pass

    # Example: cross out games already played (stub logic for now)
    if "Final" in row["Game"]:
        format_cell_range(ws_games, f"A{i}:J{i}", fmt_finished)

print("✅ MLB Dashboard updated in Google Sheets with formatting")
