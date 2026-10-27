"""
Renders each platform's 26-week trend grid as a PNG for the digest.

Every panel is a single measure on its own axis (small multiples, never
dual axes). Weekly flows are bars with the latest week in full color;
running totals are lines.
"""

from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES = "#2a78d6"
SERIES_PAST = "#a9c9f0"
SERIES_2 = "#eb6834"
SERIES_2_PAST = "#f5b89f"


def short_number(n: float | None) -> str:
    if n is None:
        return "–"
    for limit, suffix in ((1_000_000, "M"), (1_000, "k")):
        if abs(n) >= limit:
            text = f"{n / limit:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return f"{n:.0f}"


def _change_text(this, prev) -> str:
    if this is None or not prev:
        return ""
    pct = (this - prev) / prev * 100
    return f"  ({'+' if pct >= 0 else '−'}{abs(pct):.0f}% vs week before)"


def _style(ax, title: str, subtitle: str, labels: list[str]) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=TEXT_PRIMARY, pad=18)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=TEXT_SECONDARY)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=8, length=0)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: short_number(v)))
    ticks = list(range(len(labels) - 1, -1, -4))[::-1]
    ax.set_xticks(ticks, [labels[i] for i in ticks])


def _week_label(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%-d %b")


def _bars(ax, title: str, unit: str, values: list, labels: list[str]) -> None:
    xs = [i for i, v in enumerate(values) if v is not None]
    colors = [SERIES if i == len(values) - 1 else SERIES_PAST for i in xs]
    ax.bar(xs, [values[i] for i in xs], width=0.7, color=colors)
    latest = values[-1]
    prev = values[-2] if len(values) > 1 else None
    _style(ax, title, f"Last week: {short_number(latest)} {unit}{_change_text(latest, prev)}", labels)


def _stacked(ax, title: str, a: tuple, b: tuple, labels: list[str]) -> None:
    (a_name, a_vals), (b_name, b_vals) = a, b
    n = len(a_vals)
    xs = list(range(n))
    a_vals = [v or 0 for v in a_vals]
    b_vals = [v or 0 for v in b_vals]
    ax.bar(xs, a_vals, width=0.7, color=[SERIES if i == n - 1 else SERIES_PAST for i in xs], label=a_name)
    ax.bar(xs, b_vals, width=0.7, bottom=a_vals,
           color=[SERIES_2 if i == n - 1 else SERIES_2_PAST for i in xs], label=b_name)
    subtitle = f"Last week: {short_number(a_vals[-1])} {a_name.lower()}, {short_number(b_vals[-1])} {b_name.lower()}"
    _style(ax, title, subtitle, labels)
    ax.legend(loc="upper left", fontsize=8, frameon=False, labelcolor=TEXT_SECONDARY, handlelength=1)


def _line(ax, title: str, unit: str, values: list, labels: list[str], estimated: list[bool] | None = None) -> None:
    estimated = estimated or [False] * len(values)
    pts = [(i, v) for i, v in enumerate(values) if v is not None]
    if pts:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=SERIES, linewidth=2,
                solid_capstyle="round", solid_joinstyle="round")
        for i, v in pts:
            hollow = estimated[i]
            ax.plot(i, v, "o", markersize=4 if i < len(values) - 1 else 7,
                    markerfacecolor=SURFACE if hollow else SERIES, markeredgecolor=SERIES, markeredgewidth=1.5)
        lo = min(p[1] for p in pts)
        hi = max(p[1] for p in pts)
        pad = max((hi - lo) * 0.15, hi * 0.005, 1)
        ax.set_ylim(lo - pad, hi + pad)
    ax.set_xlim(-0.6, len(values) - 0.4)
    latest = values[-1]
    prev = values[-2] if len(values) > 1 else None
    change = ""
    if latest is not None and prev is not None:
        diff = latest - prev
        change = f"  ({'+' if diff >= 0 else '−'}{short_number(abs(diff))} vs week before)"
    _style(ax, title, f"Now: {short_number(latest)} {unit}{change}", labels)


def _figure(suptitle: str, note: str):
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    fig.suptitle(suptitle, x=0.01, ha="left", fontsize=13, fontweight="bold", color=TEXT_PRIMARY)
    fig.text(0.01, 0.005, note, fontsize=8, color=TEXT_SECONDARY)
    return fig, axes


def youtube_chart(weekly: list[dict], subscribers: list[int], path: str) -> str:
    labels = [_week_label(w["end"]) for w in weekly]
    fig, axes = _figure(
        "YouTube — last 26 weeks",
        f"Each bar is one 7-day week; the dark bar is the latest ({weekly[-1]['start']} to {weekly[-1]['end']}).",
    )
    _line(axes[0][0], "Subscribers", "subscribers", subscribers, labels)
    _bars(axes[0][1], "Views per week", "views", [w["views"] for w in weekly], labels)
    _bars(axes[1][0], "Watch time per week", "hours",
          [round(w["estimatedMinutesWatched"] / 60) for w in weekly], labels)
    _stacked(axes[1][1], "Likes and comments per week",
             ("Likes", [w["likes"] for w in weekly]), ("Comments", [w["comments"] for w in weekly]), labels)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97), h_pad=2.5, w_pad=3)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def instagram_chart(weekly: list[dict], followers: list[dict], path: str) -> str:
    labels = [_week_label(w["end"]) for w in weekly]
    note = f"Each bar is one 7-day week; the dark bar is the latest ({weekly[-1]['start']} to {weekly[-1]['end']})."
    if any(f["estimated"] for f in followers):
        note += " Hollow follower points are estimates (Instagram reports new followers, not unfollows)."
    fig, axes = _figure("Instagram — last 26 weeks", note)
    _line(axes[0][0], "Followers", "followers", [f["followers"] for f in followers], labels,
          [f["estimated"] for f in followers])
    _bars(axes[0][1], "Accounts reached per week", "accounts", [w.get("reach") for w in weekly], labels)
    _bars(axes[1][0], "Views per week", "views", [w.get("views") for w in weekly], labels)
    _bars(axes[1][1], "Interactions per week", "likes, comments, shares and saves",
          [w.get("total_interactions") for w in weekly], labels)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97), h_pad=2.5, w_pad=3)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path
