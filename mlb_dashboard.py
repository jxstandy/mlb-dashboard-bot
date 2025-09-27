import os
import requests
import pandas as pd
import datetime as dt
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pybaseball import pitching_stats, batting_stats, statcast

# --------------------------
# 1. Auth Google Sheets
# --------------------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
creds_json = os.environ["GOOGLE_SHEETS_CRED"]
with open("creds.json", "w") as f:
    f.write(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
sheet = client.open_by_key(SHEET_ID)

# --------------------------
# 2. Odds API
# --------------------------
API_KEY = os.environ["ODDS_API_KEY"]

def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/?regions=us&markets=h2h,totals,spreads&oddsFormat=decimal&apiKey={API_KEY}"
    r = requests.get(url)
    data = r.json()
    games, upcoming = [], []

    ct = pytz.timezone("America/Chicago")
    now_ct = dt.datetime.now(ct)

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

        # convert to probability %
        def odds_to_prob(odds):
            try:
                return round((1/float(odds))*100,2)
            except:
                return "N/A"

        home_ml = odds_to_prob(moneyline[0]["price"]) if len(moneyline) > 0 else "N/A"
        away_ml = odds_to_prob(moneyline[1]["price"]) if len(moneyline) > 1 else "N/A"

        start_time = pd.to_datetime(game["commence_time"]).tz_convert(ct)

        row = {
            "Game": f"{home} vs {away}",
            "Start Time": start_time.strftime("%Y-%m-%d %I:%M %p"),
            "Home Team": home,
            "Away Team": away,
            "Home ML %": home_ml,
            "Away ML %": away_ml,
            "Run Line Home": spreads[0]["price"] if len(spreads) > 0 else "N/A",
            "Run Line Away": spreads[1]["price"] if len(spreads) > 1 else "N/A",
            "Total Over": totals[0]["price"] if len(totals) > 0 else "N/A",
            "Total Under": totals[1]["price"] if len(totals) > 1 else "N/A",
            "Last Updated": now_ct.strftime("%Y-%m-%d %H:%M:%S")
        }

        if start_time.date() == now_ct.date():
            games.append(row)
        elif start_time.date() > now_ct.date():
            upcoming.append(row)

    return pd.DataFrame(games), pd.DataFrame(upcoming)

games_df, upcoming_df = fetch_odds()

# --------------------------
# 3. Season Stats
# --------------------------
pitching_df = pitching_stats(2024)[["Name","Team","ERA","WHIP","FIP","IP","SO","BB","HR"]]
hitting_df = batting_stats(2024)[["Name","Team","AVG","OBP","SLG","OPS","HR","RBI","SO","BB"]]

# --------------------------
# 4. Last 5 Games
# --------------------------
def last5_pitchers():
    today = dt.datetime.now().strftime("%Y-%m-%d")
    df = statcast(start_dt=(dt.datetime.now()-dt.timedelta(days=10)).strftime("%Y-%m-%d"),
                  end_dt=today)
    return df.groupby("pitcher").tail(5)

def last5_hitters():
    today = dt.datetime.now().strftime("%Y-%m-%d")
    df = statcast(start_dt=(dt.datetime.now()-dt.timedelta(days=10)).strftime("%Y-%m-%d"),
                  end_dt=today)
    return df.groupby("batter").tail(5)

pitchers5_df = last5_pitchers()
hitters5_df = last5_hitters()

# --------------------------
# 5. Write to Sheets
# --------------------------
def write_sheet(df, tab):
    try:
        ws = sheet.worksheet(tab)
        sheet.del_worksheet(ws)
    except:
        pass
    ws = sheet.add_worksheet(title=tab, rows=str(len(df)+5), cols="20")
    ws.update([df.columns.values.tolist()] + df.values.tolist())

write_sheet(games_df, "Games")
write_sheet(upcoming_df, "Upcoming Games")
write_sheet(pitching_df, "Pitcher Stats")
write_sheet(hitting_df, "Hitter Stats")
write_sheet(pitchers5_df, "Last 5 Pitchers")
write_sheet(hitters5_df, "Last 5 Hitters")

print("✅ Google Sheet updated successfully")
