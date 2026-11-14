"""RWKV forecast: how close review cards are to being due under RWKV-Instant.

Deck list: due | near | safe and the count line under "Studied … today". Deck options: due /
near / safe at the current vs the typed desired retention, and a dot bar (one dot per review card
of that preset on a recall axis, red line at the typed DR). Every number means "if you stop
reviewing now": each answer moves every card's recall, so it is recomputed after reviews.
Read-only: never writes cards.
"""

from __future__ import annotations

import json
import threading
import time
import traceback

import aqt
from aqt import gui_hooks, mw
from aqt.qt import QTimer

from . import dr, engine, views

DEFAULTS = {
    "enabled": True,
    "count_line": True,
    "near_margin": 0.03,
    "bar_axis_min": 0.6,
    "max_age_minutes": 5,
}
RETRY_MS = 2000
MAX_RETRIES = 15


def _conf() -> dict:
    return {**DEFAULTS, **(mw.addonManager.getConfig(__name__) or {})}


class State:
    fc: engine.Forecast | None = None
    key: tuple | None = None  # collection state the forecast was computed for
    names: dict[int, str] = {}  # cid -> sort field (dot tooltips)
    home_did: dict[int, int] = {}  # cid -> home deck id
    presets: dict[str, list[int]] = {}  # preset name -> its review cards (deck options)
    running = False
    cancel: threading.Event | None = None  # set to stop the running projection (API path)
    again = False  # another refresh was asked for while running
    retries = 0
    status = ""  # shown instead of the bar while there are no numbers (busy, error)


S = State()


def _col_key() -> tuple:
    last = mw.col.db.scalar("select max(id) from revlog") or 0
    return (mw.col.mod, last)


def _fresh() -> bool:
    if S.fc is None or S.key != _col_key():
        return False
    return time.time() - S.fc.taken < float(_conf()["max_age_minutes"]) * 60


def _has_consumer() -> bool:
    """Something on screen shows the forecast: the deck list or the open deck options dialog."""
    dialog = _dr_dialog
    return mw.state == "deckBrowser" or (dialog is not None and getattr(dialog, "web", None) is not None)


def _load_names(fc: engine.Forecast):
    """Short collection reads for the forecast's cards; run with the collection executor."""
    ids = ",".join(str(c) for c in fc.cards) or "0"
    names, home_did = {}, {}
    for cid, did, odid, sfld in mw.col.db.execute(
        f"select c.id, c.did, c.odid, n.sfld from cards c join notes n on n.id = c.nid where c.id in ({ids})"
    ):
        names[cid], home_did[cid] = str(sfld)[:60], odid or did
    return fc, names, home_did, dr.preset_map(mw.col, fc.cards, home_did)


def refresh() -> None:
    """Recompute in the background, then redraw the bar if the deck list is showing."""
    if mw.col is None:
        return
    if S.running:
        S.again = True
        return
    S.running, S.again = True, False
    key = _col_key()
    cancel = S.cancel = threading.Event()

    def finish(error: BaseException | None, payload=None) -> None:
        S.running = False
        cancelled = isinstance(error, engine.Cancelled)
        if error is None:
            S.fc, S.names, S.home_did, S.presets = payload
            S.key, S.status, S.retries = key, "", 0
        elif cancelled:  # keep the previous forecast; the next deck-list render recomputes
            S.status, S.retries, S.again = "", 0, False
        elif isinstance(error, engine.Busy):
            S.retries += 1
            if S.retries <= MAX_RETRIES and _has_consumer():
                S.status = f"waiting for RWKV ({error})…"
                QTimer.singleShot(RETRY_MS, refresh)
            elif S.retries <= MAX_RETRIES:  # nobody is looking: the next render starts it again
                S.status, S.retries = "", 0
            else:
                S.status = "RWKV stayed busy; open the deck list again to retry"
                S.retries = 0
        else:
            print("".join(traceback.format_exception(error)))
            S.status = "forecast failed (see the debug console)"
        if mw.state == "deckBrowser":
            _update_deck_list()
        _answer_dr()
        if S.again:
            QTimer.singleShot(0, refresh)

    def result(fut):
        try:
            return None, fut.result()
        except Exception as e:
            return e, None

    if engine.uses_api():
        # the projection runs off the collection executor; only the short reads below take it
        def done_projection(fut):
            error, fc = result(fut)
            if error is not None or mw.col is None:
                finish(error or engine.Cancelled())
                return

            def done_names(fut2):
                error2, payload = result(fut2)
                finish(error2, payload)

            mw.taskman.run_in_background(lambda: _load_names(fc), done_names, uses_collection=True)

        mw.taskman.run_in_background(
            lambda: engine.compute(mw, engine.offsets_for(), cancel_event=cancel),
            done_projection,
            uses_collection=False,
        )
        return

    def job():
        return _load_names(engine.compute(mw, engine.offsets_for()))

    def done(fut):
        error, payload = result(fut)
        finish(error, payload)

    mw.taskman.run_in_background(job, done, uses_collection=True)


def _on_deck_browser(deck_browser, content) -> None:
    conf = _conf()
    if not conf["enabled"]:
        return
    content.stats += views.deck_list_text(S.fc, conf, S.status)  # under "Studied … today"
    if not _fresh():
        _refresh_after_deck_counts(deck_browser)


AFTER_COUNTS_POLL_MS = 30
AFTER_COUNTS_MAX_MS = 5000


def _refresh_after_deck_counts(deck_browser, waited: int = 0) -> None:
    """Start once the fork's own RWKV deck counts are in: both need the RWKV backend, and running
    together made Anki's counts ~3x slower (55 → 180 ms on 360 cards)."""
    pending = getattr(deck_browser, "_rwkv_pending_deck_ids", None)
    if pending and waited < AFTER_COUNTS_MAX_MS and mw.state == "deckBrowser":
        QTimer.singleShot(
            AFTER_COUNTS_POLL_MS, lambda: _refresh_after_deck_counts(deck_browser, waited + AFTER_COUNTS_POLL_MS)
        )
        return
    refresh()


def _update_deck_list() -> None:
    conf = _conf()
    if not conf["enabled"]:
        return
    swap = (
        "(function(){const e=document.getElementById('rwkvfc');"
        f"if(e) e.outerHTML={json.dumps(views.deck_list_text(S.fc, conf, S.status))};}})();"
    )
    mw.deckBrowser.web.eval(swap)


# ---------------------------------------------------------------- deck options


_dr_dialog = None  # the open deck options dialog
_dr_request: dict | None = None  # last {preset, selected} it asked for


def _on_deck_options(dialog) -> None:
    global _dr_dialog
    _dr_dialog = dialog
    if not _fresh():  # once per opening; renamed or new presets show up after this
        refresh()
    dialog.web.eval(dr.PAGE_JS)


def _answer_dr() -> None:
    d, req = _dr_dialog, _dr_request
    if d is None or req is None or getattr(d, "web", None) is None:
        return
    if S.fc is None:
        markup = dr.message(S.status or "computing…")
    else:
        cids = S.presets.get(req["preset"])
        if cids is None:
            markup = dr.message("save this preset first")
        elif not cids:
            markup = dr.message("no review cards use this preset")
        else:
            selected = float(req["selected"])
            markup = dr.table(S.fc, cids, selected, float(_conf()["near_margin"])) + views.options_bar(
                S.fc, cids, selected, _conf(), S.names
            )
    d.web.eval(dr.show_js(markup))


def _on_dr(payload: str) -> None:
    global _dr_request
    try:
        _dr_request = json.loads(payload)
    except ValueError:
        return
    _answer_dr()
    # no collection query here (the page's own backend work may hold it): only the age decides
    if S.fc is None or time.time() - S.fc.taken > float(_conf()["max_age_minutes"]) * 60:
        refresh()


def _browse(ids: str) -> None:
    cids = [c for c in ids.split(",") if c.isdigit()]
    if cids:
        aqt.dialogs.open("Browser", mw).search_for(f"cid:{','.join(cids)}")


def _on_js_message(handled, message, context):
    if isinstance(message, str) and message.startswith("rwkvfc:browse:"):
        _browse(message.split(":", 2)[2])
        return (True, None)
    if isinstance(message, str) and message.startswith("rwkvfc:dr:"):
        _on_dr(message.split(":", 2)[2])
        return (True, None)
    return handled


gui_hooks.deck_browser_will_render_content.append(_on_deck_browser)
gui_hooks.webview_did_receive_js_message.append(_on_js_message)
gui_hooks.deck_options_did_load.append(_on_deck_options)


def _cancel_running() -> None:
    if S.cancel is not None:
        S.cancel.set()


def _on_state_change(new_state, old_state) -> None:
    if new_state == "review":  # reviewing needs the RWKV backend; the forecast is stale after answers anyway
        _cancel_running()


def _on_profile_close() -> None:
    _cancel_running()
    S.fc = None


gui_hooks.state_did_change.append(_on_state_change)
gui_hooks.profile_will_close.append(_on_profile_close)
