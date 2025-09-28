import pandas as pd
import requests
import datetime as dt
import pytz
import gspread
from gspread_formatting import *
from google.oauth2.service_account import Credentials

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)

# Replace with your Google Sheet ID
SPREADSHEET_ID = "YOUR_SHEET_ID_HERE"

def fetch_odds():
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
    params = {"regions": "us", "markets": "h2h", "oddsFormat": "decimal"}
    response = requests.get(url, params=params)
    games, upcoming = [], []

    if response.status_code == 200:
        now = dt.datetime.now(dt.timezone.utc)
        for game in response.json():
            row = {
                "Game": f"{game['home_team']} vs {game['away_team']}",
                "Home Team": game["home_team"],
                "Away Team": game["away_team"],
                "Commence Time (CT)": dt.datetime.fromisoformat(
                    game["commence_time"].replace("Z", "+00:00")
                ).astimezone(pytz.timezone("US/Central")).strftime("%Y-%m-%d %H:%M:%S"),
                "Last Updated": now.astimezone(pytz.timezone("US/Central")).strftime("%Y-%m-%d %H:%M:%S"),
            }

            if game["bookmakers"]:
                odds = game["bookmakers"][0]["markets"][0]["outcomes"]
                for outcome in odds:
                    if outcome["name"] == row["Home Team"]:
                        row["Home ML %"] = round(100 / outcome["price"], 2)
                    elif outcome["name"] == row["Away Team"]:
                        row["Away ML %"] = round(100 / outcome["price"], 2)

            commence = dt.datetime.fromisoformat(game["commence_time"].replace("Z", "+00:00"))
            if commence > now:
                upcoming.append(row)
            else:
                games.append(row)

    return pd.DataFrame(games), pd.DataFrame(upcoming)

def update_sheet():
    games_df, upcoming_df = fetch_odds()
    sh = client.open_by_key(SPREADSHEET_ID)

    # Clear and update sheets
    for name, df in {"Games": games_df, "Upcoming": upcoming_df}.items():
        try:
            worksheet = sh.worksheet(name)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=name, rows="100", cols="20")

        worksheet.update([df.columns.values.tolist()] + df.values.tolist())

        # Format percentages
        fmt = cellFormat(
            numberFormat=NumberFormat(type="PERCENT", pattern="0.00%"),
            textFormat=textFormat(bold=False)
        )
        format_cell_range(worksheet, "E:F", fmt)

        # Color coding
        red = Color(1, 0.8, 0.8)
        green = Color(0.8, 1, 0.8)
        format_cell_ranges(worksheet, {
            "E:E": CellFormat(backgroundColor=green),
            "F:F": CellFormat(backgroundColor=red),
        })

        # Strike-through finished games
        if name == "Games":
            strike = CellFormat(textFormat=textFormat(strikethrough=True))
            format_cell_range(worksheet, "A:A", strike)

if __name__ == "__main__":
    update_sheet()