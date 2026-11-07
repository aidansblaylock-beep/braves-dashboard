import streamlit as st
from datetime import date
from data import load_roster

st.header("Braves Roster")

today = date.today()
default_season = today.year if today.month >= 3 else today.year - 1

col1, col2, col3 = st.columns(3)
season = col1.selectbox("Season", list(range(default_season, 2014, -1)))
roster_labels = {"40Man": "40-Man", "active": "Active (26)", "fullSeason": "Full Season"}
roster_type = col2.selectbox("Roster", list(roster_labels), format_func=roster_labels.get)
status = col3.selectbox("Status", ["All", "Active", "Injured List", "Minors", "Other"])

hitters, pitchers = load_roster(season, roster_type)
if status != "All":
    hitters = hitters[hitters["Status"] == status]
    pitchers = pitchers[pitchers["Status"] == status]

PHOTO = st.column_config.ImageColumn("", width="small")

hit_tab, pit_tab = st.tabs([f"Hitters ({len(hitters)})", f"Pitchers ({len(pitchers)})"])

with hit_tab:
    if hitters.empty:
        st.info("No hitters match these filters.")
    else:
        st.dataframe(
            hitters.sort_values("AB", ascending=False, na_position="last"),
            hide_index=True,
            use_container_width=True,
            row_height=44,
            column_config={
                "Photo": PHOTO,
                **{c: st.column_config.NumberColumn(c, format="%.3f")
                   for c in ["AVG", "OBP", "SLG", "OPS"]},
            },
        )

with pit_tab:
    if pitchers.empty:
        st.info("No pitchers match these filters.")
    else:
        st.dataframe(
            pitchers.sort_values("IP", ascending=False, na_position="last"),
            hide_index=True,
            use_container_width=True,
            row_height=44,
            column_config={
                "Photo": PHOTO,
                **{c: st.column_config.NumberColumn(c, format="%.2f")
                   for c in ["ERA", "WHIP", "K/9"]},
            },
        )

st.caption("Data: MLB Stats API. Refreshes every 30 minutes.")