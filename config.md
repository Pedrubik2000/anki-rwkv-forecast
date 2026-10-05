**RWKV forecast** for RWKV-Instant. Every number means *if you stop reviewing now*: each answer
moves every card's recall, so it is recomputed after reviews or changes.

**Deck list** (under "Studied … today"): `due | near | safe` now, and the count line
`due 5 · +1 in 1 h · +2 in 3 h · 9 by tomorrow` ("+N" = not due now, due by then; "by tomorrow" =
due at the next day rollover). Click a number to open those cards in the Browser.

**Deck options** (under Desired retention): due / near / safe for the preset's review cards at the
current DR and at the DR you are typing (live, before you save), and a dot bar: one dot per card at
its recall now, red line at the typed DR. Recall doesn't depend on the target, so only the line
moves. "This deck" overrides are not applied to the Selected column.

- `enabled`: show the deck-list text.
- `count_line`: show the count line in the deck list.
- `near_margin`: "near" = recall between the target and target + this (0.03 = 3 points).
- `bar_axis_min`: left end of the deck options recall axis (0.6 = 60%).
- `max_age_minutes`: recompute when the forecast is older than this (or after any review or change).

Cards reviewed earlier today often lose recall quickly during the day and jump back up at the day
rollover (the model then sees "1 day since the last review"), so "by tomorrow" can be lower than
the 3 h numbers suggest.
