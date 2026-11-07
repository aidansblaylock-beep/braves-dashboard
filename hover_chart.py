import base64
import io
import requests
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.colors import to_hex
from pybaseball import plot_stadium

LINE = "#6b7785"
WALL = "#0b1f3a"
RING = "#c9d3e0"
HOME_RAW = (125.42, -198.27)    # home plate in the raw hit-coordinate space


def _to_feet(df):
    x = 2.5 * (df["hc_x"] - 125.42)
    y = 2.5 * (198.27 - df["hc_y"])
    return x.to_numpy(dtype=float), y.to_numpy(dtype=float)


def _line(x, y, color, width, dash=None):
    return go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=width, dash=dash),
                      hoverinfo="skip", showlegend=False)


def _generic_field_traces():
    fence = 400
    c = np.cos(np.pi / 4)
    theta = np.linspace(np.pi / 4, 3 * np.pi / 4, 120)
    traces = [
        _line([0, fence * c], [0, fence * c], LINE, 1.5),
        _line([0, -fence * c], [0, fence * c], LINE, 1.5),
        _line(fence * np.cos(theta), fence * np.sin(theta), WALL, 3),
        _line([0, 63.64, 0, -63.64, 0], [0, 63.64, 127.28, 63.64, 0], LINE, 1.2),
    ]
    for r in (150, 250, 350):
        traces.append(_line(r * np.cos(theta), r * np.sin(theta), RING, 1, "dash"))
    traces.append(go.Scatter(
        x=[0, 0, 0], y=[158, 258, 358], mode="text", text=["150 ft", "250 ft", "350 ft"],
        textfont=dict(size=10, color="#8a96a6"), hoverinfo="skip", showlegend=False,
    ))
    return traces


@st.cache_data(show_spinner=False)
def _park_background(park_key):
    """Lets pybaseball draw the park, then saves that drawing as a transparent picture
    that exactly fills the chart's coordinate range."""
    plot_stadium(park_key)
    fig = plt.gcf()
    ax = plt.gca()

    xmin, xmax = sorted(ax.get_xlim())
    ymin, ymax = sorted(ax.get_ylim())
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_title("")
    legend = ax.get_legend()
    if legend is not None:
        legend.remove()
    ax.set_aspect("auto")
    ax.axis("off")
    ax.set_position([0, 0, 1, 1])          # drawing fills the whole picture
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    fig.set_size_inches(9, 9 * (ymax - ymin) / (xmax - xmin))

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, transparent=True)
    plt.close(fig)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return encoded, (xmin, xmax), (ymin, ymax)


# ---------- Pitcher names ----------
@st.cache_resource
def _pitcher_name_cache():
    """A dictionary that lives as long as the app, so each name is only looked up once."""
    return {}


def lookup_pitcher_names(ids):
    """Statcast gives pitchers as ID numbers, so ask MLB's API for the names we don't have yet."""
    cache = _pitcher_name_cache()
    missing = sorted({int(i) for i in ids if pd.notna(i)} - set(cache))
    for start in range(0, len(missing), 100):
        chunk = missing[start:start + 100]
        try:
            resp = requests.get(
                "https://statsapi.mlb.com/api/v1/people",
                params={"personIds": ",".join(str(i) for i in chunk)},
                timeout=20,
            )
            for p in resp.json().get("people", []):
                cache[int(p["id"])] = p["fullName"]
        except Exception:
            pass       # a failed lookup just means those tooltips skip the pitcher line
    return cache


def _has(v):
    return v is not None and pd.notna(v)


def _hover_text(r, title, names):
    lines = [f"<b>{title}</b>"]
    if _has(r.get("game_date")):
        lines.append(str(r["game_date"])[:10])
    if _has(r.get("away_team")) and _has(r.get("home_team")):
        lines.append(f"{r['away_team']} @ {r['home_team']}")
    if _has(r.get("hit_distance_sc")):
        lines.append(f"Distance: {r['hit_distance_sc']:.0f} ft")
    if _has(r.get("launch_speed")):
        lines.append(f"Exit velo: {r['launch_speed']:.1f} mph")
    if _has(r.get("launch_angle")):
        lines.append(f"Launch angle: {r['launch_angle']:.0f}°")
    if _has(r.get("pitcher")):
        pitcher = names.get(int(r["pitcher"]))
        if pitcher:
            lines.append(f"Pitcher: {pitcher}")
    if _has(r.get("pitch_name")):
        speed = f" at {r['release_speed']:.1f} mph" if _has(r.get("release_speed")) else ""
        lines.append(f"Pitch: {r['pitch_name']}{speed}")
    return "<br>".join(lines)

def _place_homers_at_true_distance(px, py, origin, outcomes, dist, feet_per_unit):
    """Keep each home run's recorded direction, but place it at its projected distance."""
    ox, oy = origin
    dx, dy = px - ox, py - oy
    r = np.hypot(dx, dy)
    mask = (outcomes == "Home Run") & ~np.isnan(dist) & (r > 0)
    factor = np.ones_like(r)
    factor[mask] = (dist[mask] / feet_per_unit) / r[mask]
    return ox + dx * factor, oy + dy * factor

def build_hover_chart(shown, generic, park_key, show_arcs, by_distance, outcomes,
                      outcome_colors, dist_cmap, dist_norm, height_boost):
    fig = go.Figure()

    # ----- Field outline and coordinates -----
    if generic:
        px, py = _to_feet(shown)
        origin = (0.0, 0.0)
        for t in _generic_field_traces():
            fig.add_trace(t)
        xr, yr = [-330.0, 330.0], [-25.0, 470.0]
    else:
        px = shown["hc_x"].to_numpy(dtype=float)
        py = -shown["hc_y"].to_numpy(dtype=float)
        origin = HOME_RAW
        image, xlim, ylim = _park_background(park_key)
        xr, yr = [xlim[0], xlim[1]], [ylim[0], ylim[1]]
        fig.add_layout_image(dict(
            source=f"data:image/png;base64,{image}",
            xref="x", yref="y", x=xlim[0], y=ylim[1],
            sizex=xlim[1] - xlim[0], sizey=ylim[1] - ylim[0],
            sizing="stretch", layer="below", xanchor="left", yanchor="top",
        ))

    # ----- Put home runs at their projected distance (same direction, true length) -----
    if "hit_distance_sc" in shown.columns:
        px, py = _place_homers_at_true_distance(
            px, py, origin, shown["Outcome"].to_numpy(),
            shown["hit_distance_sc"].to_numpy(dtype=float),
            feet_per_unit=1.0 if generic else 2.5,
        )

    # ----- Pitcher names for the tooltips -----
    names = {}
    if "pitcher" in shown.columns:
        with st.spinner("Looking up pitcher names..."):
            names = lookup_pitcher_names(shown["pitcher"].dropna().astype(int).unique())

    records = shown.to_dict("records")
    arc_top = None

    if show_arcs:
        n = len(shown)
        dist = (shown["hit_distance_sc"].to_numpy(dtype=float)
                if "hit_distance_sc" in shown.columns else np.full(n, np.nan))
        angle = (shown["launch_angle"].to_numpy(dtype=float)
                 if "launch_angle" in shown.columns else np.full(n, np.nan))
        use_dist = by_distance and not np.isnan(dist).all()

        t = np.linspace(0, 1, 50)
        x0, y0 = origin
        arcs, shadow_x, shadow_y, tops = [], [], [], []
        for i in np.argsort(np.nan_to_num(dist, nan=0.0)):     # longest drawn last, on top
            x1, y1 = px[i], py[i]
            gx = x0 + t * (x1 - x0)
            gy = y0 + t * (y1 - y0)
            length = np.hypot(x1 - x0, y1 - y0)
            ang = angle[i] if not np.isnan(angle[i]) else 28.0
            ratio = float(np.clip(np.tan(np.radians(ang)) / 4 * height_boost, 0.12, 0.45))
            ay = gy + ratio * length * 4 * t * (1 - t)
            tops.append(ay.max())
            shadow_x += list(gx) + [None]
            shadow_y += list(gy) + [None]
            if use_dist and not np.isnan(dist[i]):
                color = to_hex(dist_cmap(dist_norm(dist[i])))
            elif use_dist:
                color = "#9aa5b1"
            else:
                color = outcome_colors["Home Run"]
            arcs.append((gx, ay, color, i))
        arc_top = max(tops)

        fig.add_trace(go.Scatter(x=shadow_x, y=shadow_y, mode="lines",
                                 line=dict(color="rgba(11,31,58,0.18)", width=1),
                                 hoverinfo="skip", showlegend=False))
        for gx, ay, color, i in arcs:
            fig.add_trace(go.Scatter(x=gx, y=ay, mode="lines", opacity=0.85,
                                     line=dict(color=color, width=2.6),
                                     hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(
            x=[px[a[3]] for a in arcs], y=[py[a[3]] for a in arcs], mode="markers",
            marker=dict(size=10, color=[a[2] for a in arcs], line=dict(color="white", width=1)),
            text=[_hover_text(records[a[3]], "Home Run", names) for a in arcs],
            hoverinfo="text", showlegend=False,
        ))
        if use_dist:
            scale = [[float(v), to_hex(dist_cmap(float(v)))] for v in np.linspace(0, 1, 5)]
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="markers", hoverinfo="skip", showlegend=False,
                marker=dict(colorscale=scale, cmin=dist_norm.vmin, cmax=dist_norm.vmax,
                            color=[dist_norm.vmin], showscale=True,
                            colorbar=dict(title="Distance (ft)", thickness=14, len=0.6)),
            ))
    else:
        outcome_col = shown["Outcome"].to_numpy()
        for outcome in outcomes:
            idx = np.where(outcome_col == outcome)[0]
            if len(idx) == 0:
                continue
            fig.add_trace(go.Scatter(
                x=px[idx], y=py[idx], mode="markers",
                marker=dict(size=9, color=outcome_colors[outcome], opacity=0.9,
                            line=dict(color="white", width=0.8)),
                text=[_hover_text(records[i], outcome, names) for i in idx],
                hoverinfo="text", showlegend=False,
            ))

    if arc_top is not None:
        yr[1] = max(yr[1], arc_top + 0.05 * (yr[1] - yr[0]))
            # Widen the frame if a long homer lands beyond the original edges
    pad = 0.04 * (yr[1] - yr[0])
    xr[0] = min(xr[0], float(np.nanmin(px)) - pad)
    xr[1] = max(xr[1], float(np.nanmax(px)) + pad)
    yr[1] = max(yr[1], float(np.nanmax(py)) + pad)

    fig.update_xaxes(range=xr, visible=False)
    fig.update_yaxes(range=yr, visible=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(
        height=640, margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", hoverlabel=dict(bgcolor="white", font_size=13),
    )
    return fig