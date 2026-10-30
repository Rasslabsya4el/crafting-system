# Evidence: the 2026-10-30 snapshot, the most reliable source per mechanic

Rules are built on the information available on 2026-10-30, even where it is old: GGG official notes, the PoE wiki, repoe-fork 3.29.3.3, Craft of Exile (pages, data and code; data version 3.29.0.3, local copy in `sources/raw/coe/`), large-sample player experiments including the owner-trusted Reddit posts (the 3.25 recombinator guide and the 3.29 Memory guide linked in the map's Notes), and the owner's own in-game checks or knowledge. There is no fixed ranking on behaviour: for each mechanic the most reliable available source is used, and where the documentation is incomplete a working implementation, Craft of Exile's code (its Harvest, for example), is the default model. A source that a 3.29 patch note or the 3.29.3.3 data shows to predate a change loses to the current one. The owner's reason: full certainty cannot be had for every mechanic, and in places Craft of Exile or a large Reddit experiment is more reliable than the wiki.

A genuine behaviour conflict is decided per mechanic by the main chat, with its reason, and the owner may override it. A conflict or gap that is quick to check goes to the owner as a short in-game check with exact steps; his answer is source kind `owner`, with what he saw or knows and the date. Every rule keeps its provenance (ADR-0004); a Craft of Exile claim cites the page or code line, its data version and the date checked.

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q2, amended by the owner on 2026-10-30 in the comments of [Owner decisions on B1 mechanics no source or Craft of Exile settles](https://github.com/Rasslabsya4el/crafting-system/issues/28).

## Considered options

Both were replaced on 2026-10-30 by the owner's clarification quoted above.

- Round 1 Q2 as first agreed: a fixed ranking (a newer official statement beats the wiki; otherwise the wiki wins on behaviour; datamined numbers beat wiki text) with Craft of Exile only a cross-check oracle and never evidence.
- Craft of Exile admitted only as the last-ranked source, used where every other source is silent (the owner's first amendment, the same day).

## Consequences

- Mechanics rules themselves are registry entries, not ADRs. The ones settled during the grills, which stand under this rule: a rare's 4/5/6 mod count is 8:3:1 (wiki; extended to Alchemy, essences and Harvest reforges as D3 of [#28](https://github.com/Rasslabsya4el/crafting-system/issues/28)); fossil factors stack as Craft of Exile does (owner, round 1 "Settled before the grill"; additive positive factors, negatives multiply, blocks win; D10 of [#28](https://github.com/Rasslabsya4el/crafting-system/issues/28)).
- The first behaviour conflict decided under this rule is CHK-048, whether one fossil boosts a mod once (wiki) or once per matching tag (Craft of Exile): Craft of Exile's `poec_getModdedWeight` is used, because the owner already chose Craft of Exile's fossil weight model for stacking and one model for the whole fossil weight is cleaner ([#28](https://github.com/Rasslabsya4el/crafting-system/issues/28), third comment).
- Prototype fact sheets marked `reimplemented-from-CoE` are re-audited under this rule like every other fact sheet ([Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q16), instead of losing admission outright as round 1 Q2 first said.
