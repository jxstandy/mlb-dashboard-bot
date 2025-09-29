import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from gspread_formatting import (
    CellFormat, Color, set_frozen, format_cell_ranges, ConditionalFormatRule, BooleanCondition
)

# =========================
# Load Environment Variables
# =========================
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

if not SPREADSHEET_ID:
    raise ValueError("❌ SPREADSHEET_ID is missing. Please set it in GitHub Secrets.")
if not ODDS_API_KEY:
    raise ValueError("❌ ODDS_API_KEY is missing. Please set it in GitHub Secrets.")

# =========================
# Google Sheets Auth
# =========================
creds_dict = json.loads(os.getenv("GOOGLE_SERVICE_JSON"))
creds = Credentials.from_service_account_info(
    creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# =========================
# Major Sports to Track
# =========================
MAJOR_SPORTS = {
    "baseball_mlb": "MLB",
    "basketball_nba": "NBA",
    "americanfootball_nfl": "NFL",
    "icehockey_nhl": "NHL",
    "americanfootball_ncaaf": "NCAAF",
    "basketball_ncaab": "NCAAB",
    "soccer_epl": "Soccer_EPL",
    "soccer_usa_mls": "Soccer_MLS",
    "mma_mixed_martial_arts": "MMA",
    "tennis_atp": "Tennis_ATP",
    "tennis_wta": "Tennis_WTA",
}

# =========================
# Formatting Helpers
# =========================
header_fmt = CellFormat(
    backgroundColor=Color(0.2, 0.4, 0.7),  # Blue header
    textFormat={"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
)

alt_row_fmt = CellFormat(backgroundColor=Color(0.95, 0.95, 0.95))  # Gray rows

best_odds_fmt = CellFormat(backgroundColor=Color(0.8, 1, 0.8))  # Light green
worst_odds_fmt = CellFormat(backgroundColor=Color(1, 0.8, 0.8))  # Light red

# =========================
# Update Sheet Function
# =========================
def update_sheet(df, tab_name):
    try:
        try:
            ws = spreadsheet.worksheet(tab_name)
            ws.clear()
        except gspread.exceptions.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=tab_name, rows="200", cols="20")

        # Write DataFrame
        set_with_dataframe(ws, df)

        # Freeze header + format
        set_frozen(ws, rows=1)
        format_cell_ranges(ws, {"1:1": header_fmt})

        # Alternate rows
        for row in range(2, len(df) + 2, 2):
            ws.format(f"A{row}:Z{row}", alt_row_fmt)

        # Apply conditional formatting for odds columns (anything with "_price")
        rules = []
        for idx, col in enumerate(df.columns, start=1):
            if "price" in col.lower():  
                col_letter = chr(64 + idx)  # convert 1 → A, 2 → B...
                range_notation = f"{col_letter}2:{col_letter}{len(df)+1}"

                # Best odds (lowest value)
                rules.append(
                    ConditionalFormatRule(
                        ranges=[ws.range(range_notation)],
                        booleanRule={
                            "condition": BooleanCondition("NUMBER_EQ", ["=MIN($%s$2:$%s$%d)" % (col_letter, col_letter, len(df)+1)]),
                            "format": best_odds_fmt,
                        },
                    )
                )
                # Worst odds (highest value)
                rules.append(
                    ConditionalFormatRule(
                        ranges=[ws.range(range_notation)],
                        booleanRule={
                            "condition": BooleanCondition("NUMBER_EQ", ["=MAX($%s$2:$%s$%d)" % (col_letter, col_letter, len(df)+1)]),
                            "format": worst_odds_fmt,
                        },
                    )
                )

        if rules:
            ws.format(rules)

        print(f"✅ Updated {tab_name} with {len(df)} rows.")

    except Exception as e:
        print(f"❌ Error updating {tab_name}: {e}")

# =========================
# Main Loop
# =========================
for sport, tab_name in MAJOR_SPORTS.items():
    try:
        print(f"📊 Fetching {sport}...")
        odds_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
        params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h,spreads,totals"}
        resp = requests.get(odds_url, params=params)

        if resp.status_code != 200:
            print(f"⚠️ API error {sport}: {resp.json()}")
            continue

        data = resp.json()
        if not data:
            print(f"ℹ️ No odds data for {sport}")
            continue

        df = pd.json_normalize(data)
        df.columns = [col.replace(".", "_") for col in df.columns]

        update_sheet(df, tab_name)

    except Exception as e:
        print(f"❌ Failed {sport}: {e}")
