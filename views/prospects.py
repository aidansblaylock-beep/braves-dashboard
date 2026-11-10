import streamlit as st
import pandas as pd
from datetime import date
from data import editing_enabled
from prospects_data import (
    LEVELS, HIT_OUT, PIT_OUT, load_orgs, load_farm_players, load_prospect_stats,
    load_prospect_favs, save_prospect_favs, add_age_vs_level,
)

PIPELINE_URL = "https://www.mlb.com/braves/news/topic/braves-pipeline-coverage"
PROSPECT_STATS_URL = "https://www.mlb.com/braves/prospects/stats"
VIEWS = ["Braves", "Other organizations", "My favorites (all MLB)"]

today = date.today()
default_season = today.year if today.month >= 3 else today.year - 1

head_col, l1, l2 = st.columns([3, 1, 1], vertical_alignment="center")
head_col.header("Prospects")
l1.link_button("Braves Pipeline ↗", PIPELINE_URL, use_container_width=True)
l2.link_button("MLB prospect stats ↗", PROSPECT_STATS_URL, use_container_width=True)

favs = load_prospect_favs()
orgs = load_orgs(default_season)
PHOTO = st.column_config.ImageColumn("", width="small")

view = st.radio("View", VIEWS, horizontal=True)

# ---------- Controls ----------
top = st.columns([1, 2, 1])
season = top[0].selectbox("Season", list(range(default_season, 2014, -1)), key="prospect_season")

org_name = "Atlanta Braves"
if view == "Other organizations":
    org_name = top[1].selectbox("Organization", [n for n in orgs if n != "Atlanta Braves"])

levels = list(LEVELS.values())
min_pa, min_ip, fav_only = 0, 0, False
if view != VIEWS[2]:
    level_labels = list(LEVELS.values())
    f = st.columns([2, 1, 1, 1])
    levels = f[0].multiselect("Levels", level_labels,
                              default=[lv for lv in level_labels if lv != "Rookie"])
    min_pa = f[1].number_input("Min PA (hitters)", min_value=0, max_value=700, value=50, step=10)
    min_ip = f[2].number_input("Min IP (pitchers)", min_value=0, max_value=200, value=20, step=5)
    fav_only = f[3].toggle("Favorites only")

# ---------- Which players to load ----------
if view == VIEWS[2]:
    ids = tuple(sorted(favs))
    if not ids:
        st.info("No favorites yet. Star prospects in the Braves or Other organizations views, "
                "and they'll show up here from every organization.")
        st.stop()
else:
    farm = load_farm_players(orgs[org_name], season)
    ids = tuple(int(i) for i, _ in farm)
    if not ids:
        st.info("No minor league players found for that organization and season.")
        st.stop()

with st.spinner("Loading minor league stats..."):
    hit_df, pit_df = load_prospect_stats(ids, season)

if view != VIEWS[2]:
    hit_df, pit_df = add_age_vs_level(hit_df, pit_df)
    hit_df = hit_df[hit_df["Level"].isin(levels) & (hit_df["PA"].fillna(0) >= min_pa)]
    pit_df = pit_df[pit_df["Level"].isin(levels) & (pit_df["IP"].fillna(0) >= min_ip)]
    if fav_only:
        hit_df = hit_df[hit_df["player_id"].isin(set(favs))]
        pit_df = pit_df[pit_df["player_id"].isin(set(favs))]

hit_df = hit_df.sort_values("OPS", ascending=False, na_position="last")
pit_df = pit_df.sort_values("ERA", ascending=True, na_position="last")


# ---------- Table with a star column ----------
def render(df, cols, fmt_cols, key):
    """Local: click the star box to favorite. Live site: stars are read-only."""
    df = df.copy()
    df["★"] = df["player_id"].isin(set(favs))
    df = df[["player_id"] + cols]
    config = {"player_id": None, "Photo": PHOTO}
    config.update(fmt_cols)

    if editing_enabled():
        config["★"] = st.column_config.CheckboxColumn("★", width="small")
        edited = st.data_editor(
            df, hide_index=True, use_container_width=True, row_height=44,
            disabled=[c for c in df.columns if c != "★"],
            column_config=config,
            key=f"{key}_{hash(tuple(sorted(favs)))}",
        )
        shown = set(df["player_id"])
        starred_now = set(edited.loc[edited["★"], "player_id"])
        updated = (set(favs) - shown) | starred_now
        if updated != set(favs):
            names = {**favs, **dict(zip(edited["player_id"], edited["Player"]))}
            save_prospect_favs({int(i): names[i] for i in updated})
            st.rerun()
    else:
        df["★"] = df["★"].map({True: "★", False: ""})
        config["★"] = st.column_config.TextColumn("★", width="small")
        st.dataframe(df, hide_index=True, use_container_width=True, row_height=44,
                     column_config=config)


age_fmt = {"Age": st.column_config.NumberColumn("Age", format="%.0f")}
show_age_vs = view != VIEWS[2]
if show_age_vs:
    age_fmt["Age vs Lvl"] = st.column_config.NumberColumn("Age vs Lvl", format="%+.1f")

hit_cols = ["★", "Photo", "Player", "Pos", "Age"] + (["Age vs Lvl"] if show_age_vs else []) \
    + ["Level", "Team"] + HIT_OUT
pit_cols = ["★", "Photo", "Player", "Age"] + (["Age vs Lvl"] if show_age_vs else []) \
    + ["Level", "Team"] + PIT_OUT

hit_fmt = {**age_fmt, **{c: st.column_config.NumberColumn(c, format="%.3f")
                         for c in ["AVG", "OBP", "SLG", "OPS"]}}
pit_fmt = {**age_fmt, "IP": st.column_config.NumberColumn("IP", format="%.1f"),
           **{c: st.column_config.NumberColumn(c, format="%.2f") for c in ["ERA", "WHIP", "K/9"]}}

if view == VIEWS[2]:
    st.subheader("My favorites across MLB")
else:
    st.subheader(f"{org_name} farm system")

hit_tab, pit_tab = st.tabs([f"Hitters ({len(hit_df)})", f"Pitchers ({len(pit_df)})"])

with hit_tab:
    if hit_df.empty:
        st.info("No hitters match these filters.")
    else:
        render(hit_df, hit_cols, hit_fmt, f"hit_{view}_{org_name}_{fav_only}")

with pit_tab:
    if pit_df.empty:
        st.info("No pitchers match these filters.")
    else:
        render(pit_df, pit_cols, pit_fmt, f"pit_{view}_{org_name}_{fav_only}")

st.caption(
    "Stats combine all minor league levels for the season, and Level is the highest level reached. "
    "Age is current age. Age vs Lvl is years younger (-) or older (+) than the average player "
    "at that level in the same organization. Click a column header to sort. "
    "Data: MLB Stats API."
)