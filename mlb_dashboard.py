import os
import gspread
from google.oauth2.service_account import Credentials
import requests

# ------------------------------------------------------
# CONFIG
# ------------------------------------------------------
# Add both Sheets + Drive scopes (needed for creating new sheets)
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load service account
SERVICE_ACCOUNT_FILE = "service_account.json"

# Get Spreadsheet ID from environment if provided
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", None)

# Sports to pull odds for
SPORTS = [
    "baseball_mlb",
    "basketball_nba",
    "basketball_ncaab",
    "football_nfl",
    "football_ncaaf",
    "icehockey_nhl",
    "soccer_epl",
    "soccer_uefa_champs_league",
    "mma_mixed_martial_arts",
    "tennis_atp_singles"
]

# Replace with your Odds API key
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

# ------------------------------------------------------
# AUTHENTICATION
# ------------------------------------------------------
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

# If no spreadsheet ID is provided, create a new one
if not SPREADSHEET_ID:
    print("⚠️ No Spreadsheet ID provided. Creating new sheet...")
    spreadsheet = client.create("Sports Odds Dashboard")
    SPREADSHEET_ID = spreadsheet.id
    print(f"✅ Created new spreadsheet: {SPREADSHEET_ID}")
else:
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        print(f"✅ Using existing spreadsheet: {SPREADSHEET_ID}")
    except Exception as e:
        print(f"⚠️ Could not open sheet by ID ({SPREADSHEET_ID}), creating new one instead...")
        spreadsheet = client.create("Sports Odds Dashboard")
        SPREADSHEET_ID = spreadsheet.id
        print(f"✅ Created new spreadsheet: {SPREADSHEET_ID}")

# ------------------------------------------------------
# FETCH ODDS DATA
# ------------------------------------------------------
def fetch_odds(sport_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "decimal"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"⚠️ Failed to fetch odds for {sport_key}: {response.text}")
        return []

# ------------------------------------------------------
# UPDATE SHEETS
# ------------------------------------------------------
for sport in SPORTS:
    data = fetch_odds(sport)

    # Prepare rows
    rows = [["Home Team", "Away Team", "Bookmaker", "Home Odds", "Away Odds"]]
    for game in data:
        home_team = game.get("home_team", "N/A")
        away_team = [team for team in game["teams"] if team != home_team][0]

        for bookmaker in game.get("bookmakers", []):
            book_name = bookmaker["title"]
            markets = bookmaker.get("markets", [])
            if markets:
                outcomes = markets[0].get("outcomes", [])
                home_odds = next((o["price"] for o in outcomes if o["name"] == home_team), "N/A")
                away_odds = next((o["price"] for o in outcomes if o["name"] == away_team), "N/A")
                rows.append([home_team, away_team, book_name, home_odds, away_odds])

    # Update or create worksheet
    try:
        worksheet = spreadsheet.worksheet(sport)
        spreadsheet.del_worksheet(worksheet)  # refresh old sheet
    except:
        pass

    worksheet = spreadsheet.add_worksheet(title=sport, rows=len(rows), cols=len(rows[0]))
    worksheet.update("A1", rows)
    print(f"✅ Updated sheet for {sport}")

print(f"🎉 All sports odds updated in spreadsheet: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
