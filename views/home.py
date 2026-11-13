import html
import requests
import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta
from data import (
    load_roster, load_transactions, load_todays_games,
    load_team_snapshot, today_eastern, NEWS_LINKS,
)

BASE_URL = "https://statsapi.mlb.com/api/v1"
BRAVES_ID = 144

# Division IDs and the order the arrows step through them
DIVISIONS = {
    204: "NL East", 205: "NL Central", 203: "NL West",
    201: "AL East", 202: "AL Central", 200: "AL West",
}
NL_DIVS = {203, 204, 205}
VIEWS = [
    "NL East", "NL Central", "NL West", "NL Wild Card",
    "AL East", "AL Central", "AL West", "AL Wild Card",
]
DIV_ID_BY_NAME = {name: div_id for div_id, name in DIVISIONS.items()}

DIV_COLS = ["Team", "W", "L", "PCT", "GB", "Home", "Away", "L10", "Strk", "RD"]
WC_COLS = ["Team", "Status", "W", "L", "PCT", "WCGB", "L10", "Strk", "RD"]

# Minimums so tiny samples can't lead the rate stats (adjust to taste)
MIN_AB = 100
MIN_IP = 30

STYLE = """
<style>
/* Section titles with arrow buttons */
.sec-title { font-size: 1.75rem; font-weight: 700; color: #0b1f3a; line-height: 1.2; }
.sec-rule { border-bottom: 2px solid #e3e8ef; margin: 0.3rem 0 0.9rem; }

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
.stand-table tr.cutoff td { border-bottom: 2px dashed #d6001c; }

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

/* Team leader cards */
.lc-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin-bottom: 14px; }
.lc {
    background: #ffffff; border: 1px solid #e3e8ef; border-top: 4px solid #0b1f3a;
    border-radius: 8px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(11, 31, 58, 0.06);
}
.lc-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; color: #5b6b82; text-transform: uppercase; margin-bottom: 6px; }
.lc-top { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; padding-bottom: 10px; border-bottom: 1px solid #eef1f5; }
.lc-photo {
    width: 56px; height: 56px; border-radius: 50%; object-fit: cover; object-position: top;
    background: #e3e8ef; border: 2px solid #ffffff; box-shadow: 0 0 0 1px #d5dce6; flex-shrink: 0;
}
.lc-name { flex: 1; font-weight: 800; color: #0b1f3a; font-size: 1rem; line-height: 1.2; }
.lc-value { font-weight: 800; color: #d6001c; font-size: 1.6rem; }
.lc-row { display: flex; justify-content: space-between; font-size: 0.85rem; color: #44556d; padding: 2px 0; }
.lc-row b { color: #0b1f3a; }
.lc-empty { color: #8a96a6; font-size: 0.9rem; }

/* Latest moves and reading list */
.move-row {
    display: flex; gap: 12px; padding: 9px 0; border-bottom: 1px solid #eef1f5;
    font-size: 0.88rem; color: #0b1f3a; line-height: 1.35;
}
.move-row .date { color: #5b6b82; width: 54px; font-size: 0.8rem; flex-shrink: 0; }
.link-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
.link-card {
    display: flex; flex-direction: column; gap: 2px; padding: 12px 14px; background: #ffffff;
    border: 1px solid #e3e8ef; border-left: 4px solid #0b1f3a; border-radius: 8px;
    text-decoration: none; transition: border-color 0.15s, transform 0.15s;
}
.link-card:hover { border-left-color: #d6001c; transform: translateY(-1px); }
.link-card .ln { font-weight: 800; color: #0b1f3a; font-size: 0.95rem; }
.link-card .lnote { color: #5b6b82; font-size: 0.8rem; }

/* Today's game card */
.tg-card {
    background: #ffffff; border: 1px solid #e3e8ef; border-left: 4px solid #d6001c;
    border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;
    box-shadow: 0 1px 2px rgba(11, 31, 58, 0.06);
}
.tg-top { display: flex; justify-content: space-between; align-items: center; }
.tg-label { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; color: #5b6b82; text-transform: uppercase; }
.tg-status { font-size: 0.8rem; font-weight: 800; color: #0b1f3a; }
.tg-status.live { color: #d6001c; }
.tg-status.w { color: #2e9e5b; }
.tg-status.l { color: #d6001c; }
.tg-matchup { font-size: 1.3rem; font-weight: 800; color: #0b1f3a; margin: 4px 0 6px; }
.tg-sub { font-size: 0.9rem; color: #44556d; }
.tg-score { display: flex; gap: 14px; font-size: 1.6rem; font-weight: 800; color: #0b1f3a; font-variant-numeric: tabular-nums; }
.tg-pitchers { margin-top: 8px; padding-top: 8px; border-top: 1px solid #eef1f5; }
.tg-plabel { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; color: #5b6b82; text-transform: uppercase; margin-bottom: 4px; }
.tg-prow { display: flex; gap: 10px; font-size: 0.9rem; color: #44556d; padding: 2px 0; }
.tg-prow span { width: 40px; color: #5b6b82; font-weight: 700; }
.tg-prow b { color: #0b1f3a; }
</style>
"""


def short_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d:%b} {d.day}"


# ---------- Data ----------
@st.cache_data(ttl=900, show_spinner=False)
def load_all_standings(season):
    """Every team in baseball, tagged with its division and league."""
    resp = requests.get(
        f"{BASE_URL}/standings",
        params={"leagueId": "103,104", "season": season, "standingsTypes": "regularSeason"},
        timeout=20,
    )
    resp.raise_for_status()
    rows = []
    for record in resp.json().get("records", []):
        div_id = record["division"]["id"]
        for t in record["teamRecords"]:
            splits = {
                s.get("type"): f"{s.get('wins')}-{s.get('losses')}"
                for s in t.get("records", {}).get("splitRecords", [])
            }
            rows.append({
                "id": t["team"]["id"],
                "Team": t["team"]["name"],
                "Div": div_id,
                "League": "NL" if div_id in NL_DIVS else "AL",
                "Rank": int(t["divisionRank"]),
                "W": t["wins"],
                "L": t["losses"],
                "PCT": t["winningPercentage"],
                "PCTn": float(t["winningPercentage"]),
                "GB": t["gamesBack"],
                "Home": splits.get("home", "-"),
                "Away": splits.get("away", "-"),
                "L10": splits.get("lastTen", "-"),
                "Strk": t.get("streak", {}).get("streakCode", ""),
                "RD": t.get("runDifferential", ""),
            })
    return pd.DataFrame(rows)


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


def wild_card_table(df, league, season):
    """Only the teams in the wild card race (division leaders are left out)."""
    lg = df[df["League"] == league]
    rest = lg[lg["Rank"] != 1].sort_values(["PCTn", "W"], ascending=False).copy()
    spots = 3 if season >= 2022 else 2

    if len(rest) >= spots:
        cut = rest.iloc[spots - 1]
        games_back = ((cut["W"] - rest["W"]) + (rest["L"] - cut["L"])) / 2
    else:
        games_back = pd.Series(0.0, index=rest.index)

    def fmt(x):
        if x == 0:
            return "-"
        return f"+{abs(x):.1f}" if x < 0 else f"{x:.1f}"

    rest["WCGB"] = [fmt(x) for x in games_back]
    rest["Status"] = [f"WC{i + 1}" if i < spots else "" for i in range(len(rest))]

    return rest.reset_index(drop=True), spots - 1


# ---------- HTML builders ----------
def table_html(df, cols, cutoff_after=None):
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for pos, (_, r) in enumerate(df.iterrows()):
        classes = []
        if r["id"] == BRAVES_ID:
            classes.append("me")
        if cutoff_after is not None and pos == cutoff_after:
            classes.append("cutoff")
        cls = ' class="' + " ".join(classes) + '"' if classes else ""
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

# Types of moves to hide from the Home card (minor league shuffling). Edit to taste.
NOISE_WORDS = ("Assigned", "Optioned", "Recalled", "Status Change", "Rehab")


def latest_moves(n=6):
    end = date.today()
    df = load_transactions(BRAVES_ID, end - timedelta(days=60), end)
    if df.empty:
        return df
    mask = ~df["Type"].str.contains("|".join(NOISE_WORDS), case=False, na=False)
    return df[mask].head(n)


def moves_html(df):
    rows = ""
    for _, r in df.iterrows():
        rows += (
            '<div class="move-row"><span class="date">' + short_date(r["Date"]) + "</span>"
            "<span>" + html.escape(str(r["Description"])) + "</span></div>"
        )
    return rows


def links_html():
    items = ""
    for link in NEWS_LINKS:
        items += (
            '<a class="link-card" href="' + html.escape(link["url"]) +
            '" target="_blank" rel="noopener noreferrer">'
            '<span class="ln">' + html.escape(link["name"]) + "</span>"
            '<span class="lnote">' + html.escape(link.get("note", "")) + "</span></a>"
        )
    return '<div class="link-grid">' + items + "</div>"

def game_card_html(g):
    """One game as a card. g is one dict from load_todays_games()."""
    where = "vs" if g["is_home"] else "@"
    us = html.escape(g["us_abbr"])
    them = html.escape(g["them_abbr"] or g["them_name"])
    matchup = "Braves " + where + " " + html.escape(g["them_name"])
    has_score = g["us_score"] is not None and g["them_score"] is not None
    pitchers = ""

    if g["state"] == "Live" and has_score:
        status = "LIVE" + (" · " + g["inning"] if g["inning"] else "")
        status_cls = "live"
    elif g["state"] == "Final" and has_score:
        won = g["us_score"] > g["them_score"]
        status = "FINAL · " + ("W" if won else "L")
        status_cls = "w" if won else "l"
    else:
        # Not started yet (or postponed, delayed, etc.): show start time + probable pitchers
        status = g["start_text"]
        if g["detail"] not in ("Scheduled", "Pre-Game"):
            status += " · " + g["detail"]
        status_cls = ""
        us_p = html.escape(g["us_pitcher"] or "TBD")
        them_p = html.escape(g["them_pitcher"] or "TBD")
        pitchers = (
            '<div class="tg-pitchers"><div class="tg-plabel">Probable pitchers</div>'
            '<div class="tg-prow"><span>' + us + "</span><b>" + us_p + "</b></div>"
            '<div class="tg-prow"><span>' + them + "</span><b>" + them_p + "</b></div></div>"
        )

    score = ""
    if has_score:
        score = (
            '<div class="tg-score"><span>' + us + " " + str(g["us_score"]) + "</span>"
            "<span>–</span><span>" + them + " " + str(g["them_score"]) + "</span></div>"
        )

    return (
        '<div class="tg-card"><div class="tg-top">'
        '<span class="tg-label">Today&rsquo;s Game</span>'
        '<span class="tg-status ' + status_cls + '">' + html.escape(status) + "</span></div>"
        '<div class="tg-matchup">' + matchup + "</div>" + score + pitchers + "</div>"
    )


def off_day_html(next_game):
    extra = ""
    if next_game:
        extra = '<div class="tg-sub">Next game: ' + html.escape(next_game) + "</div>"
    return (
        '<div class="tg-card"><div class="tg-top">'
        '<span class="tg-label">Today&rsquo;s Game</span></div>'
        '<div class="tg-matchup">No game today</div>' + extra + "</div>"
    )

# ---------- Arrow buttons for the standings ----------
if "stand_view" not in st.session_state:
    st.session_state["stand_view"] = 0


def step_view(delta):
    st.session_state["stand_view"] = (st.session_state["stand_view"] + delta) % len(VIEWS)


# ---------- Page ----------
st.markdown(STYLE, unsafe_allow_html=True)

today = date.today()
default_season = today.year if today.month >= 3 else today.year - 1

title_col, season_col = st.columns([5, 1])
title_col.header("Atlanta Braves")
season = season_col.selectbox("Season", list(range(default_season, 2014, -1)), key="home_season")

all_standings = load_all_standings(season)
schedule = load_schedule(season)

# ----- At a glance -----
braves = all_standings[all_standings["id"] == BRAVES_ID] if not all_standings.empty else all_standings
if not braves.empty:
    b = braves.iloc[0]
    m = st.columns(5)
    m[0].metric("Games Back", b["GB"])
    m[1].metric("Run Differential", b["RD"])
    m[2].metric("Home", b["Home"])
    m[3].metric("Away", b["Away"])
    m[4].metric("Last 10", b["L10"])

st.write("")

# ----- Today's game -----
try:
    todays_games = load_todays_games(today_eastern())
except Exception:
    todays_games = None

if todays_games is None:
    st.info("Couldn't load today's game right now.")
elif not todays_games:
    next_game = load_team_snapshot(default_season)["next"]
    st.markdown(off_day_html(next_game), unsafe_allow_html=True)
else:
    for g in todays_games:
        st.markdown(game_card_html(g), unsafe_allow_html=True)

# ----- Standings and recent results -----
left, right = st.columns([3, 2], gap="large")

with left:
    view = VIEWS[st.session_state["stand_view"]]
    heading = view if "Wild Card" in view else f"{view} Standings"

    head_col, prev_col, next_col = st.columns([6, 1, 1], vertical_alignment="center")
    head_col.markdown(f'<div class="sec-title">{heading}</div>', unsafe_allow_html=True)
    prev_col.button("◀", key="stand_prev", on_click=step_view, args=(-1,), use_container_width=True)
    next_col.button("▶", key="stand_next", on_click=step_view, args=(1,), use_container_width=True)
    st.markdown('<div class="sec-rule"></div>', unsafe_allow_html=True)

    if all_standings.empty:
        st.info("No standings available for this season yet.")
    elif "Wild Card" in view:
        league = view[:2]
        table, cutoff = wild_card_table(all_standings, league, season)
        st.markdown(table_html(table, WC_COLS, cutoff_after=cutoff), unsafe_allow_html=True)
    else:
        div_df = all_standings[all_standings["Div"] == DIV_ID_BY_NAME[view]].sort_values("Rank")
        st.markdown(table_html(div_df, DIV_COLS), unsafe_allow_html=True)

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

# ----- Latest moves and reading list -----
moves_col, links_col = st.columns(2, gap="large")

with moves_col:
    st.subheader("Latest Moves")
    try:
        moves = latest_moves()
    except Exception:
        moves = None
    if moves is None:
        st.info("Couldn't load moves right now.")
    elif moves.empty:
        st.info("No recent moves.")
    else:
        st.markdown(moves_html(moves), unsafe_allow_html=True)
        st.caption("Full list under Recent Moves on the Braves Roster page.")

with links_col:
    st.subheader("Reading List")
    st.markdown(links_html(), unsafe_allow_html=True)

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