import requests
import pandas as pd
import datetime as dt
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import *

# -------------------------
# Config
# -------------------------
API_KEY = os.environ["ODDS_API_KEY"]
SHEET_ID = os.environ["SHEET_ID"]

# Load Google Sheets credentials
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds_json = os.environ["GOOGLE_SHEETS_CREDENTIALS"]
creds_dict = json.loads(creds_json)
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID)

# -------------------------
# 1. Fetch MLB Odds
# -------------------------
def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?regions=us&markets=h2h,totals,spreads&oddsFormat=decimal&apiKey={API_KEY}"
    r = requests.get(url)
    data = r.json()

    games, upcoming = [], []
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5)))  # CT timezone

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

        commence = dt.datetime.fromisoformat(
            game["commence_time"].replace("Z", "+00:00")
        ).astimezone(now.tzinfo)

        row = {
            "Game": f"{home} vs {away}",
            "Home Team": home,
            "Away Team": away,
            "Commence (CT)": commence.strftime("%Y-%m-%d %H:%M"),
            "Home ML %": round(100 * (1 / moneyline[0]["price"])) if len(moneyline) > 0 else "N/A",
            "Away ML %": round(100 * (1 / moneyline[1]["price"])) if len(moneyline) > 1 else "N/A",
            "Run Line Home": spreads[0]["price"] if len(spreads) > 0 else "N/A",
            "Run Line Away": spreads[1]["price"] if len(spreads) > 1 else "N/A",
            "Total Over": totals[0]["price"] if len(totals) > 0 else "N/A",
            "Total Under": totals[1]["price"] if len(totals) > 1 else "N/A",
            "Last Updated": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if commence > now:
            upcoming.append(row)
        else:
            games.append(row)

    return pd.DataFrame(games), pd.DataFrame(upcoming)

# -------------------------
# 2. Push Data to Google Sheets
# -------------------------
def update_sheets():
    games_df, upcoming_df = fetch_odds()

    # --- Games Tab ---
    try:
        ws = sheet.worksheet("Games")
    except:
        ws = sheet.add_worksheet(title="Games", rows="100", cols="20")
    ws.clear()
    ws.update([games_df.columns.values.tolist()] + games_df.values.tolist())

    # --- Upcoming Tab ---
    try:
        ws2 = sheet.worksheet("Upcoming")
    except:
        ws2 = sheet.add_worksheet(title="Upcoming", rows="100", cols="20")
    ws2.clear()
    ws2.update([upcoming_df.columns.values.tolist()] + upcoming_df.values.tolist())

    # -------------------------
    # 3. Apply Formatting
    # -------------------------
    fmt_green = CellFormat(textFormat=TextFormat(bold=True), backgroundColor=Color(0.8, 1, 0.8))
    fmt_red = CellFormat(textFormat=TextFormat(bold=True), backgroundColor=Color(1, 0.8, 0.8))
    fmt_strike = CellFormat(textFormat=TextFormat(strikethrough=True))

    # Apply % win column formatting
    for tab in ["Games", "Upcoming"]:
        ws = sheet.worksheet(tab)
        data = ws.get_all_values()

        if len(data) > 1:  # skip empty
            rows = len(data)
            home_vals = ws.range(f"E2:E{rows}")  # Home ML %
            away_vals = ws.range(f"F2:F{rows}")  # Away ML %

            for cell in home_vals:
                try:
                    val = float(cell.value)
                    if val > 50:
                        format_cell_range(ws, cell.address, fmt_green)
                    else:
                        format_cell_range(ws, cell.address, fmt_red)
                except:
                    pass

            for cell in away_vals:
                try:
                    val = float(cell.value)
                    if val > 50:
                        format_cell_range(ws, cell.address, fmt_green)
                    else:
                        format_cell_range(ws, cell.address, fmt_red)
                except:
                    pass

        # Strike-through finished games (only in Games tab)
        if tab == "Games":
            finished = ws.range(f"A2:A{rows}")
            for cell in finished:
                if cell.value:  # If game listed
                    format_cell_range(ws, cell.address, fmt_strike)

    print("✅ Sheets updated & formatted successfully.")

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    update_sheets()
