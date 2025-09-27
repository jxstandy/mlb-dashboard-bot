import pandas as pd
import requests
import datetime as dt
import pytz
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ---------------------------
# Google Sheets Setup
# ---------------------------
SHEET_NAME = "MLB Dashboard"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)
sheets_api = build("sheets", "v4", credentials=creds)

try:
    spreadsheet = client.open(SHEET_NAME)
except gspread.SpreadsheetNotFound:
    spreadsheet = client.create(SHEET_NAME)
    spreadsheet.share("your_email@gmail.com", perm_type="user", role="writer")

spreadsheet_id = spreadsheet.id

# ---------------------------
# Fetch Odds API
# ---------------------------
API_KEY = "YOUR_ODDS_API_KEY"
SPORT = "baseball_mlb"
REGION = "us"

def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds?regions={REGION}&apiKey={API_KEY}"
    r = requests.get(url)
    data = r.json()

    games = []
    upcoming = []
    now = dt.datetime.now(dt.timezone.utc)
    ct = pytz.timezone("America/Chicago")

    for game in data:
        row = {
            "Game ID": game["id"],
            "Home Team": game["home_team"],
            "Away Team": game["away_team"],
            "Commence Time": game["commence_time"]
        }

        commence = pd.to_datetime(game["commence_time"], utc=True)

        if commence > now:
            row["Commence Time"] = commence.tz_convert(ct).strftime("%m/%d/%Y %I:%M %p CT")
            upcoming.append(row)
        else:
            row["Commence Time"] = commence.tz_convert(ct).strftime("%m/%d/%Y %I:%M %p CT")
            games.append(row)

    return pd.DataFrame(games), pd.DataFrame(upcoming)

# ---------------------------
# Clean DataFrame
# ---------------------------
def clean_dataframe(df):
    if df.empty:
        return df

    for col in df.columns:
        if df[col].dtype in ["float64", "int64"]:
            if df[col].between(0, 1).all():
                df[col] = (df[col] * 100).round(1).astype(str) + "%"

    return df

# ---------------------------
# Push to Google Sheets
# ---------------------------
def update_sheet(sheet_name, df):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        spreadsheet.del_worksheet(worksheet)
    except gspread.exceptions.WorksheetNotFound:
        pass

    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="200", cols="20")

    if not df.empty:
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    return worksheet.id

# ---------------------------
# Add Formatting
# ---------------------------
def add_formatting(sheet_id, is_games_tab=False):
    requests = []

    # ✅ Color scale for percentages
    requests.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{"sheetId": sheet_id}],
                "gradientRule": {
                    "minpoint": {"color": {"red": 1}, "type": "NUMBER", "value": "0"},
                    "midpoint": {"color": {"red": 1, "green": 1}, "type": "NUMBER", "value": "50"},
                    "maxpoint": {"color": {"green": 1}, "type": "NUMBER", "value": "100"}
                }
            },
            "index": 0
        }
    })

    # ✅ Strike-through finished games (Games tab only)
    if is_games_tab:
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{"sheetId": sheet_id}],
                    "booleanRule": {
                        "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=ROW()>1'}]},
                        "format": {"textFormat": {"strikethrough": True}}
                    }
                },
                "index": 1
            }
        })

    body = {"requests": requests}
    sheets_api.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

# ---------------------------
# Main
# ---------------------------
def main():
    games_df, upcoming_df = fetch_odds()
    games_df = clean_dataframe(games_df)
    upcoming_df = clean_dataframe(upcoming_df)

    games_sheet = update_sheet("Games", games_df)
    upcoming_sheet = update_sheet("Upcoming", upcoming_df)

    add_formatting(games_sheet, is_games_tab=True)
    add_formatting(upcoming_sheet, is_games_tab=False)

    print("✅ Sheets updated with color coding & strike-through!")

if __name__ == "__main__":
    main()
