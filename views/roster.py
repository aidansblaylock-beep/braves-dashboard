import streamlit as st
from datetime import date, timedelta
from data import load_roster, load_transactions, load_40man, BRAVES_ID

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

hit_tab, pit_tab, moves_tab = st.tabs(
    [f"Hitters ({len(hitters)})", f"Pitchers ({len(pitchers)})", "Recent Moves"]
)

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

with moves_tab:
    st.caption("Roster changes and official transactions for the Braves. "
               "These dates are separate from the season and roster filters above.")
    d1, d2 = st.columns(2)
    start = d1.date_input("From", value=today - timedelta(days=30), max_value=today, key="moves_from")
    end = d2.date_input("To", value=today, max_value=today, key="moves_to")

    if start > end:
        st.warning("The start date needs to be on or before the end date.")
    else:
        # ----- 40-man snapshot -----
        try:
            before = load_40man(BRAVES_ID, start)
            after = load_40man(BRAVES_ID, end)
        except Exception:
            before = after = None

        if after is not None:
            added = [after[i] for i in after if i not in before]
            removed = [before[i] for i in before if i not in after]

            s = st.columns(3)
            s[0].metric("40-Man Roster", len(after), delta=len(after) - len(before), delta_color="off")
            s[1].metric("Added to 40-man", len(added))
            s[2].metric("Removed from 40-man", len(removed))

            with st.expander(f"Roster changes, {start:%b} {start.day} to {end:%b} {end.day}"):
                left, right = st.columns(2)
                left.markdown("**Added**")
                if added:
                    for p in added:
                        left.write(f"{p['name']} ({p['pos']})")
                else:
                    left.write("No additions in this range.")
                right.markdown("**Removed**")
                if removed:
                    for p in removed:
                        right.write(f"{p['name']} ({p['pos']})")
                else:
                    right.write("No removals in this range.")
                st.caption("The 40-man count includes players on the injured list "
                           "and players listed as reassigned to the minors.")

        # ----- Transactions feed -----
        try:
            tx = load_transactions(BRAVES_ID, start, end)
        except Exception:
            tx = None
            st.warning("Couldn't load transactions right now. Try again in a minute.")

        if tx is not None and tx.empty:
            st.info("No transactions found for that date range.")
        elif tx is not None:
            f1, f2 = st.columns([2, 1])
            types = sorted(t for t in tx["Type"].unique() if t)
            chosen = f1.multiselect("Type", types, placeholder="All types")
            query = f2.text_input("Search player or description")

            if chosen:
                tx = tx[tx["Type"].isin(chosen)]
            if query:
                q = query.lower()
                mask = (tx["Player"].str.lower().str.contains(q, na=False)
                        | tx["Description"].str.lower().str.contains(q, na=False))
                tx = tx[mask]

            m = st.columns(3)
            m[0].metric("Moves", len(tx))
            m[1].metric("Signings", int(tx["Type"].str.contains("Signed", case=False, na=False).sum()))
            m[2].metric("Trades", int(tx["Type"].str.contains("Trade", case=False, na=False).sum()))

            if tx.empty:
                st.info("No transactions match those filters.")
            else:
                st.dataframe(
                    tx.head(500),
                    hide_index=True,
                    use_container_width=True,
                    row_height=44,
                    column_config={
                        "Photo": PHOTO,
                        "Description": st.column_config.TextColumn("Description", width="large"),
                    },
                )
                if len(tx) > 500:
                    st.caption("Showing the 500 most recent moves.")

st.caption("Data: MLB Stats API. Refreshes every 15 to 30 minutes.")