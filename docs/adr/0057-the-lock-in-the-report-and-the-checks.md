# The Lock is read as in-game steps, always gets a line, and is checked against the explicit product

How a Lock step is shown, what every plan says about the Lock, how a given route writes one, and how the Peek is verified and benchmarked. The model is ADR-0054, the previewable set ADR-0055, the burn and the price ADR-0056.

## The Lock step

A step that takes the Lock reads as the player does it, not as a currency:

> Hinekora's Lock; hover Exalted Orb, Orb of Annulment, Regal Orb; use the one whose result is one of these items (cards); if more than one qualifies, take the first on the list; otherwise Chromatic Orb and lock again, or <fallback action>.

The cards are the acceptance set (ADR-0054), grouped by currency and ordered by the rank of the pairs, each shown as the route view shows a state. The text report caps the list and says so; the JSON and the route page carry it whole, with the chance of each option winning and the chance of giving up (the pseudo-states of ADR-0054). The route page draws the burn as the loop back to the Lock.

## The Lock line

Every plan prints one line about the Lock, even when it is not worth it (owner, [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106) answer 4):

> Hinekora's Lock: not worth it; would pay below N Divine (now P).

- **N** is the price below which one Lock, on some step of the plan without the Lock, already lowers the cost. For each state `s` the Lock-free plan visits, the gain is `g(s) = V(s) - E[ min( min_a ( c_a + V(o_a) ), F(s) ) ]`, the Peek of ADR-0054 at price 0 with the Lock-free values (one sweep per visited state, tens to hundreds of states, so almost no time). `N` is the largest `g(s)`, in Divine at the price file's rate. Below `N` the Lock at that state saves `g(s) - L` on every visit to it, so the plan really changes (policy improvement); above `N` the plan can still change only through a state the Lock-free plan does not visit, which the solver finds by its own search and the line does not claim. The line states only the first.
- With a Lock in the plan the line reads "Hinekora's Lock: step k, saves X Divine of the plan's mean at the current price P" and gives `N` as well.
- The other cases each have their own wording, never silence: **no previewable option** on any visited state ("no previewable action in this plan"); **an item the Lock refuses** (corrupted, mirrored); **the Lock dropped by the target's `actions:`** ("switched off by the target"); **no price in the price file** ("no price, dropped", and `N` is still printed, since it does not need `P`); **an approximate answer** (ADR-0023), where the exact values `N` needs do not exist: the line says "not worth it at this price on the coarse bounds" when the pruning removed the Lock everywhere, and does not print `N`.
- JSON: a `foresight` object with the price, `n`, the best state, whether the plan uses the Lock and the saving.
- When the best `g(s)` comes from a `by_item_text` option, the line says "N counts <currencies> by item text".

## Approximate inputs

The list of ADR-0028 gains, for every Peek of the policy, the `by_item_text` options (ADR-0055) and, when a Chromatic burn is taken, the socket assumption (ADR-0056). **Independence is not listed**: it is the owner's rule (ADR-0054), and no "safe" cost is printed beside the plan. An answer with no Lock step lists none of this, but its Lock line still counts approximate options when `N` uses them.

## A given route can take the Lock

A given route (YAML, ADR-0019) gains a rule form `lock`: the options looked at, an ordered `accept` list (an option and conditions on its **result** state, the first entry that matches wins), and an `else` (a burn, an unpreviewed action or a restart). It is read into the same acceptance set and pseudo-states as the solver's, so `risk.evaluate` and the simulator see ordinary actions and R29's step 8 ("use Hinekora's Locks to preview Exalted slams... on fail consume the preview by changing the item and retry the lock") can be written down.

## Verification (ADR-0019)

- **Layer 1 is unchanged**: no new kernel; the options reuse existing ones.
- **Layer 2**: the simulator throws every option independently on a copy of the concrete item and applies the acceptance set. It checks the arithmetic of the Peek, not the independence, which is the owner's rule.
- **Layer 3 has two oracles.** One is the explicit product expansion (states `(s, previews)`) of tiny models, solved by the existing solver, by brute force and by HiGHS. The other is the hand test of ADR-0054: with the fallback `F` = 66 (play B blind), 23.97 with the Lock before its price, 66 without, break-even 42.03. A fuzz includes burn self-loops, jewels without a burn, options with equal kernels (two independent draws, so the value must fall against one) and a trap that never accepts.
- **Layer 4**: R29 with the Lock, run with `--verify`.

## Benchmarks

- **R29 with its Lock step restored.** B3's R29 runs without the Lock (ADR-0013, amended by B3) and stays the baseline; B8 compares the guide's given route and the solver's at equal prices and across the exponent grid of ADR-0033. R29's Runesmith step stays out (historical).
- **A synthetic target with the Lock's price overridden low**, where the plan must take the Lock and the Lock line must show `N` above the override; at the real price the same target must print "not worth it".
- The pass rule is ADR-0013's.

Origin: [Grill B8](https://github.com/Rasslabsya4el/crafting-system/issues/106) (owner's answers 2 and 4; the round draft); ADR-0013, ADR-0019, ADR-0028, ADR-0054 to ADR-0056.
