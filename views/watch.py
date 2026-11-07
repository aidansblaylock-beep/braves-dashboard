import streamlit as st
from datetime import date
from data import (
    load_player_directory, load_favorites, save_favorites, load_player_stats,
)

st.header("Players to Watch")

today = date.today()
default_season = today.year if today.month >= 3 else today.year - 1

pick_col, _ = st.columns([1, 5])
season = pick_col.selectbox("Season", list(range(default_season, 2014, -1)), key="watch_season")

favs = load_favorites()
directory = load_player_directory(default_season)

# ----- Add a player -----
with st.expander("Add a player", expanded=not favs):
    choice = st.selectbox(
        "Search by name", directory["label"], index=None,
        placeholder="Start typing a name...",
    )
    if st.button("Add to my list", disabled=choice is None):
        row = directory[directory["label"] == choice].iloc[0]
        if int(row["id"]) in [f["id"] for f in favs]:
            st.warning("Already on your list.")
        else:
            favs.append({"id": int(row["id"]), "name": row["name"]})
            save_favorites(favs)
            st.rerun()

# ----- Remove players -----
if favs:
    with st.expander("Remove players"):
        to_remove = st.multiselect("Select players to remove", [f["name"] for f in favs])
        if st.button("Remove selected") and to_remove:
            favs = [f for f in favs if f["name"] not in to_remove]
            save_favorites(favs)
            st.rerun()

if not favs:
    st.info("Your list is empty. Open 'Add a player' above to start building it.")
    st.stop()

# ----- Stats -----
hitters, pitchers, missing = load_player_stats(tuple(f["id"] for f in favs), season)

PHOTO = st.column_config.ImageColumn("", width="small")

hit_tab, pit_tab = st.tabs([f"Hitters ({len(hitters)})", f"Pitchers ({len(pitchers)})"])

with hit_tab:
    if hitters.empty:
        st.info("No hitters on your list yet.")
    else:
        st.dataframe(
            hitters.sort_values("OPS", ascending=False, na_position="last"),
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
        st.info("No pitchers on your list yet.")
    else:
        st.dataframe(
            pitchers.sort_values("ERA", na_position="last"),
            hide_index=True,
            use_container_width=True,
            row_height=44,
            column_config={
                "Photo": PHOTO,
                **{c: st.column_config.NumberColumn(c, format="%.2f")
                   for c in ["ERA", "WHIP", "K/9"]},
            },
        )

if missing:
    st.caption(f"No {season} stats found for: " + ", ".join(missing))
st.caption("Data: MLB Stats API. Refreshes every 30 minutes.")