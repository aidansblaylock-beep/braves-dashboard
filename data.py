import requests
import pandas as pd
import streamlit as st
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_URL = "https://statsapi.mlb.com/api/v1"
BRAVES_ID = 144
def _flag(name):
    try:
        value = st.secrets.get(name, False)
    except Exception:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def safe_mode_on():
    return _flag("PUBLIC_SAFE_MODE")


_PLACEHOLDER = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'>"
    "<rect width='120' height='120' fill='%23e3e8ef'/>"
    "<circle cx='60' cy='46' r='22' fill='%23b8c3d3'/>"
    "<ellipse cx='60' cy='112' rx='38' ry='34' fill='%23b8c3d3'/></svg>"
)


def headshot_url(player_id, width=120):
    if safe_mode_on():
        return _PLACEHOLDER
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        f"d_people:generic:headshot:67:current.png/w_{width},q_auto:best/"
        f"v1/people/{player_id}/headshot/67/current"
    )

# API field name -> column label shown on the page
HIT_COLS = {
    "gamesPlayed": "G", "atBats": "AB", "hits": "H", "homeRuns": "HR",
    "rbi": "RBI", "baseOnBalls": "BB", "strikeOuts": "SO",
    "avg": "AVG", "obp": "OBP", "slg": "SLG", "ops": "OPS",
}
PIT_COLS = {
    "gamesPlayed": "G", "gamesStarted": "GS", "wins": "W", "losses": "L",
    "saves": "SV", "inningsPitched": "IP", "era": "ERA", "whip": "WHIP",
    "strikeOuts": "SO", "baseOnBalls": "BB", "strikeoutsPer9Inn": "K/9",
}
INFO_COLS = ["Photo", "Player", "#", "Pos", "Status"]

def categorize(status):
    if "Injured" in status:
        return "Injured List"
    if "Minors" in status:
        return "Minors"
    if status == "Active":
        return "Active"
    return "Other"


@st.cache_data(ttl=1800, show_spinner="Loading roster...")
def load_roster(season, roster_type):
    """One API call returns the roster plus each player's season stats."""
    url = f"{BASE_URL}/teams/{BRAVES_ID}/roster"
    params = {
        "rosterType": roster_type,
        "season": season,
        "hydrate": f"person(stats(type=season,season={season},group=[hitting,pitching]))",
    }
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()

    hitters, pitchers = [], []
    for entry in resp.json()["roster"]:
        person = entry["person"]
        info = {
            "Photo": headshot_url(person["id"]),
            "Player": person["fullName"],
            "#": entry.get("jerseyNumber", ""),
            "Pos": entry["position"]["abbreviation"],
            "Status": categorize(entry["status"]["description"]),
        }

        stats = {}
        for s in person.get("stats", []):
            splits = s.get("splits", [])
            if splits:
                stats[s["group"]["displayName"]] = splits[0]["stat"]

        if entry["position"]["type"] == "Pitcher":
            row = dict(info)
            for key, label in PIT_COLS.items():
                row[label] = stats.get("pitching", {}).get(key)
            pitchers.append(row)
        else:
            row = dict(info)
            for key, label in HIT_COLS.items():
                row[label] = stats.get("hitting", {}).get(key)
            hitters.append(row)

    hit_df = pd.DataFrame(hitters, columns=INFO_COLS + list(HIT_COLS.values()))
    pit_df = pd.DataFrame(pitchers, columns=INFO_COLS + list(PIT_COLS.values()))

    for df in (hit_df, pit_df):
        for col in df.columns:
            if col not in INFO_COLS:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return hit_df, pit_df

FAV_FILE = Path(__file__).parent / "favorites.json"


@st.cache_data(ttl=86400, show_spinner="Loading player list...")
def load_player_directory(season):
    """Every MLB player for a season, used for the search dropdown."""
    resp = requests.get(f"{BASE_URL}/sports/1/players", params={"season": season}, timeout=30)
    resp.raise_for_status()
    people = resp.json()["people"]
    df = pd.DataFrame({
        "id": [p["id"] for p in people],
        "name": [p["fullName"] for p in people],
        "pos": [p.get("primaryPosition", {}).get("abbreviation", "") for p in people],
    })
    df["label"] = df["name"] + " (" + df["pos"] + ")"
    return df.sort_values("name").reset_index(drop=True)


def load_favorites():
    if FAV_FILE.exists():
        return json.loads(FAV_FILE.read_text())
    return []


def save_favorites(favs):
    FAV_FILE.write_text(json.dumps(favs, indent=2))


@st.cache_data(ttl=1800, show_spinner="Loading stats...")
def load_player_stats(player_ids, season):
    """Season stats for any list of players (pass ids as a tuple)."""
    params = {
        "personIds": ",".join(str(i) for i in player_ids),
        "hydrate": f"currentTeam,stats(group=[hitting,pitching],type=season,season={season})",
    }
    resp = requests.get(f"{BASE_URL}/people", params=params, timeout=20)
    resp.raise_for_status()

    info_cols = ["Photo", "Player", "Team", "Pos"]
    hitters, pitchers, missing = [], [], []
    for p in resp.json()["people"]:
        info = {
            "Photo": headshot_url(p["id"]),
            "Player": p["fullName"],
            "Team": p.get("currentTeam", {}).get("name", ""),
            "Pos": p.get("primaryPosition", {}).get("abbreviation", ""),
        }
        stats = {}
        for s in p.get("stats", []):
            splits = s.get("splits", [])
            if splits:
                stats[s["group"]["displayName"]] = splits[0]["stat"]

        found = False
        hit = stats.get("hitting")
        if hit and int(hit.get("atBats", 0)) > 0:
            hitters.append({**info, **{lbl: hit.get(k) for k, lbl in HIT_COLS.items()}})
            found = True
        pit = stats.get("pitching")
        if pit:
            pitchers.append({**info, **{lbl: pit.get(k) for k, lbl in PIT_COLS.items()}})
            found = True
        if not found:
            missing.append(p["fullName"])

    hit_df = pd.DataFrame(hitters, columns=info_cols + list(HIT_COLS.values()))
    pit_df = pd.DataFrame(pitchers, columns=info_cols + list(PIT_COLS.values()))
    for df in (hit_df, pit_df):
        for col in df.columns:
            if col not in info_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return hit_df, pit_df, missing

@st.cache_data(ttl=1800, show_spinner=False)
def load_roster_players(season, roster_type="40Man"):
    """Braves roster as a simple list of id / name / position type (no stats, so it's fast)."""
    resp = requests.get(
        f"{BASE_URL}/teams/{BRAVES_ID}/roster",
        params={"rosterType": roster_type, "season": season},
        timeout=20,
    )
    resp.raise_for_status()
    return [
        {
            "id": e["person"]["id"],
            "name": e["person"]["fullName"],
            "type": e["position"]["type"],
        }
        for e in resp.json()["roster"]
    ]
def _ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _short_date(iso):
    from datetime import datetime
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d:%b} {d.day}"


def _braves_games(season):
    resp = requests.get(
        f"{BASE_URL}/schedule",
        params={"sportId": 1, "teamId": BRAVES_ID, "season": season,
                "gameType": "R", "hydrate": "team"},
        timeout=15,
    )
    resp.raise_for_status()
    games = []
    for d in resp.json().get("dates", []):
        for g in d["games"]:
            home, away = g["teams"]["home"], g["teams"]["away"]
            is_home = home["team"]["id"] == BRAVES_ID
            us, them = (home, away) if is_home else (away, home)
            games.append({
                "date": d["date"],
                "opp": them["team"].get("abbreviation") or them["team"]["name"],
                "home": is_home,
                "final": g["status"]["abstractGameState"] == "Final",
                "us": us.get("score"),
                "them": them.get("score"),
            })
    return games


@st.cache_data(ttl=900, show_spinner=False)
def load_team_snapshot(season):
    """Small summary for the header: record, division rank, last game, next game."""
    from datetime import date
    snap = {"record": None, "rank": None, "last": None, "next": None}

    try:
        resp = requests.get(
            f"{BASE_URL}/standings",
            params={"leagueId": "103,104", "season": season, "standingsTypes": "regularSeason"},
            timeout=15,
        )
        for record in resp.json().get("records", []):
            for t in record["teamRecords"]:
                if t["team"]["id"] == BRAVES_ID:
                    snap["record"] = f"{t['wins']}-{t['losses']}"
                    snap["rank"] = _ordinal(int(t["divisionRank"]))
    except Exception:
        pass

    try:
        games = _braves_games(season)
        finals = [g for g in games if g["final"]]
        if finals:
            g = finals[-1]
            if g["us"] is not None and g["them"] is not None:
                result = "W" if g["us"] > g["them"] else "L"
                where = "vs" if g["home"] else "@"
                snap["last"] = f"{result} {g['us']}-{g['them']} {where} {g['opp']}"

        today = str(date.today())
        upcoming = [g for g in games if not g["final"] and g["date"] >= today]
        if not upcoming:
            # Offseason: look at next season's schedule if MLB has posted it
            upcoming = [g for g in _braves_games(season + 1) if not g["final"]]
        if upcoming:
            g = upcoming[0]
            where = "vs" if g["home"] else "@"
            snap["next"] = f"{_short_date(g['date'])} {where} {g['opp']}"
    except Exception:
        pass

    return snap

def editing_enabled():
    """Editing is on locally. Either PUBLIC_MODE or PUBLIC_SAFE_MODE in the deployed
    app's Secrets turns it off for visitors."""
    try:
        return not (bool(st.secrets.get("PUBLIC_MODE", False))
                    or bool(st.secrets.get("PUBLIC_SAFE_MODE", False)))
    except Exception:
        return True

TX_COLUMNS = ["Photo", "Date", "Player", "Type", "Team", "Description"]


@st.cache_data(ttl=900, show_spinner=False)
def load_transactions(team_id, start, end):
    """Official MLB transactions for one team between two dates, newest first."""
    params = {
        "teamId": team_id,
        "startDate": start.strftime("%m/%d/%Y"),
        "endDate": end.strftime("%m/%d/%Y"),
    }
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
    df = pd.DataFrame(rows, columns=TX_COLUMNS)
    return df.sort_values("Date", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=900, show_spinner=False)
def load_40man(team_id, on_date):
    """A team's 40-man roster on a given date, as {player id: name and position}."""
    resp = requests.get(
        f"{BASE_URL}/teams/{team_id}/roster",
        params={"rosterType": "40Man", "date": on_date.strftime("%Y-%m-%d")},
        timeout=20,
    )
    resp.raise_for_status()
    return {
        e["person"]["id"]: {
            "name": e["person"]["fullName"],
            "pos": e.get("position", {}).get("abbreviation", ""),
        }
        for e in resp.json()["roster"]
    }


# Hand-picked links for the Home page reading list. Edit this list yourself.
NEWS_LINKS = [
    {"name": "MLB Trade Rumors", "note": "Transactions and rumors", "url": "https://www.mlbtraderumors.com"},
    {"name": "MLB.com: Braves", "note": "Team news and schedule", "url": "https://www.mlb.com/braves"},
    {"name": "Braves Pipeline", "note": "Minor league and prospect coverage", "url": "https://www.mlb.com/braves/news/topic/braves-pipeline-coverage"},
    {"name": "MLB.com News", "note": "League-wide news and articles", "url": "https://www.mlb.com/news"},
    # Add your own, for example a beat writer you follow:
    # {"name": "Writer Name", "note": "Braves beat writer, Outlet", "url": "https://..."},
]
# ---------- Today's game ----------
EASTERN = ZoneInfo("America/New_York")


def today_eastern():
    """Today's date in Eastern time. The deployed server runs on UTC, so plain
    date.today() would flip to 'tomorrow' around 8 PM Eastern, mid-game."""
    return datetime.now(EASTERN).date()


@st.cache_data(ttl=60, show_spinner=False)
def load_todays_games(on_date):
    """Braves games on one date (a list, because doubleheaders mean two).
    An empty list means no game that day. Cached for only 60 seconds so a
    live score stays fresh."""
    resp = requests.get(
        f"{BASE_URL}/schedule",
        params={
            "sportId": 1,
            "teamId": BRAVES_ID,
            "date": on_date.strftime("%Y-%m-%d"),
            "hydrate": "team,probablePitcher,linescore",
        },
        timeout=15,
    )
    resp.raise_for_status()

    games = []
    for d in resp.json().get("dates", []):
        for g in d["games"]:
            home, away = g["teams"]["home"], g["teams"]["away"]
            is_home = home["team"]["id"] == BRAVES_ID
            us, them = (home, away) if is_home else (away, home)

            # The API gives start time in UTC; convert it to Eastern
            start = datetime.fromisoformat(g["gameDate"].replace("Z", "+00:00")).astimezone(EASTERN)
            line = g.get("linescore", {})

            games.append({
                "start": start,
                "start_text": f"{start:%I:%M %p}".lstrip("0") + " ET",
                "state": g["status"]["abstractGameState"],   # Preview, Live or Final
                "detail": g["status"]["detailedState"],      # Scheduled, Postponed, etc.
                "is_home": is_home,
                "us_abbr": us["team"].get("abbreviation", "ATL"),
                "us_score": us.get("score"),
                "us_pitcher": us.get("probablePitcher", {}).get("fullName"),
                "them_id": them["team"]["id"],
                "them_name": them["team"]["name"],
                "them_abbr": them["team"].get("abbreviation", ""),
                "them_score": them.get("score"),
                "them_pitcher": them.get("probablePitcher", {}).get("fullName"),
                "inning": f"{line.get('inningState', '')} {line.get('currentInningOrdinal', '')}".strip(),
            })
    return sorted(games, key=lambda x: x["start"])