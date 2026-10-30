# Prices: Chaos Orb unit, a dated local price file, every source tried before an action is dropped

Costs are in Chaos Orbs, with a Divine Orb equivalent in reports; time and clicks cost nothing. The solver reads prices only from a dated local price file, so a query is repeatable and never waits on the network; fetchers are separate tools that write that file, and any line can be overridden by hand.

poe.ninja is the price source. When a price is missing, the fetchers look further before giving up: price history in other time ranges on poe.ninja or poe.watch, and for buy actions the official PoE trade API through an existing wrapper rather than our own search-filter code ([Price sources: price history and the trade API](https://github.com/Rasslabsya4el/crafting-system/issues/13) names the endpoints and the wrapper). Only when every source fails is the action unavailable to the solver, and the report lists what was dropped for lack of a price. A price file older than 7 days gives a warning, not an error.

The trade-API fetcher runs only when the owner starts it, never unattended: that is the safe reading of GGG's developer documentation and Terms of Use (main chat, 2026-10-30, in [Owner decisions on B1 mechanics no source or Craft of Exile settles](https://github.com/Rasslabsya4el/crafting-system/issues/28); the owner may widen it).

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q5, [Design grill round 3: modules, verification, process](https://github.com/Rasslabsya4el/crafting-system/issues/4) Q21 (amended by the owner).
