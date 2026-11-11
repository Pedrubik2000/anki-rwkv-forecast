"""HTML for the forecast: the text under "Studied … today" in the deck list, and the dot bar
in deck options. Plain HTML, no scripts. Deck-list counts call pycmd("rwkvfc:browse:<cids>").
"""

from __future__ import annotations

import html

from .engine import Forecast

NOTE = "if you stop reviewing now"

CSS = """
#rwkvfc { margin: 0.4em auto 1em; font-size: 0.95em; }
#rwkvfc .note { opacity: .6; font-size: .85em; }
#rwkvfc a.n { cursor: pointer; color: inherit; text-decoration: underline dotted; }
#rwkvfc .due { color: #d32f2f; } #rwkvfc .near { color: #ef6c00; } #rwkvfc .safe { color: #2e7d32; }
.night-mode #rwkvfc .due { color: #ef5350; } .night-mode #rwkvfc .near { color: #ffa726; }
.night-mode #rwkvfc .safe { color: #66bb6a; }
"""


def split(fc: Forecast, cids, i: int, margin: float, target=None) -> dict[str, list[int]]:
    """due / near / safe at time index i; `target` overrides each card's own target."""
    g: dict[str, list[int]] = {"due": [], "near": [], "safe": []}
    for cid in cids:
        r, t = fc.cards[cid]["r"][i], target if target is not None else fc.cards[cid]["target"]
        g["due" if r < t else "near" if r < t + margin else "safe"].append(cid)
    return g


def _a(cids, text, cls=""):
    if not cids:
        return f'<span class="{cls}">{text}</span>'
    ids = ",".join(str(c) for c in cids)
    return f'<a class="n {cls}" onclick="pycmd(\'rwkvfc:browse:{ids}\');return false;">{text}</a>'


def deck_list_text(fc: Forecast | None, conf: dict, status: str) -> str:
    """`due | near | safe` now, then the count line, then the recall graph (`deck_list_graph`)."""
    head = f'<b>RWKV forecast</b> <span class="note">{NOTE}'
    if fc is None or not fc.cards:
        msg = status or ("no review cards" if fc is not None else "computing…")
        return f'<div id="rwkvfc"><style>{CSS}</style>{head} · {html.escape(msg)}</span></div>'
    margin = float(conf["near_margin"])
    cids = list(fc.cards)
    now = split(fc, cids, 0, margin)
    parts = [
        _a(now["due"], f"due {len(now['due'])}", "due") + " | "
        + _a(now["near"], f"near {len(now['near'])}", "near") + " | "
        + _a(now["safe"], f"safe {len(now['safe'])}", "safe")
    ]
    if conf["count_line"]:
        due0 = set(now["due"])
        soon = []
        for label, text in (("1h", "1 h"), ("3h", "3 h")):
            due_t = split(fc, cids, fc.index(label), margin)["due"]
            ids = [c for c in due_t if c not in due0]
            soon.append(_a(ids, f"+{len(ids)} in {text}"))
        tom = split(fc, cids, fc.index("tomorrow"), margin)["due"]
        parts.append(" · ".join([_a(now["due"], f"due {len(now['due'])}", "due"), *soon,
                                 _a(tom, f"{len(tom)} by tomorrow")]))
    graph = deck_list_graph(fc, conf) if conf.get("deck_list_graph", True) else ""
    return (f'<div id="rwkvfc"><style>{CSS}</style><div>{head}</span></div>'
            + "".join(f"<div>{p}</div>" for p in parts) + graph + "</div>")


GRAPH_CSS = """
#rwkvfc fieldset { width: 520px; max-width: 90vw; box-sizing: border-box; margin: .6em auto 0; padding: 4px 10px 6px;
  border: 1px solid rgba(128,128,128,.5); border-radius: 4px; }
#rwkvfc legend { font-size: .85em; opacity: .7; padding: 0 4px; }
#rwkvfc .recall { position: relative; margin: 6px 4px 0; border-bottom: 1px solid #999; }
#rwkvfc .recall i { position: absolute; width: 6px; height: 6px; border-radius: 50%; margin-left: -3px; }
#rwkvfc .recall i.due { background: #e53935; } #rwkvfc .recall i.near { background: #e65100; }
#rwkvfc .recall i.safe { background: #43a047; }
#rwkvfc .recall b { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: #e53935; }
#rwkvfc .recall s { position: absolute; top: 0; bottom: 0; background: rgba(230, 81, 0, .16); }
#rwkvfc .axis { position: relative; height: 14px; margin: 0 4px; font-size: 10px; opacity: .7; }
#rwkvfc .axis span { position: absolute; transform: translateX(-50%); }
#rwkvfc .axis span:first-child { transform: none; } #rwkvfc .axis span:last-child { transform: translateX(-100%); }
"""


def deck_list_graph(fc: Forecast, conf: dict) -> str:
    """kuma3 desktop's RWKV recall box: a dot per review card at its recall now, stacked where they meet,
    a red line at each desired retention and the "near" band beside it."""
    lo, margin = float(conf["bar_axis_min"]), float(conf["near_margin"])
    pct = lambda r: max(0.0, min(1.0, (r - lo) / (1 - lo))) * 100
    order = sorted(fc.cards, key=lambda c: fc.cards[c]["r"][0])
    bins = [int(pct(fc.cards[c]["r"][0]) / 0.9) for c in order]  # about a dot wide
    tallest = max((bins.count(b) for b in set(bins)), default=1)
    step = min(7.0, 60 / max(1, tallest))
    stacks: dict[int, int] = {}
    dots = []
    for cid, b in zip(order, bins):
        r, t = fc.cards[cid]["r"][0], fc.cards[cid]["target"]
        n = stacks[b] = stacks.get(b, 0) + 1
        k = "due" if r < t else "near" if r < t + margin else "safe"
        dots.append(f'<i class="{k}" style="left:{pct(r):.2f}%;bottom:{(n - 1) * step + 1:.1f}px"'
                    f' title="R {r * 100:.1f}%"></i>')
    lines = "".join(
        f'<s style="left:{pct(t):.2f}%;width:{pct(t + margin) - pct(t):.2f}%"></s><b style="left:{pct(t):.2f}%"></b>'
        for t in sorted({fc.cards[c]["target"] for c in order})
    )
    ticks = "".join(f'<span style="left:{k * 25}%">{round((lo + (1 - lo) * k / 4) * 100)}%</span>' for k in range(5))
    return (
        f"<style>{GRAPH_CSS}</style><fieldset><legend>RWKV recall now · red line = desired retention</legend>"
        f'<div class="recall" style="height:{(tallest - 1) * step + 10:.0f}px">{lines}{"".join(dots)}</div>'
        f'<div class="axis">{ticks}</div></fieldset>'
    )


# ---------------------------------------------------------------- deck options bar

BAR_CSS = """
#rwkvfc-dr .bar { position: relative; margin: .8em 6px 0; border-bottom: 1px solid rgba(128,128,128,.5); }
#rwkvfc-dr .dot { position: absolute; width: 7px; height: 7px; border-radius: 50%; margin-left: -3.5px; }
#rwkvfc-dr .dot.due { background: #ef5350; } #rwkvfc-dr .dot.near { background: #ffa726; }
#rwkvfc-dr .dot.safe { background: #66bb6a; }
#rwkvfc-dr .target { position: absolute; top: -4px; bottom: 0; width: 2px; background: #ef5350; margin-left: -1px; }
#rwkvfc-dr .axis { position: relative; height: 14px; margin: 0 6px .8em; font-size: 10px; opacity: .6; }
#rwkvfc-dr .axis span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
"""
DOT_STEP = 6  # px between stacked dots (less when the tallest stack would pass MAX_HEIGHT)
MAX_HEIGHT = 70
BIN = 0.006  # recall width of one stack (about one dot wide in the options column)


def options_bar(fc: Forecast, cids, target: float, conf: dict, names: dict[int, str]) -> str:
    """One dot per card at its recall now; red line and colours at `target` (the selected DR)."""
    lo, margin = float(conf["bar_axis_min"]), float(conf["near_margin"])
    pct = lambda r: max(0.0, min(1.0, (r - lo) / (1 - lo))) * 100
    order = sorted(cids, key=lambda c: fc.cards[c]["r"][0])
    bins = [int(max(fc.cards[c]["r"][0], lo) / BIN) for c in order]
    tallest = max((bins.count(b) for b in set(bins)), default=1)
    step = min(DOT_STEP, (MAX_HEIGHT - 7) / max(1, tallest - 1))
    stacks: dict[int, int] = {}
    dots = []
    for cid, b in zip(order, bins):
        r = fc.cards[cid]["r"][0]
        n = stacks[b] = stacks.get(b, 0) + 1
        k = "due" if r < target else "near" if r < target + margin else "safe"
        tip = html.escape(f"{names.get(cid, '')}\nR {r * 100:.1f}%")
        dots.append(f'<div class="dot {k}" style="left:{pct(r):.2f}%;bottom:{(n - 1) * step:.1f}px" title="{tip}"></div>')
    height = (tallest - 1) * step + 11
    ticks = "".join(
        f'<span style="left:{(v - lo) / (1 - lo) * 100:.1f}%">{round(v * 100)}%</span>'
        for v in [lo + (1 - lo) * k / 4 for k in range(5)]
    )
    return (
        f"<style>{BAR_CSS}</style>"
        f'<div class="bar" style="height:{height}px"><div class="target" style="left:{pct(target):.2f}%"></div>'
        f'{"".join(dots)}</div><div class="axis">{ticks}</div>'
    )
