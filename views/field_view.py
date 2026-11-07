import requests
import numpy as np
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
from datetime import date
from pybaseball import statcast_batter, plot_stadium
from data import load_player_directory, load_favorites, load_roster_players, headshot_url
from hover_chart import build_hover_chart

st.header("Field View")
st.caption("Where a hitter's batted balls landed, drawn on a ballpark outline or a generic field.")

# Team name -> (pybaseball park key, Statcast home_team abbreviation)
PARKS = {
    "Arizona Diamondbacks": ("diamondbacks", "AZ"), "Athletics": ("athletics", "ATH"),
    "Atlanta Braves": ("braves", "ATL"), "Baltimore Orioles": ("orioles", "BAL"),
    "Boston Red Sox": ("red_sox", "BOS"), "Chicago Cubs": ("cubs", "CHC"),
    "Chicago White Sox": ("white_sox", "CWS"), "Cincinnati Reds": ("reds", "CIN"),
    "Cleveland Guardians": ("indians", "CLE"), "Colorado Rockies": ("rockies", "COL"),
    "Detroit Tigers": ("tigers", "DET"), "Houston Astros": ("astros", "HOU"),
    "Kansas City Royals": ("royals", "KC"), "Los Angeles Angels": ("angels", "LAA"),
    "Los Angeles Dodgers": ("dodgers", "LAD"), "Miami Marlins": ("marlins", "MIA"),
    "Milwaukee Brewers": ("brewers", "MIL"), "Minnesota Twins": ("twins", "MIN"),
    "New York Mets": ("mets", "NYM"), "New York Yankees": ("yankees", "NYY"),
    "Philadelphia Phillies": ("phillies", "PHI"), "Pittsburgh Pirates": ("pirates", "PIT"),
    "San Diego Padres": ("padres", "SD"), "San Francisco Giants": ("giants", "SF"),
    "Seattle Mariners": ("mariners", "SEA"), "St. Louis Cardinals": ("cardinals", "STL"),
    "Tampa Bay Rays": ("rays", "TB"), "Texas Rangers": ("rangers", "TEX"),
    "Toronto Blue Jays": ("blue_jays", "TOR"), "Washington Nationals": ("nationals", "WSH"),
}
GENERIC = "All parks (generic field)"

# ---------- Fixed outcome groups and colors (never change between players/years) ----------
OUTCOMES = ["Single", "Double", "Triple", "Home Run", "Out", "Error / Other"]
OUTCOME_COLORS = {
    "Single": "#2e9e5b", "Double": "#1f77d0", "Triple": "#8e44ad",
    "Home Run": "#d6001c", "Out": "#9aa5b1", "Error / Other": "#f0a30a",
}
EVENT_GROUPS = {
    "single": "Single", "double": "Double", "triple": "Triple", "home_run": "Home Run",
    "field_out": "Out", "force_out": "Out", "grounded_into_double_play": "Out",
    "double_play": "Out", "triple_play": "Out", "sac_fly": "Out", "sac_bunt": "Out",
    "sac_fly_double_play": "Out", "sac_bunt_double_play": "Out", "fielders_choice_out": "Out",
}

# ---------- Home run arc settings ----------
# Distance colors: short homers gold -> long homers deep maroon (fixed scale, so colors never shift)
DIST_CMAP = LinearSegmentedColormap.from_list(
    "hr_distance", ["#f2b705", "#e8590c", "#d6001c", "#6b0f1a"]
)
DIST_NORM = Normalize(vmin=350, vmax=470, clip=True)
HEIGHT_BOOST = 3   # how exaggerated the arc height is (raise for taller arcs, lower for flatter)


def group_outcome(event):
    return EVENT_GROUPS.get(event, "Error / Other")


today = date.today()
latest_season = today.year if today.month >= 3 else today.year - 1


# ---------- Drawing helpers ----------
def to_feet(df):
    """Convert Statcast hit coordinates to feet from home plate (home plate = 0, 0)."""
    x = 2.5 * (df["hc_x"] - 125.42)
    y = 2.5 * (198.27 - df["hc_y"])
    return x.to_numpy(), y.to_numpy()


def draw_generic_field(ax):
    """A simple field outline, in feet. The 400 ft wall is for scale, not a real park."""
    fence = 400
    c = np.cos(np.pi / 4)
    line_color = "#6b7785"
    ax.plot([0, fence * c], [0, fence * c], color=line_color, lw=1.5, zorder=1)
    ax.plot([0, -fence * c], [0, fence * c], color=line_color, lw=1.5, zorder=1)
    theta = np.linspace(np.pi / 4, 3 * np.pi / 4, 120)
    ax.plot(fence * np.cos(theta), fence * np.sin(theta), color="#0b1f3a", lw=2.5, zorder=1)
    for r in (150, 250, 350):
        ax.plot(r * np.cos(theta), r * np.sin(theta), color="#c9d3e0", lw=0.8, ls="--", zorder=0)
        ax.text(0, r + 6, f"{r} ft", ha="center", fontsize=7, color="#8a96a6")
    ax.plot([0, 63.64, 0, -63.64, 0], [0, 63.64, 127.28, 63.64, 0], color=line_color, lw=1.2, zorder=1)
    ax.scatter([0], [60.5], s=18, color=line_color, zorder=1)
    ax.set_aspect("equal")
    ax.axis("off")


def draw_flight(ax, start, end, apex_ratio, color, n=50):
    """Draw a 3-D looking flight path: a lifted, tapering arc plus a faint ground shadow.
    The ball always comes down exactly on the landing spot. Returns the arc's highest y."""
    (x0, y0), (x1, y1) = start, end
    t = np.linspace(0, 1, n)
    gx = x0 + t * (x1 - x0)                      # path along the ground
    gy = y0 + t * (y1 - y0)
    length = np.hypot(x1 - x0, y1 - y0)
    ay = gy + apex_ratio * length * 4 * t * (1 - t)   # lift the path to make the arc

    ax.plot(gx, gy, color="#0b1f3a", alpha=0.15, lw=1, zorder=1.5)   # ground shadow

    pts = np.column_stack([gx, ay]).reshape(-1, 1, 2)
    segments = np.concatenate([pts[:-1], pts[1:]], axis=1)
    widths = np.linspace(2.8, 0.9, len(segments))                    # thick near home, thin far away
    ax.add_collection(LineCollection(segments, linewidths=widths, colors=[color],
                                     alpha=0.85, zorder=2))
    return ay.max()


# ---------- Cached downloads ----------
@st.cache_data(persist="disk", show_spinner=False)
def _load_past_season(player_id, year):
    """Finished seasons never change, so these are saved to disk for good."""
    return statcast_batter(f"{year}-03-01", f"{year}-11-30", player_id)


@st.cache_data(ttl=3600, show_spinner=False)
def _load_current_season(player_id, year):
    """A season in progress changes daily, so it refreshes every hour."""
    return statcast_batter(f"{year}-03-01", f"{year}-11-30", player_id)


def get_season(player_id, year):
    in_progress = year == today.year and today.month <= 10
    return _load_current_season(player_id, year) if in_progress else _load_past_season(player_id, year)


@st.cache_data(ttl=86400, show_spinner=False)
def get_played_seasons(player_id):
    """MLB seasons since 2015 (Statcast era) in which this player has hitting stats."""
    try:
        resp = requests.get(
            f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats",
            params={"stats": "yearByYear", "group": "hitting"},
            timeout=15,
        )
        splits = resp.json()["stats"][0]["splits"]
    except Exception:
        return []
    years = {
        int(s["season"]) for s in splits
        if s.get("sport", {}).get("id", 1) == 1 and int(s["season"]) >= 2015
    }
    return sorted(years, reverse=True)

@st.cache_data(ttl=86400, show_spinner=False)
def get_player_card(player_id):
    """Team, position and batting side for the player card."""
    try:
        resp = requests.get(
            f"https://statsapi.mlb.com/api/v1/people/{player_id}",
            params={"hydrate": "currentTeam"},
            timeout=15,
        )
        p = resp.json()["people"][0]
        return {
            "team": p.get("currentTeam", {}).get("name", ""),
            "pos": p.get("primaryPosition", {}).get("abbreviation", ""),
            "bats": p.get("batSide", {}).get("code", ""),
        }
    except Exception:
        return {"team": "", "pos": "", "bats": ""}
    
# ---------- Player picker ----------
source = st.radio(
    "Player list",
    ["Braves hitters", "My players to watch", "Search any player"],
    horizontal=True,
)

if source == "Braves hitters":
    options = {p["name"]: int(p["id"]) for p in load_roster_players(latest_season)
               if p["type"] != "Pitcher"}
elif source == "My players to watch":
    options = {f["name"]: int(f["id"]) for f in load_favorites()}
else:
    directory = load_player_directory(latest_season)
    directory = directory[directory["pos"] != "P"]
    options = {lbl: int(i) for lbl, i in zip(directory["label"], directory["id"])}

if not options:
    st.info("No players in this list yet. Add some on the Players to Watch page.")
    st.stop()

c1, c2 = st.columns([2, 1])
player_name = c1.selectbox("Player", list(options))
player_id = options[player_name]
seasons = get_played_seasons(player_id)

if not seasons:
    c2.selectbox("Season", ["No data"], disabled=True)
    st.warning("No MLB hitting seasons since 2015 found for this player. "
               "(Statcast tracking starts in 2015, and pitchers have no batted-ball data here.)")
    st.stop()

season_options = [str(y) for y in seasons] + (["Career"] if len(seasons) > 1 else [])
season_choice = c2.selectbox("Season", season_options)

if st.button("Show spray chart", type="primary"):
    st.session_state["field_view"] = {
        "id": player_id, "name": player_name, "season": season_choice, "seasons": seasons,
    }

sel = st.session_state.get("field_view")
if sel is None:
    st.info("Pick a player and a season, then click **Show spray chart**.")
    st.stop()

# ---------- Work out which seasons to load ----------
if sel["season"] == "Career":
    season_list = sorted(sel.get("seasons") or get_played_seasons(sel["id"]))
    season_label = f"Career ({season_list[0]}-{season_list[-1]})"
else:
    season_list = [int(sel["season"])]
    season_label = sel["season"]

# ---------- Download with a progress bar ----------
progress = st.progress(0, text="Starting...")
frames = []
for i, yr in enumerate(season_list):
    progress.progress(i / len(season_list), text=f"Loading {yr} season ({i + 1} of {len(season_list)})...")
    frames.append(get_season(sel["id"], yr))
progress.empty()

df_all = pd.concat(frames, ignore_index=True)
if df_all.empty or "events" not in df_all.columns:
    st.info("No Statcast batting data for that player in that period.")
    st.stop()

in_play = df_all.dropna(subset=["hc_x", "hc_y", "events"]).copy()
in_play["Outcome"] = in_play["events"].map(group_outcome)

# ---------- Filters (instant, no downloading) ----------
park_options = [GENERIC] + list(PARKS)
default_park = GENERIC if sel["season"] == "Career" else "Atlanta Braves"
park_name = st.selectbox("Ballpark", park_options, index=park_options.index(default_park))
generic = park_name == GENERIC

show_arcs = st.toggle("Home run arcs (shows home runs only)")
by_distance = True
if show_arcs:
    by_distance = st.toggle("Color arcs by distance", value=True)

pill_choice = st.pills(
    "Outcomes (click to turn on or off)",
    OUTCOMES, selection_mode="multi", default=OUTCOMES, key="field_outcomes",
    disabled=show_arcs,
) or []
chosen = ["Home Run"] if show_arcs else pill_choice

style = "Dots"
if generic and not show_arcs:
    style = st.radio("Style", ["Dots", "Heatmap"], horizontal=True)

if generic:
    at_park = in_play
else:
    park_key, park_abbr = PARKS[park_name]
    at_park = in_play[in_play["home_team"] == park_abbr]
shown = at_park[at_park["Outcome"].isin(chosen)]

# ---------- Display ----------
where = "all ballparks" if generic else f"{park_name}'s park"
st.markdown("""
<style>
.pcard {
    display: flex; align-items: center; gap: 18px; background: #ffffff;
    border: 1px solid #e3e8ef; border-left: 4px solid #d6001c; border-radius: 10px;
    padding: 14px 20px; margin: 8px 0 16px; box-shadow: 0 1px 2px rgba(11, 31, 58, 0.06);
}
.pcard-photo {
    width: 84px; height: 84px; border-radius: 50%; object-fit: cover; object-position: top;
    background: #e3e8ef; border: 3px solid #ffffff; box-shadow: 0 0 0 1px #d5dce6; flex-shrink: 0;
}
.pcard-name { font-size: 1.6rem; font-weight: 800; color: #0b1f3a; line-height: 1.1; }
.pcard-meta { color: #44556d; font-size: 0.95rem; margin-top: 4px; }
.pcard-sub {
    color: #d6001c; font-size: 0.75rem; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase; margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

card = get_player_card(sel["id"])
display_name = sel["name"].split(" (")[0]          # drops the "(RF)" from search labels
meta_parts = [card["team"], card["pos"], f"Bats {card['bats']}" if card["bats"] else ""]
meta = " · ".join(part for part in meta_parts if part)
context = f"{season_label} · {'All ballparks' if generic else park_name}"

st.markdown(
    f'<div class="pcard"><img class="pcard-photo" src="{headshot_url(sel["id"], 200)}" alt="">'
    f'<div><div class="pcard-name">{display_name}</div>'
    f'<div class="pcard-meta">{meta}</div>'
    f'<div class="pcard-sub">{context}</div></div></div>',
    unsafe_allow_html=True,
)

if at_park.empty:
    st.info("No batted balls found at this park for that period.")
    st.stop()
if shown.empty:
    st.info("No batted balls match the current selection.")
    st.stop()

avg_ev = shown["launch_speed"].mean()
m1, m2, m3 = st.columns(3)
m1.metric("Balls in play", len(shown))
m2.metric("Home runs", int((shown["Outcome"] == "Home Run").sum()))
m3.metric("Avg exit velocity", f"{avg_ev:.1f} mph" if pd.notna(avg_ev) else "n/a")

chart_col, legend_col = st.columns([3, 1])

with chart_col:
    use_hover = not (generic and style == "Heatmap")
    
    if use_hover:
        fig = build_hover_chart(
            shown=shown, generic=generic, park_key=None if generic else park_key,
            show_arcs=show_arcs, by_distance=by_distance,
            outcomes=OUTCOMES, outcome_colors=OUTCOME_COLORS,
            dist_cmap=DIST_CMAP, dist_norm=DIST_NORM, height_boost=HEIGHT_BOOST,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        if generic:
            fig, ax = plt.subplots(figsize=(7, 6.4))
            draw_generic_field(ax)
            px, py = to_feet(shown)
            origin = (0.0, 0.0)
        else:
            plot_stadium(park_key)          # draws only the ballpark outline
            ax = plt.gca()
            px = shown["hc_x"].to_numpy()
            py = -shown["hc_y"].to_numpy()
            origin = (125.42, -198.27)      # home plate in these coordinates

        arc_top = None
        if show_arcs:
            n = len(shown)
            dist = (shown["hit_distance_sc"].to_numpy(dtype=float)
                    if "hit_distance_sc" in shown.columns else np.full(n, np.nan))
            angle = (shown["launch_angle"].to_numpy(dtype=float)
                     if "launch_angle" in shown.columns else np.full(n, np.nan))
            use_dist = by_distance and not np.isnan(dist).all()

            tops = []
            for i in np.argsort(np.nan_to_num(dist, nan=0.0)):   # longest drawn last, on top
                if use_dist and not np.isnan(dist[i]):
                    color = DIST_CMAP(DIST_NORM(dist[i]))
                elif use_dist:
                    color = "#9aa5b1"                               # no distance recorded
                else:
                    color = OUTCOME_COLORS["Home Run"]
                ang = angle[i] if not np.isnan(angle[i]) else 28.0
                ratio = float(np.clip(np.tan(np.radians(ang)) / 4 * HEIGHT_BOOST, 0.12, 0.45))
                tops.append(draw_flight(ax, origin, (px[i], py[i]), ratio, color))
                ax.scatter([px[i]], [py[i]], s=38, color=color,
                           edgecolor="white", linewidth=0.6, zorder=3)
            arc_top = max(tops)

            if use_dist:
                sm = ScalarMappable(norm=DIST_NORM, cmap=DIST_CMAP)
                plt.gcf().colorbar(sm, ax=ax, shrink=0.55, pad=0.02, label="Distance (ft)")

        elif generic and style == "Heatmap":
            ax.hexbin(px, py, gridsize=22, extent=(-300, 300, 0, 450),
                      cmap="Reds", mincnt=1, alpha=0.9, zorder=2)
        else:
            outcome_col = shown["Outcome"].to_numpy()
            for outcome in OUTCOMES:
                mask = outcome_col == outcome
                if mask.any():
                    ax.scatter(px[mask], py[mask], s=45, color=OUTCOME_COLORS[outcome],
                               edgecolor="white", linewidth=0.5, alpha=0.9, zorder=3)

        # Make sure the tallest arcs fit inside the chart
        if generic:
            ax.set_xlim(-330, 330)
            ax.set_ylim(-25, max(470, (arc_top or 0) + 25))
        elif arc_top is not None:
            lo, hi = ax.get_ylim()
            ax.set_ylim(lo, max(hi, arc_top + 0.05 * (hi - lo)))

        st.pyplot(plt.gcf())
        plt.close()

with legend_col:
    st.write("**Outcomes**")
    counts = at_park["Outcome"].value_counts()
    rows = ""
    for outcome in OUTCOMES:
        opacity = 1 if outcome in chosen else 0.3
        rows += (
            f"<div style='display:flex;align-items:center;gap:10px;margin:10px 0;opacity:{opacity}'>"
            f"<span style='width:14px;height:14px;border-radius:50%;display:inline-block;"
            f"background:{OUTCOME_COLORS[outcome]}'></span>"
            f"<span style='flex:1'>{outcome}</span><b>{int(counts.get(outcome, 0))}</b></div>"
        )
    st.markdown(rows, unsafe_allow_html=True)

# ---------- Home run log (only when arcs are on) ----------
if show_arcs:
    st.subheader("Home run log")
    log_cols = {
        "game_date": "Date", "home_team": "Home", "away_team": "Away",
        "hit_distance_sc": "Distance (ft)", "launch_speed": "Exit Velo (mph)",
        "launch_angle": "Launch Angle",
    }
    present = [c for c in log_cols if c in shown.columns]
    log = shown[present].rename(columns=log_cols)
    if "Distance (ft)" in log.columns:
        log = log.sort_values("Distance (ft)", ascending=False, na_position="last")
    st.dataframe(log, hide_index=True, use_container_width=True)