# Strands come from the start item, a stranded purchase or an Orb of Remembrance; the Foulborn orbs are three more currencies

[Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) decides how strands enter a plan and what the three Foulborn orbs are. The rules are [research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98); ADR-0040 and ADR-0041 give the count, the cut and the spend.

## The Genesis Tree is out, and so is every acquisition method

The owner decided: the Genesis Tree is one of many ways to acquire an item, and the final item does not differ, so **acquisition methods are not modelled** (grill B5, answer 4). A Genesis-born item, a dropped item and a gambled one are just **start items**: the user pastes the item, with its `Memory Strands: N` line if it shows one (ADR-0040), and the planner crafts from there. The four Genesis claims of the research (womb items, the tier-rating nodes, the mod-type weights) stay in the research folder as a record and are not promoted to the rules registry. The Foulborn orbs, which only the tree births, are **bought at the market price** from the price file (ADR-0007); they are never made.

## Strands enter a plan in three ways

1. **The start item** carries them (ADR-0040).
2. **A stranded purchase.** A buy offer (the B1 buy action; ADR-0008's buy specs) may name a minimum strand count. The price comes from the trade API with the `memory_level` minimum filter (the slot exists in `trade_query.py`), instant buyout (#133), and is cached in the price file; an offer without a price is dropped and the report lists it (ADR-0007). The planner does not ask for all 100 counts. It offers the counts at which a cut class begins for a tier table that the target needs, which are usually two to four per query. This is a choice of which prices to fetch, not a claim that the counts of one class are equivalent (the spend depends on the exact count, ADR-0040): it is the main chat's default, for the main chat to confirm, and the answer is `approximate` on it. A listing "with at least `m`" is planned as an item with **exactly `m`**: under the plan's weight reading (ADR-0042) more strands never hurt a requirement on a minimum tier (the cut only drops low tiers and the spend cannot go below 0), so the planned cost is an upper bound for what the listing really gives; under readings 2 and 3 it is the estimate for `m` strands.
3. **An Orb of Remembrance**, below.

## The Orb of Remembrance

- **The action.** On a **normal equipment item** it sets the count to a new random number whatever the count was: it adds strands to an item with none and re-rolls an item that has some (wiki). It is a re-roll and can be applied again; the repetition is an inference from "randomises" and from the first author's talisman rolled "to 100" with orbs, marked `approximate` in the claim. **Jewels are refused**: the wiki says equipment and treats jewels as a separate class, and the author's tests are on a talisman; the other equipment classes rest on the wiki's word. `approximate`. Corrupted and mirrored items are refused as for every orb.
- **The count.** `x ~ N(35, 25)`, accepted if `10 <= x < 100.5`, redrawn otherwise, the result `round(x)`. The research states the rule as "redraw until the rounded value is in 10..100" (a lower bound of 9.5, mean 41.66); both fit the 2,255 results and the note says the fit is not sensitive to it. The plan takes 10.0 on one ground only, the count at 10 (20 against about 32 at its neighbours; the note expects 13 for a half-width cell), and the choice is `approximate`. These bounds are the research's fit: no result below 10 in the author's 2,255 results (the count at 10 is lower than its neighbours, as a continuous cut at 10.0 gives), three of exactly 100, mean 41.84 against 41.56 observed, chi-square 7.2 on 17 degrees of freedom (sirgog's rule is "discard if below 10 or above 100"; the rounding is not known: `approximate`). It is an exact table of 91 probabilities computed once to twelve digits and held as fractions that sum to 1. The result **does not depend on the old count** (nothing tests it): `approximate`.
- **The loop.** After one orb the item is still normal, so the planner may apply another: the state graph has the self-loop, and the solver finds the stop threshold itself (the cheapest policy accepts a count when re-rolling is dearer in expectation). After the first craft the item is no longer normal, so a further re-roll needs a Scouring Orb, which keeps the strands (ADR-0041).
- **The price** is the orb's price from the price file. The 56 Chaos seen in a search snippet is not a design number.

## The Foulborn orbs

Three currencies, **Foulborn Orb of Augmentation, Foulborn Regal Orb and Foulborn Exalted Orb**, each acting as its plain version (the same refusals, the same pool, the same draw) with two changes:

- **The cut adds 75 to `D`** (ADR-0040): the same formula on a stranded item and on a 0-strand item, which is the case the wiki's list of kept tiers fixes (`D = 175`).
- **The spend** is the orb's own: Foulborn Augmentation 0 to 32, Foulborn Regal 0 to 48, Foulborn Exalted by the mods on the item (ADR-0041).

They are not new in 3.29 (3.27.0). Their prices are market prices only. A second Foulborn orb on an item whose strands the first spent has no test; the model applies the rules unchanged (cut of the remaining count plus 75), `approximate`.

## What this changes

- A Foulborn orb is a plain currency action with a flag; Remembrance is a chance node over `s`, built on ADR-0027's `Adds`.
- The unknowns of this ADR are `approximate` claims, so every answer that reads them lists them (ADR-0028).

Origin: [Grill B5](https://github.com/Rasslabsya4el/crafting-system/issues/103) (round 1 answers 2 and 4; the standing rule); [Research #98](https://github.com/Rasslabsya4el/crafting-system/issues/98); ADR-0007, ADR-0008, ADR-0024, ADR-0027, ADR-0028, ADR-0040, ADR-0041.

## Amendment: the claims ([#274](https://github.com/Rasslabsya4el/crafting-system/issues/274))

The Remembrance count is claim `memory_strands.remembrance_distribution` (value: mean 35, sd 25, accepted from 10 to below 100.5, rounded; `approximate`); it does not depend on the old count if the sheet's rows are consecutive orbs on one item (claim `remembrance_independent_of_old_count`, `approximate`). Players have used the orb on helmets, boots, a belt, body armour, an amulet and a talisman; jewels and the other classes rest on the wiki's word (claim `remembrance_classes_observed`). The Foulborn Exalted ceiling is the row 46, 52, 56, 60, 62, 66 by the mods before the craft (claim `foulborn.exalted_spend_by_mod_count`); on a stranded item the bonus is added to the denominator (claim `foulborn.bonus_is_added_to_the_strand_denominator`), and on a 0-strand item the cut is claim `foulborn.zero_strand_cut_matches_eleven_strands`, `approximate`.
