import html
import streamlit as st

# >>> CHANGE THIS to your real GitHub repo URL <<<
GITHUB_URL = "https://github.com/aidansblaylock-beep"

STYLE = """
<style>
.ab-card {
    background: #ffffff; border: 1px solid #e3e8ef; border-left: 4px solid #d6001c;
    border-radius: 8px; padding: 16px 20px; margin-bottom: 14px;
    box-shadow: 0 1px 2px rgba(11, 31, 58, 0.06);
}
.ab-title { font-weight: 800; color: #0b1f3a; font-size: 1.05rem; margin-bottom: 6px; }
.ab-card p, .ab-card li { color: #44556d; font-size: 0.95rem; line-height: 1.55; margin: 0 0 4px; }
.ab-card ul { margin: 4px 0 0 18px; padding: 0; }
.ab-card a { color: #d6001c; font-weight: 700; text-decoration: none; }
.ab-card a:hover { text-decoration: underline; }
</style>
"""


def card(title, body_html):
    """One About section. body_html is our own fixed text, not API data."""
    return (
        '<div class="ab-card"><div class="ab-title">' + title + "</div>"
        + body_html + "</div>"
    )


st.markdown(STYLE, unsafe_allow_html=True)
st.header("About")

st.markdown(card(
    "What this is",
    "<p>An unofficial, fan-built dashboard for following the Atlanta Braves and "
    "players around baseball. It has standings, roster stats, a live Today&rsquo;s Game card, "
    "a list of players to watch, a spray-chart Field View, and a prospects explorer. "
    "It&rsquo;s a learning project, built to practice Python, data analysis, and "
    "dashboard design.</p>",
), unsafe_allow_html=True)

st.markdown(card(
    "Data sources",
    "<ul>"
    "<li>The free <b>MLB Stats API</b> for standings, schedules, rosters, player stats, "
    "transactions, and prospects.</li>"
    "<li><b>pybaseball</b>, a Python library that pulls Statcast data (hit locations, "
    "exit velocity, distance) from <b>Baseball Savant</b>. It powers the Field View.</li>"
    "</ul>",
), unsafe_allow_html=True)

st.markdown(card(
    "How it&rsquo;s built",
    "<ul>"
    "<li><b>Python</b> with <b>Streamlit</b> for the multi-page app</li>"
    "<li><b>pandas</b> and <b>NumPy</b> for data handling</li>"
    "<li><b>Plotly</b> and <b>Matplotlib</b> for charts</li>"
    "<li>Hosted on <b>Streamlit Community Cloud</b> from a public GitHub repository</li>"
    "</ul>",
), unsafe_allow_html=True)

st.markdown(card(
    "Built with AI assistance",
    "<p>I built this project with help from Claude, an AI assistant made by Anthropic. "
    "I worked step by step and tested each piece as I went. It&rsquo;s part of how "
    "I&rsquo;m learning Python and data analysis.</p>",
), unsafe_allow_html=True)

st.markdown(card(
    "Source code",
    '<p>The full code is public on <a href="' + html.escape(GITHUB_URL) +
    '" target="_blank" rel="noopener noreferrer">GitHub</a>.</p>',
), unsafe_allow_html=True)

st.caption(
    "Unofficial fan project, not affiliated with or endorsed by Major League Baseball "
    "or the Atlanta Braves."
)