import os
import requests
import pandas as pd
import datetime as dt
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import *

# -------------------------
# CONFIG (from GitHub secrets)
# -------------------------
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
SPREADSHEET_ID = os.getenv("GOOGLE_SHEET_ID")

if not ODDS_API_KEY:
    raise ValueError("❌ ODDS_API_KEY is missing. Did you set it in GitHub Secrets?")

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)

print(f"👤 Service account email: {creds.service_account_email}")

spreadsheet = None
if SPREADSHEET_ID:
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        print(f"📄 Connected to Google Sheet: {SPREADSHEET_ID}")
    except Exception as e:
        print(f"⚠️ Could not open sheet by ID ({SPREADSHEET_ID}): {e}")

if not spreadsheet:
    spreadsheet = client.create("Sports Odds Dashboard")
    SPREADSHEET_ID = spreadsheet.id
    print(f"🆕 Created new Google Sheet: {SPREADSHEET_ID}")

# -------------------------
# 1. Fetch All Sports from API
# -------------------------
def fetch_all_sports():
    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={ODDS_API_KEY}"
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"❌ Failed to fetch sports list: {r.text}")
    return r.json()

def fetch_odds(sport_key, sport_name):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?regions=us&markets=h2h,totals,spreads&oddsFormat=decimal&apiKey={ODDS_API_KEY}"
    r = requests.get(url)
    if r.status_code != 200:
        print(f"⚠️ Failed to fetch odds for {sport_name}: {r.text}")
        return pd.DataFrame()

    data = r.json()
    games = []
    for game in data:
        home = game.get("home_team")
        away = game.get("away_team")

        try:
            markets = {m["key"]: m for m in game["bookmakers"][0]["markets"]}
        except Exception:
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

# -------------------------
# 2. Push to Google Sheets
# -------------------------
def update_sheet(df, tab_name):
    try:
        ws = spreadsheet.worksheet(tab_name)
        spreadsheet.del_worksheet(ws)
    except:
        pass
    ws = spreadsheet.add_worksheet(title=tab_name, rows="100", cols="20")
    ws.update([df.columns.values.tolist()] + df.values.tolist())
    return ws

# -------------------------
# 3. Formatting
# -------------------------
fmt_fav = CellFormat(backgroundColor=Color(0.8, 1, 0.8))   # light green
fmt_dog = CellFormat(backgroundColor=Color(1, 0.8, 0.8))   # light red
fmt_finished = CellFormat(textFormat=TextFormat(strikethrough=True, foregroundColor=Color(0.7, 0.7, 0.7)))  # gray strike-through

def apply_formatting(ws):
    game_data = ws.get_all_records()
    for i, row in enumerate(game_data, start=2):  # row 2 onwards
        home_ml = row.get("Home ML")
        away_ml = row.get("Away ML")

        try:
            if home_ml != "N/A" and away_ml != "N/A":
                if float(home_ml) < float(away_ml):
                    format_cell_range(ws, f"D{i}", fmt_fav)  # Home ML
                    format_cell_range(ws, f"E{i}", fmt_dog)  # Away ML
                else:
                    format_cell_range(ws, f"D{i}", fmt_dog)
                    format_cell_range(ws, f"E{i}", fmt_fav)
        except:
            pass

        # Cross out finished games if they contain "Final"
        if "Final" in row.get("Game", ""):
            format_cell_range(ws, f"A{i}:J{i}", fmt_finished)

# -------------------------
# 4. Main Script
# -------------------------
sports_list = fetch_all_sports()

for sport in sports_list:
    key = sport.get("key")
    title = sport.get("title")
    if not key or not title:
        continue
    print(f"➡️ Fetching odds for {title} ({key})")
    df = fetch_odds(key, title)
    if not df.empty:
        ws = update_sheet(df, title[:30])  # limit to 30 chars
        apply_formatting(ws)

print("✅ Dashboard updated in Google Sheets with ALL sports odds + formatting")
print(f"📄 Final Spreadsheet ID: {SPREADSHEET_ID}")
