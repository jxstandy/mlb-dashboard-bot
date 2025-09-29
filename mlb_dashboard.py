import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from gspread_formatting import CellFormat, Color, format_cell_range, TextFormat

# === Google Sheets Setup ===
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID is missing. Please set it in GitHub Secrets.")

creds_dict = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT"))
creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# === Odds API Setup ===
API_KEY = os.getenv("ODDS_API_KEY")  # Add this as a secret
BASE_URL = "https://api.the-odds-api.com/v4/sports"

# Major sports only
SPORTS = {
    "Baseball (MLB)": "baseball_mlb",
    "Basketball (NBA)": "basketball_nba",
    "Football (NFL)": "americanfootball_nfl",
    "College Football (NCAAF)": "americanfootball_ncaaf",
    "College Basketball (NCAAB)": "basketball_ncaab",
    "Hockey (NHL)": "icehockey_nhl",
    "Soccer (EPL)": "soccer_epl"
}

# === Formatting ===
header_format = CellFormat(
    backgroundColor=Color(0.2, 0.2, 0.2),
    textFormat=TextFormat(bold=True, foregroundColor=Color(1, 1, 1))
)
green_format = CellFormat(backgroundColor=Color(0.7, 0.9, 0.7))
red_format = CellFormat(backgroundColor=Color(0.9, 0.7, 0.7))

def fetch_odds(sport_key):
    url = f"{BASE_URL}/{sport_key}/odds"
    params = {"apiKey": API_KEY, "regions": "us", "markets": "h2h,spreads,totals"}
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"⚠️ Error fetching {sport_key}: {response.text}")
        return None
    return response.json()

def update_sheet(df, sheet_name):
    try:
        try:
            ws = spreadsheet.worksheet(sheet_name)
            spreadsheet.del_worksheet(ws)
        except gspread.exceptions.WorksheetNotFound:
            pass
        ws = spreadsheet.add_worksheet(title=sheet_name, rows="200", cols="20")

        if df is not None and not df.empty:
            set_with_dataframe(ws, df)
            format_cell_range(ws, "1:1", header_format)
            
            # Conditional formatting odds column
            if "Odds" in df.columns:
                for idx, val in enumerate(df["Odds"], start=2):
                    if isinstance(val, (int, float)):
                        cell = f"C{idx}"
                        if val > 0:
                            format_cell_range(ws, cell, green_format)
                        elif val < 0:
                            format_cell_range(ws, cell, red_format)
    except Exception as e:
        print(f"⚠️ Error updating sheet {sheet_name}: {e}")

def build_dataframe(data):
    if not data:
        return pd.DataFrame()
    rows = []
    for game in data:
        home = game["home_team"]
        away = [t for t in game["teams"] if t != home][0]
        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "Home": home,
                        "Away": away,
                        "Market": market.get("key", ""),
                        "Team": outcome.get("name", ""),
                        "Odds": outcome.get("price", None),
                        "Book": bookmaker.get("title", "")
                    })
    return pd.DataFrame(rows)

# === Main ===
if __name__ == "__main__":
    print(f"✅ Using Spreadsheet ID: {SPREADSHEET_ID}")
    for sport_name, sport_key in SPORTS.items():
        print(f"⚡ Updating {sport_name}...")
        data = fetch_odds(sport_key)
        df = build_dataframe(data) if data else pd.DataFrame()
        update_sheet(df, sport_name)
    print("🎉 Dashboard updated successfully!")
