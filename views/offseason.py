import requests
import pandas as pd
import streamlit as st
from datetime import date, timedelta
from data import headshot_url

BASE_URL = "https://statsapi.mlb.com/api/v1"
COLUMNS = ["Photo", "Date", "Player", "Type", "Team", "Description"]


@st.cache_data(ttl=86400, show_spinner=False)
def load_teams(season):
    resp = requests.get(f"{BASE_URL}/teams", params={"sportId": 1, "season": season}, timeout=20)
    resp.raise_for_status()
    teams = {t["name"]: t["id"] for t in resp.json()["teams"]}
    return dict(sorted(teams.items()))


@st.cache_data(ttl=900, show_spinner="Loading transactions...")
def load_transactions(team_id, start, end):
    params = {"startDate": start.strftime("%m/%d/%Y"), "endDate": end.strftime("%m/%d/%Y")}
    if team_id:
        params["teamId"] = team_id
    else:
        params["sportId"] = 1
    resp = requests.get(f"{BASE_URL}/transactions", params=params, timeout=30)
    resp.raise_for_status()

    rows = []
    for t in resp.json().get("transactions", []):
        person = t.get("person") or {}
        team = t.get("toTeam") or t.get("fromTeam") or {}
        rows.append({
            "Photo": headshot_url(person["id"]) if person.get("id") else "",
            "Date": str(t.get("date", ""))[:10],
            "Player": person.get("fullName", ""),
            "Type": t.get("typeDesc", ""),
            "Team": team.get("name", ""),
            "Description": t.get("description", ""),
        })
    df = pd.DataFrame(rows, columns=COLUMNS)
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


st.header("Offseason")
st.caption("Official MLB transactions: signings, trades, waiver claims and roster moves.")

today = date.today()
teams = load_teams(today.year)
team_names = ["All MLB"] + list(teams)
default_index = team_names.index("Atlanta Braves") if "Atlanta Braves" in team_names else 0

c1, c2, c3 = st.columns([2, 1, 1])
team_choice = c1.selectbox("Team", team_names, index=default_index)
start = c2.date_input("From", value=today - timedelta(days=30), max_value=today)
end = c3.date_input("To", value=today, max_value=today)

if start > end:
    st.warning("The start date needs to be on or before the end date.")
    st.stop()

if team_choice == "All MLB" and (end - start).days > 14:
    st.info("League-wide results are large, so only the most recent 14 days are shown.")
    start = end - timedelta(days=14)

try:
    df = load_transactions(None if team_choice == "All MLB" else teams[team_choice], start, end)
except Exception:
    st.warning("Couldn't load transactions right now. Try again in a minute.")
    st.stop()

if df.empty:
    st.info("No transactions found for that team and date range.")
    st.stop()

f1, f2 = st.columns([2, 1])
types = sorted(t for t in df["Type"].unique() if t)
chosen = f1.multiselect("Type", types, placeholder="All types")
query = f2.text_input("Search player or description")

if chosen:
    df = df[df["Type"].isin(chosen)]
if query:
    q = query.lower()
    mask = (df["Player"].str.lower().str.contains(q, na=False)
            | df["Description"].str.lower().str.contains(q, na=False))
    df = df[mask]

m = st.columns(3)
m[0].metric("Moves", len(df))
m[1].metric("Signings", int(df["Type"].str.contains("Signed", case=False, na=False).sum()))
m[2].metric("Trades", int(df["Type"].str.contains("Trade", case=False, na=False).sum()))

if df.empty:
    st.info("No transactions match those filters.")
    st.stop()

st.dataframe(
    df.head(500),
    hide_index=True,
    use_container_width=True,
    row_height=44,
    column_config={
        "Photo": st.column_config.ImageColumn("", width="small"),
        "Description": st.column_config.TextColumn("Description", width="large"),
    },
)
if len(df) > 500:
    st.caption("Showing the 500 most recent moves.")
st.caption("Data: MLB Stats API (official transactions). Refreshes every 15 minutes.")