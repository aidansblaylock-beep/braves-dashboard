import json
import requests
import pandas as pd
import streamlit as st
from pathlib import Path
from data import headshot_url

BASE_URL = "https://statsapi.mlb.com/api/v1"
FAV_FILE = Path(__file__).parent / "prospect_favorites.json"

# Minor league levels, highest first: sportId -> label
LEVELS = {11: "AAA", 12: "AA", 13: "High-A", 14: "A", 16: "Rookie"}
LEVEL_ORDER = list(LEVELS)

HIT_SUM = ["gamesPlayed", "plateAppearances", "atBats", "hits", "homeRuns",
           "baseOnBalls", "hitByPitch", "sacFlies", "stolenBases", "totalBases"]
PIT_SUM = ["gamesPlayed", "gamesStarted", "earnedRuns", "hits", "baseOnBalls", "strikeOuts"]
HIT_OUT = ["G", "PA", "HR", "SB", "AVG", "OBP", "SLG", "OPS"]
PIT_OUT = ["G", "GS", "IP", "ERA", "WHIP", "K/9", "SO", "BB"]
BASE_COLS = ["player_id", "Photo", "Player", "Pos", "Age", "Level", "Team"]


# ---------- Starred prospects (saved in prospect_favorites.json) ----------
def load_prospect_favs():
    if FAV_FILE.exists():
        data = json.loads(FAV_FILE.read_text())
        return {int(k): v for k, v in data.items()}
    return {}


def save_prospect_favs(favs):
    FAV_FILE.write_text(json.dumps({str(k): v for k, v in favs.items()}, indent=2))


# ---------- Organizations and their minor league players ----------
@st.cache_data(ttl=86400, show_spinner=False)
def load_orgs(season):
    resp = requests.get(f"{BASE_URL}/teams", params={"sportId": 1, "season": season}, timeout=20)
    resp.raise_for_status()
    return dict(sorted({t["name"]: t["id"] for t in resp.json()["teams"]}.items()))


@st.cache_data(ttl=21600, show_spinner=False)
def load_farm_players(org_id, season):
    """Players on an organization's minor league affiliates, as [(player id, label)]."""
    resp = requests.get(f"{BASE_URL}/teams/affiliates",
                        params={"teamIds": org_id, "season": season}, timeout=20)
    resp.raise_for_status()
    players = {}
    for team in resp.json().get("teams", []):
        if team.get("sport", {}).get("id") not in LEVELS:
            continue
        r = requests.get(f"{BASE_URL}/teams/{team['id']}/roster",
                         params={"rosterType": "fullSeason", "season": season}, timeout=20)
        if r.status_code != 200:
            continue
        for e in r.json().get("roster", []):
            p = e["person"]
            players[p["id"]] = f"{p['fullName']} ({e['position']['abbreviation']}, {team['name']})"
    return sorted(players.items(), key=lambda kv: kv[1])


# ---------- Stats, combined across minor league levels ----------
def _num(stat, key):
    try:
        return int(stat.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _outs(ip):
    """Baseball innings like '45.1' become outs (136)."""
    try:
        whole, _, frac = str(ip).partition(".")
        return int(whole) * 3 + int(frac or 0)
    except ValueError:
        return 0


def _combine_hitting(entries):
    t = {k: sum(_num(s, k) for _, s in entries) for k in HIT_SUM}
    ab, h, bb, hbp, sf, tb = (t["atBats"], t["hits"], t["baseOnBalls"],
                              t["hitByPitch"], t["sacFlies"], t["totalBases"])
    avg = h / ab if ab else None
    obp_den = ab + bb + hbp + sf
    obp = (h + bb + hbp) / obp_den if obp_den else None
    slg = tb / ab if ab else None
    ops = obp + slg if obp is not None and slg is not None else None
    return {"G": t["gamesPlayed"], "PA": t["plateAppearances"], "HR": t["homeRuns"],
            "SB": t["stolenBases"], "AVG": avg, "OBP": obp, "SLG": slg, "OPS": ops}


def _combine_pitching(entries):
    outs = sum(_outs(s.get("inningsPitched")) for _, s in entries)
    t = {k: sum(_num(s, k) for _, s in entries) for k in PIT_SUM}
    er, h, bb, so = t["earnedRuns"], t["hits"], t["baseOnBalls"], t["strikeOuts"]
    return {
        "G": t["gamesPlayed"], "GS": t["gamesStarted"],
        "IP": float(f"{outs // 3}.{outs % 3}"),
        "ERA": 27 * er / outs if outs else None,
        "WHIP": 3 * (h + bb) / outs if outs else None,
        "K/9": 27 * so / outs if outs else None,
        "SO": so, "BB": bb,
    }


def _top_level(entries):
    best = min(entries, key=lambda e: LEVEL_ORDER.index(e[0]))
    return LEVELS[best[0]]


@st.cache_data(ttl=1800, show_spinner=False)
def load_prospect_stats(player_ids, season):
    """One request per level for the whole group, then combined into one season line per player."""
    ids = ",".join(str(i) for i in player_ids)
    people, hit_by, pit_by = {}, {}, {}
    for sport_id in LEVELS:
        resp = requests.get(
            f"{BASE_URL}/people",
            params={
                "personIds": ids,
                "hydrate": ("currentTeam,stats(group=[hitting,pitching],type=[season],"
                            f"season={season},sportId={sport_id})"),
            },
            timeout=30,
        )
        resp.raise_for_status()
        for p in resp.json().get("people", []):
            pid = p["id"]
            people[pid] = {
                "name": p["fullName"],
                "age": p.get("currentAge"),
                "pos": p.get("primaryPosition", {}).get("abbreviation", ""),
                "team": p.get("currentTeam", {}).get("name", ""),
            }
            for s in p.get("stats", []):
                splits = s.get("splits", [])
                if not splits:
                    continue
                target = hit_by if s["group"]["displayName"] == "hitting" else pit_by
                target.setdefault(pid, []).append((sport_id, splits[0]["stat"]))

    hit_rows, pit_rows = [], []
    for pid, info in people.items():
        base = {"player_id": pid, "Photo": headshot_url(pid), "Player": info["name"],
                "Pos": info["pos"], "Age": info["age"], "Team": info["team"]}
        if info["pos"] == "P":
            entries = pit_by.get(pid, [])
            stats = _combine_pitching(entries) if entries else {}
            level = _top_level(entries) if entries else ""
            pit_rows.append({**base, "Level": level, **{c: stats.get(c) for c in PIT_OUT}})
        else:
            entries = hit_by.get(pid, [])
            stats = _combine_hitting(entries) if entries else {}
            level = _top_level(entries) if entries else ""
            hit_rows.append({**base, "Level": level, **{c: stats.get(c) for c in HIT_OUT}})

    hit_df = pd.DataFrame(hit_rows, columns=BASE_COLS + HIT_OUT)
    pit_df = pd.DataFrame(pit_rows, columns=BASE_COLS + PIT_OUT)
    return hit_df, pit_df


def add_age_vs_level(hit_df, pit_df):
    """Adds 'Age vs Lvl': years younger (-) or older (+) than the average player at that level."""
    hit_df, pit_df = hit_df.copy(), pit_df.copy()
    for df in (hit_df, pit_df):
        df["Age"] = pd.to_numeric(df["Age"], errors="coerce")
    both = pd.concat([hit_df[["Level", "Age"]], pit_df[["Level", "Age"]]])
    both = both[(both["Level"] != "") & both["Age"].notna()]
    avg = both.groupby("Level")["Age"].mean()
    for df in (hit_df, pit_df):
        df["Age vs Lvl"] = (df["Age"] - df["Level"].map(avg)).round(1)
    return hit_df, pit_df