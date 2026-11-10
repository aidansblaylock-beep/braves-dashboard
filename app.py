import streamlit as st
from datetime import date
from data import load_team_snapshot, SHOW_MLB_IMAGES

st.set_page_config(page_title="Braves-Dashboard", layout="wide")

# Logo images (swap these two URLs if you'd rather use your own files)
BRAVES_LOGO = "https://www.mlbstatic.com/team-logos/team-cap-on-dark/144.svg"
MLB_LOGO = "https://www.mlbstatic.com/team-logos/league-on-dark/1.svg"

# ---------- Site-wide styling ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"], [data-testid="stMarkdownContainer"] {
    font-family: 'Inter', sans-serif;
}
.block-container { padding-top: 5rem; max-width: 1300px; }
footer { visibility: hidden; }

/* Headings */
h2 { font-weight: 800; color: #0b1f3a; letter-spacing: -0.01em; }
h3 { font-weight: 700; color: #0b1f3a; border-bottom: 2px solid #e3e8ef; padding-bottom: 0.3rem; }

/* Stat cards */
[data-testid="stMetric"] {
    background: #f6f8fb;
    border: 1px solid #e3e8ef;
    border-left: 4px solid #d6001c;
    border-radius: 8px;
    padding: 12px 16px;
}
[data-testid="stMetricLabel"] p {
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-size: 0.72rem;
    font-weight: 600;
    color: #5b6b82;
}
[data-testid="stMetricValue"] { font-weight: 800; color: #0b1f3a; }

/* Slim header bar */
.site-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #0b1f3a;
    border-bottom: 4px solid #d6001c;
    border-radius: 8px;
    padding: 8px 22px;
    margin-bottom: 18px;
}
.site-header .strip { display: flex; align-items: center; flex-wrap: wrap; }
.site-header .stat {
    display: flex;
    flex-direction: column;
    padding: 2px 20px;
    border-left: 1px solid rgba(255, 255, 255, 0.18);
}
.site-header .stat:first-child { border-left: none; padding-left: 0; }
.site-header .label {
    color: #9fb0c8;
    font-size: 0.66rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.site-header .value { color: #ffffff; font-size: 1.05rem; font-weight: 800; }
.site-header .logos { display: flex; gap: 10px; align-items: center; }
.site-header .logos a {
    display: flex;
    align-items: center;
    height: 46px;
    padding: 4px 10px;
    border-radius: 10px;
    color: #ffffff;
    font-weight: 700;
    text-decoration: none;
    transition: background 0.15s, transform 0.15s;
}
.site-header .logos a:hover { background: rgba(255, 255, 255, 0.14); transform: translateY(-1px); }
.site-header .logos img { height: 34px; width: auto; }
</style>
""", unsafe_allow_html=True)

# ---------- Live stat strip for the header ----------
today = date.today()
season = today.year if today.month >= 3 else today.year - 1
snap = load_team_snapshot(season)

stats = []
if snap["record"]:
    stats.append((f"{season} Record", snap["record"]))
if snap["rank"]:
    stats.append(("NL East", snap["rank"]))
if snap["last"]:
    stats.append(("Last Game", snap["last"]))
if snap["next"]:
    stats.append(("Next Game", snap["next"]))

strip_html = "".join(
    f'<div class="stat"><span class="label">{label}</span><span class="value">{value}</span></div>'
    for label, value in stats
) or '<div class="stat"><span class="value">ATLANTA BRAVES</span></div>'

braves_mark = f'<img src="{BRAVES_LOGO}" alt="ATL">' if SHOW_MLB_IMAGES else "ATL"
mlb_mark = f'<img src="{MLB_LOGO}" alt="MLB">' if SHOW_MLB_IMAGES else "MLB"

# ---------- Site header (logos are buttons) ----------
st.markdown(f"""
<div class="site-header">
    <div class="strip">{strip_html}</div>
    <div class="logos">
        <a href="/roster" target="_self" title="Braves roster and stats">
            <a href="/roster" target="_self" title="Braves roster and stats">
            {braves_mark}
        </a>
        <a href="/watch" target="_self" title="My players to watch">
            <a href="/watch" target="_self" title="My players to watch">
            {mlb_mark}
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------- Pages and top navigation ----------
pages = [
    st.Page("views/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("views/roster.py", title="Braves Roster", icon=":material/groups:", url_path="roster"),
    st.Page("views/watch.py", title="Players to Watch", icon=":material/star:", url_path="watch"),
    st.Page("views/field_view.py", title="Field View", icon=":material/sports_baseball:", url_path="field-view"),
       # st.Page("views/offseason.py", title="Offseason", icon=":material/swap_horiz:", url_path="offseason"),
]

pg = st.navigation(pages, position="top")
pg.run()