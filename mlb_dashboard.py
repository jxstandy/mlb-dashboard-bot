import os
import time
import gspread
import pandas as pd
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials
import requests

# ======================================
# Google Sheets + API Setup
# ======================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "service_account.json"

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID is missing. Please set it in GitHub Secrets.")

spreadsheet = client.open_by_key(SPREADSHEET_ID)

# Odds API setup
API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4/sports"

# ======================================
# Helper Functions
# ======================================
def fetch_sports():
    """Fetch all available sports from Odds API"""
    url = f"{BASE_URL}?apiKey={API_KEY}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def fetch_odds(sport_key):
    """Fetch odds for a given sport"""
    url = f"{BASE_URL}/{sport_key}/odds/?apiKey={API_KEY}&regions=us&markets=h2h,spreads,totals"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"⚠️ Skipping {sport_key}: {resp.text}")
        return None
    return resp.json()

def format_dataframe(odds_json):
    """Turn API odds JSON into a dataframe"""
    rows = []
    for game in odds_json:
        teams = game.get("teams", [])
        home = game.get("home_team", "")
        commence = game.get("commence_time", "")
        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "Commence Time": commence,
                        "Home Team": home,
                        "Teams": " vs ".join(teams),
                        "Bookmaker": bookmaker["title"],
                        "Market": market["key"],
                        "Outcome": outcome["name"],
                        "Price": outcome["price"],
                        "Point": outcome.get("point", "")
                    })
    return pd.DataFrame(rows)

def update_sheet(df, sheet_name):
    """Batch update dataframe into sheet, with formatting"""
    try:
        ws = spreadsheet.worksheet(sheet_name[:99])  # Sheet names max 100 chars
    except:
        ws = spreadsheet.add_worksheet(title=sheet_name[:99], rows="200", cols="20")

    ws.clear()
    set_with_dataframe(ws, df, include_index=False, include_column_header=True, resize=True)

    # Formatting (color header row)
    fmt = {
        "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.86},
        "horizontalAlignment": "CENTER",
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
    }
    ws.format("1:1", fmt)

    print(f"✅ Updated {sheet_name} with {len(df)} rows")

# ======================================
# Main Process (Batch Updates)
# ======================================
def main():
    print("▶️ Running dashboard script...")
    sports = fetch_sports()
    print(f"📊 Found {len(sports)} sports")

    all_updates = []  # Buffer updates here

    for sport in sports:
        sport_key = sport["key"]
        sport_title = sport["title"]
        print(f"⏳ Fetching {sport_title} ({sport_key})...")

        odds_json = fetch_odds(sport_key)
        if not odds_json:
            continue

        df = format_dataframe(odds_json)
        if df.empty:
            print(f"⚠️ No data for {sport_title}")
            continue

        all_updates.append((sport_title, df))

    # === Batch write at the end ===
    for sport_title, df in all_updates:
        update_sheet(df, sport_title)

    print("🎉 All sports updated successfully!")

if __name__ == "__main__":
    main()
