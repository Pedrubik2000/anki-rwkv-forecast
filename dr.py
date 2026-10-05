"""Deck options: due | near | safe now, current vs the desired retention you are typing.

The page's own "New card intervals at graduation" table has headers "Current DR (90.00%)" and
"Selected DR (85.00%)" that follow the input live (the selected one is a small input box); the page script reads the selected DR and the
preset name from there and asks Python for the counts, which go in a table right under it.
Recall does not depend on the target, so the same forecast is counted against two targets.
"""

from __future__ import annotations

import html
import json

# runs in the deck options page; sends "rwkvfc:dr:{preset, selected}" whenever either changes
PAGE_JS = r"""
(function () {
  if (window.__rwkvfcDr) return;
  window.__rwkvfcDr = true;
  const send = m => (window.pycmd || window.bridgeCommand)(m);
  let last = '';
  function intervalsTable() {
    return [...document.querySelectorAll('table')].find(t => /Selected DR\s*\(/.test(t.textContent));
  }
  window.rwkvfcDrShow = function (markup) {
    const t = intervalsTable();
    if (!t) return;
    // go below the table's own scroll area, not inside it
    let anchor = t;
    for (let p = t.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowY;
      if (o === 'auto' || o === 'scroll') { anchor = p; break; }
      if (p.querySelectorAll('table').length > 1 || /Optimize/.test(p.textContent)) break;
    }
    let box = document.getElementById('rwkvfc-dr');
    if (!box) { box = document.createElement('div'); box.id = 'rwkvfc-dr'; }
    if (anchor.nextSibling !== box) anchor.after(box);
    box.innerHTML = markup;
  };
  function check() {
    const t = intervalsTable();
    if (!t) return;
    // the selected value sits in a small input inside the header (older builds: plain text)
    const box = t.querySelector('.target-dr-input');
    const m = box ? box.value.match(/([\d.]+)\s*%/) : t.textContent.match(/Selected DR\s*\(([\d.]+)%/);
    const label = document.querySelector('.select-container .label');
    if (!m || !label) return;
    const preset = label.textContent.replace(/\s*\([^()]*\)\s*$/, '').replace(/[⁨⁩]/g, '').trim();
    const msg = JSON.stringify({preset: preset, selected: parseFloat(m[1]) / 100});
    if (msg !== last || !document.getElementById('rwkvfc-dr')) { last = msg; send('rwkvfc:dr:' + msg); }
  }
  // react to typing at once: the page updates its Selected DR a few frames after the input event
  function soon() { [0, 40, 120, 300].forEach(ms => setTimeout(check, ms)); }
  document.addEventListener('input', soon, true);
  document.addEventListener('change', soon, true);
  document.addEventListener('click', soon, true);  // preset switch, spin buttons
  setInterval(check, 1000);  // anything else (e.g. reset button)
  check();
})();
"""

CSS = """
#rwkvfc-dr { margin-top: .8em; }
#rwkvfc-dr .t { font-weight: bold; margin-bottom: .3em; }
#rwkvfc-dr .note { font-weight: normal; opacity: .6; font-size: .85em; }
#rwkvfc-dr table { width: 100%; border-collapse: collapse; }
#rwkvfc-dr td, #rwkvfc-dr th { border: 1px solid var(--border, rgba(128,128,128,.5)); padding: .35em .5em; text-align: left; }
#rwkvfc-dr .due { color: #ef5350; } #rwkvfc-dr .near { color: #ffa726; } #rwkvfc-dr .safe { color: #66bb6a; }
#rwkvfc-dr .due, #rwkvfc-dr .near, #rwkvfc-dr .safe { font-weight: bold; }
"""


def preset_map(col, cids, home_did: dict[int, int]) -> dict[str, list[int]]:
    """Preset name -> its review cards (by home deck). Built in the background with the forecast, so
    answering the page needs no collection access (the backend may be busy with the page's own work)."""
    conf_of_did = {d.id: col.decks.config_dict_for_deck_id(d.id)["id"] for d in col.decks.all_names_and_ids()}
    name_of_conf = {c["id"]: c["name"] for c in col.decks.all_config()}
    out: dict[str, list[int]] = {name: [] for name in name_of_conf.values()}
    for cid in cids:
        conf = conf_of_did.get(home_did.get(cid))
        if conf in name_of_conf:
            out[name_of_conf[conf]].append(cid)
    return out


def table(fc, cids: list[int], selected: float, margin: float) -> str:
    def split(target_of):
        g = {"due": 0, "near": 0, "safe": 0}
        for cid in cids:
            r, t = fc.cards[cid]["r"][0], target_of(cid)
            g["due" if r < t else "near" if r < t + margin else "safe"] += 1
        return g

    cur = split(lambda cid: fc.cards[cid]["target"])
    sel = split(lambda cid: selected)
    targets = sorted({round(fc.cards[c]["target"] * 100, 2) for c in cids})
    cur_label = "/".join(f"{t:g}%" for t in targets) or "–"
    rows = "".join(
        f'<tr><td class="{k}">{k}</td><td>{cur[k]}</td><td>{sel[k]}</td></tr>' for k in ("due", "near", "safe")
    )
    return (
        f"<style>{CSS}</style>"
        f'<div class="t">RWKV review cards now <span class="note">({len(cids)} cards, '
        f"if you stop reviewing now; near = within {margin * 100:g} points)</span></div>"
        f"<table><tr><th></th><th>Current DR ({cur_label})</th><th>Selected DR ({selected * 100:.2f}%)</th></tr>"
        f"{rows}</table>"
    )


def message(text: str) -> str:
    return f'<style>{CSS}</style><div class="t">RWKV review cards now <span class="note">{html.escape(text)}</span></div>'


def show_js(markup: str) -> str:
    return f"window.rwkvfcDrShow && window.rwkvfcDrShow({json.dumps(markup)});"
