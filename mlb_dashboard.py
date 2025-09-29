import requests
import pandas as pd
import datetime as dt
from pybaseball import pitching_stats, batting_stats
import gspread
from google.oauth2.service_account import Credentials

# -----------------------
# CONFIG
# -----------------------
ODDS_API_KEY = "ac062d318b462f4a2efe7b5ce7bf8cdb"  # ✅ Correct Odds API key
SPREADSHEET_NAME = "MLB_Dashboard"

# Google Sheets auth
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
client = gspread.authorize(creds)

# -----------------------
# 1. Fetch MLB Odds
# -----------------------
def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    url += f"?regions=us&markets=h2h,totals,spreads&oddsFormat=decimal&apiKey={ODDS_API_KEY}"
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
            "Home ML": f"{float(moneyline[0]['price']):.0%}" if len(moneyline) > 0 else "N/A",
            "Away ML": f"{float(moneyline[1]['price']):.0%}" if len(moneyline) > 1 else "N/A",
            "Run Line Home": spreads[0]["price"] if len(spreads) > 0 else "N/A",
            "Run Line Away": spreads[1]["price"] if len(spreads) > 1 else "N/A",
            "Total Over": totals[0]["price"] if len(totals) > 0 else "N/A",
            "Total Under": totals[1]["price"] if len(totals) > 1 else "N/A",
            "Last Updated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    return pd.DataFrame(games)

# -----------------------
# 2. Pitcher Stats
# -----------------------
def get_pitcher_stats():
    df = pitching_stats(2025)
    return df[["Name", "Team", "ERA", "WHIP", "FIP", "IP"]]

# -----------------------
# 3. Hitter Stats
# -----------------------
def get_hitter_stats():
    df = batting_stats(2025)
    return df[["Name", "Team", "AVG", "OBP", "SLG", "OPS", "HR", "RBI"]]

# -----------------------
# 4. Upload to Google Sheets
# -----------------------
def upload_to_sheets(df, sheet_name):
    try:
        sh = client.open(SPREADSHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sh = client.create(SPREADSHEET_NAME)
        sh.share(None, perm_type="anyone", role="writer")

    try:
        worksheet = sh.worksheet(sheet_name)
        sh.del_worksheet(worksheet)
    except:
        pass

    worksheet = sh.add_worksheet(title=sheet_name, rows=str(len(df)+10), cols=str(len(df.columns)+10))
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    games_df = fetch_odds()
    pitchers_df = get_pitcher_stats()
    hitters_df = get_hitter_stats()

    upload_to_sheets(games_df, "Games")
    upload_to_sheets(pitchers_df, "Pitchers")
    upload_to_sheets(hitters_df, "Hitters")

    print("✅ MLB Dashboard updated to Google Sheets!")
