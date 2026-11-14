# RWKV forecast for Anki

> **No longer maintained (October 2026).** This add-on will not receive updates or fixes. It still works as released; feel free to fork it.

Under **RWKV-Instant** a review card is due when its live RWKV recall drops below the desired
retention, so cards have no due dates and Anki can't show what is coming. This add-on shows it.

**Deck list** (under "Studied … today"):

```
RWKV forecast  if you stop reviewing now
due 62 | near 4 | safe 294
due 62 · +3 in 1 h · +8 in 3 h · 70 by tomorrow
```

- `due`: recall below the target now. `near`: within 3 points above it. `safe`: the rest.
- `+N in 1 h / 3 h`: not due now, due by then. `by tomorrow`: due at the next day rollover.
- Click a number to open those cards in the Browser.
- Below it, the **RWKV recall** box: one dot per review card at its recall now, a red line at each desired
  retention and the "near" band beside it. Turn it off with `deck_list_graph` in the config.

**Deck options** (under Desired retention): due / near / safe for the preset's review cards at the
current desired retention and at the one you are typing, live, before you save, plus a dot bar
(one dot per card at its recall now, red line at the typed retention).

Every number means **"if you stop reviewing now"**: under RWKV each answer moves every card's
recall, so the forecast is recomputed after reviews.

## Requirements

- The **JSchoreels FSRS-7 fork** of Anki with RWKV ([JSchoreels/anki](https://github.com/JSchoreels/anki)),
  tested on **26.09.3+fsrs7 build 96**, with **RWKV-Instant** on in the deck options.
  The add-on uses the fork's internal RWKV code (`aqt.rwkv_scheduler`), so other builds may need
  changes in `engine.py`. It does nothing useful on official Anki.
- Read-only: it never writes cards.
- Performance: on fork builds with `project_rwkv_recall` (the recall projection API) the forecast runs off the collection executor, waits instead of restarting when RWKV is busy, and stops while you review. Older builds keep the previous behavior (internal helpers, holding the collection while it runs).

## How it works

The fork scores a card with a query that carries the time since its last review and today's day
number. The add-on takes the same queries the Browser's `is:rwkv:due` search uses and moves the
clock forward (1 h, 3 h, the next rollover) without touching the model's state. Recall doesn't
depend on the target, so the deck options table counts one forecast against two targets.
It waits for Anki's own RWKV deck counts before computing (they share the RWKV backend); a forecast
for ~360 review cards takes about 20–90 ms.

Note: cards reviewed earlier today often lose recall quickly during the day and jump back up at
the day rollover (the model then sees "1 day since the last review").

## Install

Download `rwkv_forecast-<version>.ankiaddon` from
[Releases](https://github.com/Pedrubik2000/anki-rwkv-forecast/releases) and double-click it
(or Tools > Add-ons > Install from file), then restart Anki.
Or copy this folder into your Anki `addons21` folder as `rwkv_forecast`.

## Config

See [config.md](config.md): near margin, the deck options axis, how often to recompute.

## Releasing

`python package.py` builds `dist/rwkv_forecast-<version>.ankiaddon` locally. Pushing a tag `vX.Y.Z`
makes GitHub Actions build `rwkv_forecast-X.Y.Z.ankiaddon` and attach it to a new release.

## License

MIT, see [LICENSE](LICENSE).
