import html
import pandas as pd
import streamlit as st
from datetime import date, timedelta
from data import load_roster, load_transactions, load_40man, BRAVES_ID

STYLE = """
<style>
.rt-wrap { overflow-x: auto; }
.rt-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.rt-table th {
    text-align: right; font-size: 0.68rem; letter-spacing: 0.07em; text-transform: uppercase;
    color: #5b6b82; border-bottom: 2px solid #0b1f3a; padding: 8px 10px; white-space: nowrap;
}
.rt-table td {
    text-align: right; padding: 6px 10px; border-bottom: 1px solid #eef1f5; color: #0b1f3a;
    font-variant-numeric: tabular-nums; white-space: nowrap;
}
.rt-table th:nth-child(-n+5), .rt-table td:nth-child(-n+5) { text-align: left; }
.rt-table tbody tr:hover td { background: #f6f8fb; }
.rt-photo {
    width: 32px; height: 32px; border-radius: 50%; object-fit: cover; object-position: top;
    background: #e3e8ef; display: block;
}
.rt-name a { color: #0b1f3a; font-weight: 700; text-decoration: none; }
.rt-name a:hover { color: #d6001c; text-decoration: underline; }
</style>
"""

HIT_STATS = ["G", "AB", "H", "HR", "RBI", "BB", "SO", "AVG", "OBP", "SLG", "OPS"]
HIT_DIGITS = {"AVG": 3, "OBP": 3, "SLG": 3, "OPS": 3}   # stats shown with decimals
PIT_STATS = ["G", "GS", "W", "L", "SV", "IP", "ERA", "WHIP", "SO", "BB", "K/9"]
PIT_DIGITS = {"IP": 1, "ERA": 2, "WHIP": 2, "K/9": 2}   # IP needs 1 decimal (152.1 = 152 and 1/3 innings)


def fmt_cell(col, value, rate_digits):
    """One stat cell: '-' if missing, whole numbers for counts, decimals for rates."""
    if pd.isna(value):
        return "-"
    if col in rate_digits:
        text = f"{value:.{rate_digits[col]}f}"
        return text.lstrip("0") if rate_digits[col] == 3 else text   # 0.283 -> .283
    return f"{value:.0f}"


def roster_table_html(df, stat_cols, rate_digits):
    """The roster as an HTML table where each player's name links to their profile popup."""
    head = ("<th></th><th>Player</th><th>#</th><th>Pos</th><th>Status</th>"
            + "".join("<th>" + c + "</th>" for c in stat_cols))
    body = ""
    for _, r in df.iterrows():
        body += (
            "<tr>"
            '<td><img class="rt-photo" src="' + r["Photo"] + '" alt=""></td>'
            '<td class="rt-name"><a href="?player=' + str(int(r["ID"])) + '" target="_self">'
            + html.escape(str(r["Player"])) + "</a></td>"
            "<td>" + html.escape(str(r["#"])) + "</td>"
            "<td>" + html.escape(str(r["Pos"])) + "</td>"
            "<td>" + html.escape(str(r["Status"])) + "</td>"
            + "".join("<td>" + fmt_cell(c, r[c], rate_digits) + "</td>" for c in stat_cols)
            + "</tr>"
        )
    return ('<div class="rt-wrap"><table class="rt-table"><thead><tr>' + head +
            "</tr></thead><tbody>" + body + "</tbody></table></div>")

st.header("Braves Roster")
st.markdown(STYLE, unsafe_allow_html=True)

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
        s1, s2, _ = st.columns([1, 1, 2])
        sort_col = s1.selectbox("Sort by", HIT_STATS, index=HIT_STATS.index("AB"), key="hit_sort")
        order = s2.radio("Order", ["High to low", "Low to high"], horizontal=True, key="hit_order")
        ordered = hitters.sort_values(
            sort_col, ascending=(order == "Low to high"), na_position="last"
        )
        st.markdown(roster_table_html(ordered, HIT_STATS, HIT_DIGITS), unsafe_allow_html=True)

with pit_tab:
    if pitchers.empty:
        st.info("No pitchers match these filters.")
    else:
        s1, s2, _ = st.columns([1, 1, 2])
        sort_col = s1.selectbox("Sort by", PIT_STATS, index=PIT_STATS.index("IP"), key="pit_sort")
        order = s2.radio("Order", ["High to low", "Low to high"], horizontal=True, key="pit_order")
        ordered = pitchers.sort_values(
            sort_col, ascending=(order == "Low to high"), na_position="last"
        )
        st.markdown(roster_table_html(ordered, PIT_STATS, PIT_DIGITS), unsafe_allow_html=True)

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