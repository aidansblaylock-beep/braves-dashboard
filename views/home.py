import html
import requests
import pandas as pd
import streamlit as st
from datetime import date, datetime
from data import load_roster

BASE_URL = "https://statsapi.mlb.com/api/v1"
BRAVES_ID = 144
NL_EAST_ID = 204

# Minimums so tiny samples can't lead the rate stats (adjust to taste)
MIN_AB = 100
MIN_IP = 30

STYLE = """
<style>
/* Standings table */
.stand-wrap { overflow-x: auto; }
.stand-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.stand-table th {
    text-align: right; font-size: 0.68rem; letter-spacing: 0.07em; text-transform: uppercase;
    color: #5b6b82; border-bottom: 2px solid #0b1f3a; padding: 8px 10px; white-space: nowrap;
}
.stand-table td {
    text-align: right; padding: 10px; border-bottom: 1px solid #eef1f5; color: #0b1f3a;
    font-variant-numeric: tabular-nums; white-space: nowrap;
}
.stand-table th:first-child, .stand-table td:first-child { text-align: left; }
.stand-table tr.me td { background: #fdecee; font-weight: 800; }
.stand-table tr.me td:first-child { border-left: 4px solid #d6001c; }

/* Recent form and results */
.form-row { display: flex; gap: 5px; margin: 6px 0 12px; }
.chip {
    width: 26px; height: 26px; border-radius: 6px; color: #fff; font-weight: 800;
    font-size: 0.75rem; display: flex; align-items: center; justify-content: center;
}
.chip.w { background: #2e9e5b; }
.chip.l { background: #d6001c; }
.game-row {
    display: flex; align-items: center; gap: 12px; padding: 9px 0;
    border-bottom: 1px solid #eef1f5; font-size: 0.9rem; color: #0b1f3a;
}
.game-row .date { color: #5b6b82; width: 54px; font-size: 0.8rem; }
.game-row .result { font-weight: 800; width: 62px; }
.game-row .result.w { color: #2e9e5b; }
.game-row .result.l { color: #d6001c; }
.next-card { background: #0b1f3a; border-radius: 8px; padding: 12px 16px; margin-top: 14px; }
.next-card .nl { font-size: 0.68rem; letter-spacing: 0.08em; color: #9fb0c8; text-transform: uppercase; }
.next-card .nv { font-weight: 800; font-size: 1.05rem; color: #ffffff; }

/* Team leader cards */
.lc-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin-bottom: 14px; }
.lc {
    background: #ffffff; border: 1px solid #e3e8ef; border-top: 4px solid #0b1f3a;
    border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(11, 31, 58, 0.06);
}
.lc-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; color: #5b6b82; text-transform: uppercase; margin-bottom: 6px; }
.lc-top {
    display: flex; justify-content: space-between; align-items: baseline; gap: 8px;
    margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid #eef1f5;
}
.lc-name { font-weight: 800; color: #0b1f3a; font-size: 1rem; }
.lc-value { font-weight: 800; color: #d6001c; font-size: 1.6rem; }
.lc-row { display: flex; justify-content: space-between; font-size: 0.85rem; color: #44556d; padding: 2px 0; }
.lc-row b { color: #0b1f3a; }
.lc-empty { color: #8a96a6; font-size: 0.9rem; }
.lc-top { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; padding-bottom: 10px; border-bottom: 1px solid #eef1f5; }
.lc-photo {
    width: 56px; height: 56px; border-radius: 50%; object-fit: cover; object-position: top;
    background: #e3e8ef; border: 2px solid #ffffff; box-shadow: 0 0 0 1px #d5dce6; flex-shrink: 0;
}
.lc-name { flex: 1; font-weight: 800; color: #0b1f3a; font-size: 1rem; line-height: 1.2; }
.lc-value { font-weight: 800; color: #d6001c; font-size: 1.6rem; }
</style>
"""


def short_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d:%b} {d.day}"


# ---------- Data ----------
@st.cache_data(ttl=900, show_spinner=False)
def load_standings(season):
    resp = requests.get(
        f"{BASE_URL}/standings",
        params={"leagueId": "103,104", "season": season, "standingsTypes": "regularSeason"},
        timeout=20,
    )
    resp.raise_for_status()
    rows = []
    for record in resp.json().get("records", []):
        if record["division"]["id"] != NL_EAST_ID:
            continue
        for t in record["teamRecords"]:
            splits = {
                s.get("type"): f"{s.get('wins')}-{s.get('losses')}"
                for s in t.get("records", {}).get("splitRecords", [])
            }
            rows.append({
                "id": t["team"]["id"],
                "Team": t["team"]["name"],
                "Rank": int(t["divisionRank"]),
                "W": t["wins"],
                "L": t["losses"],
                "PCT": t["winningPercentage"],
                "GB": t["gamesBack"],
                "Home": splits.get("home", "-"),
                "Away": splits.get("away", "-"),
                "L10": splits.get("lastTen", "-"),
                "Strk": t.get("streak", {}).get("streakCode", ""),
                "RD": t.get("runDifferential", ""),
            })
    df = pd.DataFrame(rows)
    return df.sort_values("Rank") if not df.empty else df


@st.cache_data(ttl=900, show_spinner=False)
def load_schedule(season):
    resp = requests.get(
        f"{BASE_URL}/schedule",
        params={"sportId": 1, "teamId": BRAVES_ID, "season": season,
                "gameType": "R", "hydrate": "team"},
        timeout=20,
    )
    resp.raise_for_status()
    games = []
    for d in resp.json().get("dates", []):
        for g in d["games"]:
            home, away = g["teams"]["home"], g["teams"]["away"]
            is_home = home["team"]["id"] == BRAVES_ID
            us, them = (home, away) if is_home else (away, home)
            games.append({
                "Date": d["date"],
                "Opp": them["team"].get("abbreviation") or them["team"]["name"],
                "Where": "vs" if is_home else "@",
                "State": g["status"]["abstractGameState"],
                "Braves": us.get("score"),
                "OppScore": them.get("score"),
            })
    return pd.DataFrame(games, columns=["Date", "Opp", "Where", "State", "Braves", "OppScore"])


# ---------- HTML builders ----------
def standings_html(df):
    cols = ["Team", "W", "L", "PCT", "GB", "Home", "Away", "L10", "Strk", "RD"]
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for _, r in df.iterrows():
        cls = ' class="me"' if r["id"] == BRAVES_ID else ""
        cells = "".join("<td>" + html.escape(str(r[c])) + "</td>" for c in cols)
        body += "<tr" + cls + ">" + cells + "</tr>"
    return ('<div class="stand-wrap"><table class="stand-table"><thead><tr>' + head +
            "</tr></thead><tbody>" + body + "</tbody></table></div>")


def form_html(finals):
    chips = ""
    for _, g in finals.iterrows():
        won = g["Braves"] > g["OppScore"]
        cls = "w" if won else "l"
        letter = "W" if won else "L"
        chips += '<div class="chip ' + cls + '">' + letter + "</div>"
    return '<div class="form-row">' + chips + "</div>"


def results_html(finals):
    rows = ""
    for _, g in finals.iloc[::-1].head(5).iterrows():
        won = g["Braves"] > g["OppScore"]
        cls = "w" if won else "l"
        letter = "W" if won else "L"
        score = str(int(g["Braves"])) + "-" + str(int(g["OppScore"]))
        rows += (
            '<div class="game-row"><span class="date">' + short_date(g["Date"]) + "</span>"
            '<span class="result ' + cls + '">' + letter + " " + score + "</span>"
            "<span>" + g["Where"] + " " + html.escape(str(g["Opp"])) + "</span></div>"
        )
    return rows


def fmt3(x):
    return f"{x:.3f}".lstrip("0")        # 0.283 -> .283


def top3(df, col, ascending=False, kind="int"):
    d = df.dropna(subset=[col]).sort_values(col, ascending=ascending).head(3)
    fmt = {"int": "{:.0f}", "rate": None, "era": "{:.2f}"}[kind]
    return [
        (r["Player"], fmt3(r[col]) if kind == "rate" else fmt.format(r[col]), r["Photo"])
        for _, r in d.iterrows()
    ]


def leader_card_html(label, leaders):
    if not leaders:
        return ('<div class="lc"><div class="lc-label">' + label +
                '</div><div class="lc-empty">No data</div></div>')
    top_name, top_value, top_photo = leaders[0]
    rest = "".join(
        '<div class="lc-row"><span>' + html.escape(n) + "</span><b>" + v + "</b></div>"
        for n, v, _ in leaders[1:]
    )
    return (
        '<div class="lc"><div class="lc-label">' + label + "</div>"
        '<div class="lc-top"><img class="lc-photo" src="' + top_photo + '" alt="">'
        '<span class="lc-name">' + html.escape(top_name) + "</span>"
        '<span class="lc-value">' + top_value + "</span></div>" + rest + "</div>"
    )


# ---------- Page ----------
st.markdown(STYLE, unsafe_allow_html=True)

today = date.today()
default_season = today.year if today.month >= 3 else today.year - 1

title_col, season_col = st.columns([5, 1])
title_col.header("Atlanta Braves")
season = season_col.selectbox("Season", list(range(default_season, 2014, -1)), key="home_season")

standings = load_standings(season)
schedule = load_schedule(season)

# ----- At a glance -----
braves = standings[standings["id"] == BRAVES_ID] if not standings.empty else standings
if not braves.empty:
    b = braves.iloc[0]
    m = st.columns(5)
    m[0].metric("Games Back", b["GB"])
    m[1].metric("Run Differential", b["RD"])
    m[2].metric("Home", b["Home"])
    m[3].metric("Away", b["Away"])
    m[4].metric("Last 10", b["L10"])

st.write("")

# ----- Standings and recent results -----
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("NL East Standings")
    if standings.empty:
        st.info("No standings available for this season yet.")
    else:
        st.markdown(standings_html(standings), unsafe_allow_html=True)

with right:
    st.subheader("Recent Results")
    finals = schedule[
        (schedule["State"] == "Final") & schedule["Braves"].notna() & schedule["OppScore"].notna()
    ]
    if finals.empty:
        st.info("No completed games yet.")
    else:
        st.caption("Last 10 games, oldest to newest")
        st.markdown(form_html(finals.tail(10)), unsafe_allow_html=True)
        st.markdown(results_html(finals), unsafe_allow_html=True)

# ----- Team leaders -----
st.subheader("Team Leaders")
hitters, pitchers = load_roster(season, "fullSeason")
qual_hit = hitters[hitters["AB"] >= MIN_AB]
qual_pit = pitchers[pitchers["IP"] >= MIN_IP]

cards = [
    leader_card_html("Home Runs", top3(hitters, "HR")),
    leader_card_html("Batting Avg", top3(qual_hit, "AVG", kind="rate")),
    leader_card_html("RBI", top3(hitters, "RBI")),
    leader_card_html("OPS", top3(qual_hit, "OPS", kind="rate")),
    leader_card_html("ERA", top3(qual_pit, "ERA", ascending=True, kind="era")),
    leader_card_html("Wins", top3(pitchers, "W")),
    leader_card_html("Strikeouts", top3(pitchers, "SO")),
    leader_card_html("Saves", top3(pitchers, "SV")),
]
st.markdown('<div class="lc-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)

st.caption(f"Batting average and OPS need {MIN_AB}+ AB; ERA needs {MIN_IP}+ IP. Data: MLB Stats API.")