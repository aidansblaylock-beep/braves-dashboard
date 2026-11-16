import html
from datetime import datetime
import streamlit as st
from data import load_player_profile, headshot_url

STYLE = """
<style>
.pc-card {
    background: #ffffff; border: 1px solid #e3e8ef; border-left: 4px solid #d6001c;
    border-radius: 10px; overflow: hidden; box-shadow: 0 1px 2px rgba(11, 31, 58, 0.06);
}
.pc-band {
    background: #0b1f3a; border-bottom: 4px solid #d6001c; padding: 12px 18px;
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.pc-name { color: #ffffff; font-size: 1.5rem; font-weight: 800; line-height: 1.15; }
.pc-sub { color: #9fb0c8; font-size: 0.85rem; font-weight: 600; margin-top: 2px; }
.pc-num { color: #ffffff; font-size: 1.8rem; font-weight: 800; opacity: 0.9; }
.pc-body { display: flex; flex-wrap: wrap; gap: 18px; padding: 16px 18px; align-items: flex-start; }
.pc-photo {
    width: 140px; height: 140px; border-radius: 8px; object-fit: cover; object-position: top;
    background: #e3e8ef; border: 2px solid #ffffff; box-shadow: 0 0 0 1px #d5dce6; flex-shrink: 0;
}
.pc-info {
    flex: 1; min-width: 220px; display: grid; gap: 12px 16px;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}
.pc-label { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em; color: #5b6b82; text-transform: uppercase; }
.pc-value { font-size: 0.95rem; font-weight: 700; color: #0b1f3a; }
.pc-nick { color: #5b6b82; font-style: italic; font-size: 0.9rem; padding: 0 18px 14px; }
.pc-sec { font-size: 1.1rem; font-weight: 800; color: #0b1f3a; margin: 18px 0 6px; padding-bottom: 4px; border-bottom: 2px solid #e3e8ef; }
.pc-scroll { overflow-x: auto; }
.pc-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.pc-table th {
    text-align: right; font-size: 0.66rem; letter-spacing: 0.07em; text-transform: uppercase;
    color: #5b6b82; border-bottom: 2px solid #0b1f3a; padding: 6px 8px; white-space: nowrap;
}
.pc-table td {
    text-align: right; padding: 7px 8px; border-bottom: 1px solid #eef1f5; color: #0b1f3a;
    font-variant-numeric: tabular-nums; white-space: nowrap;
}
.pc-table th:nth-child(-n+2), .pc-table td:nth-child(-n+2) { text-align: left; }
.pc-table tr.career td { background: #fdecee; font-weight: 800; border-top: 2px solid #0b1f3a; }
.pc-empty { color: #8a96a6; font-size: 0.9rem; padding: 8px 0; }
</style>
"""


def _pretty_date(iso):
    """'1997-12-18' -> 'Dec 18, 1997' (blank if missing)."""
    if not iso:
        return ""
    d = datetime.strptime(iso, "%Y-%m-%d")
    return f"{d:%b} {d.day}, {d.year}"


def _fact(label, value):
    """One label/value pair on the card. Skipped if there's no value."""
    if not value:
        return ""
    return (
        '<div><div class="pc-label">' + label + "</div>"
        '<div class="pc-value">' + html.escape(str(value)) + "</div></div>"
    )


def card_html(bio):
    """The front of the baseball card. bio is the 'bio' dict from load_player_profile()."""
    sub = " &middot; ".join(html.escape(x) for x in (bio["team"], bio["pos_name"]) if x)
    number = ""
    if bio["number"]:
        number = '<span class="pc-num">#' + html.escape(str(bio["number"])) + "</span>"
    nick = ""
    if bio["nickname"]:
        nick = '<div class="pc-nick">&ldquo;' + html.escape(bio["nickname"]) + "&rdquo;</div>"

    weight = f"{bio['weight']} lbs" if bio["weight"] else ""
    bats_throws = f"{bio['bats']} / {bio['throws']}" if bio["bats"] and bio["throws"] else ""

    facts = (
        _fact("Age", bio["age"])
        + _fact("Born", _pretty_date(bio["birth_date"]))
        + _fact("Birthplace", bio["birth_place"])
        + _fact("Height", bio["height"])
        + _fact("Weight", weight)
        + _fact("Bats / Throws", bats_throws)
        + _fact("MLB Debut", _pretty_date(bio["debut"]))
    )

    return (
        '<div class="pc-card">'
        '<div class="pc-band"><div>'
        '<div class="pc-name">' + html.escape(bio["name"]) + "</div>"
        '<div class="pc-sub">' + sub + "</div></div>" + number + "</div>"
        + nick +
        '<div class="pc-body">'
        '<img class="pc-photo" src="' + headshot_url(bio["id"], 240) + '" alt="">'
        '<div class="pc-info">' + facts + "</div></div></div>"
    )

# Table columns: (label shown on the page, field name from the API)
HIT_TABLE = [
    ("G", "gamesPlayed"), ("AB", "atBats"), ("H", "hits"), ("HR", "homeRuns"),
    ("RBI", "rbi"), ("BB", "baseOnBalls"), ("SO", "strikeOuts"), ("SB", "stolenBases"),
    ("AVG", "avg"), ("OBP", "obp"), ("SLG", "slg"), ("OPS", "ops"),
]
PIT_TABLE = [
    ("G", "gamesPlayed"), ("GS", "gamesStarted"), ("W", "wins"), ("L", "losses"),
    ("SV", "saves"), ("IP", "inningsPitched"), ("ERA", "era"), ("WHIP", "whip"),
    ("SO", "strikeOuts"), ("BB", "baseOnBalls"), ("K/9", "strikeoutsPer9Inn"),
]


def groups_for(bio):
    """Which stat tables a player gets: pitchers P, two-way players both, everyone else hitting."""
    if bio["pos"] == "P":
        return ["pitching"]
    if bio["pos"] == "TWP":
        return ["hitting", "pitching"]
    return ["hitting"]


def stats_table_html(title, group_stats, columns):
    """One stats table: a row per MLB season, then a Career row.
    group_stats is profile['stats']['hitting'] or ['pitching']."""
    seasons = group_stats["seasons"]
    heading = '<div class="pc-sec">' + title + "</div>"
    if not seasons:
        return heading + '<div class="pc-empty">No MLB stats yet.</div>'

    def row(year, team, stat, cls=""):
        cells = "<td>" + html.escape(str(year)) + "</td><td>" + html.escape(team) + "</td>"
        for _, key in columns:
            val = stat.get(key)
            cells += "<td>" + (html.escape(str(val)) if val is not None else "-") + "</td>"
        attr = ' class="' + cls + '"' if cls else ""
        return "<tr" + attr + ">" + cells + "</tr>"

    head = "<th>Year</th><th>Team</th>" + "".join("<th>" + label + "</th>" for label, _ in columns)
    body = "".join(row(s["season"], s["team"], s["stat"]) for s in seasons)
    if group_stats["career"]:
        body += row("Career", "MLB", group_stats["career"], "career")

    return (
        heading + '<div class="pc-scroll"><table class="pc-table"><thead><tr>' + head +
        "</tr></thead><tbody>" + body + "</tbody></table></div>"
    )

def _clear_player():
    """Runs when the popup is closed: remove ?player= from the web address,
    so the popup doesn't reopen the next time the page reruns."""
    if "player" in st.query_params:
        del st.query_params["player"]


@st.dialog("Player Card", width="large", on_dismiss=_clear_player)
def _player_popup(player_id):
    try:
        profile = load_player_profile(player_id)
    except Exception:
        st.info("Couldn't load this player right now. Please try again in a moment.")
        return

    if profile is None:
        st.info("We couldn't find that player.")
        return

    bio = profile["bio"]
    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown(card_html(bio), unsafe_allow_html=True)

    tables = ""
    for group in groups_for(bio):
        if group == "hitting":
            tables += stats_table_html("Hitting", profile["stats"]["hitting"], HIT_TABLE)
        else:
            tables += stats_table_html("Pitching", profile["stats"]["pitching"], PIT_TABLE)
    st.markdown(tables, unsafe_allow_html=True)


def show_player_popup_if_requested():
    """Call this once from app.py. Opens the popup if the address has ?player=ID."""
    player_id = st.query_params.get("player", "")
    if player_id.isdigit():
        _player_popup(int(player_id))