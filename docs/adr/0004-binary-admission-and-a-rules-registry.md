# A rule is admitted or not, and every claim lives in one registry with its provenance

A mechanics rule is either admitted or not: there are no confidence levels and no solver threshold. The solver never sees an action or a branch that rests on a rule that is not admitted; the question becomes a GitHub issue labelled `needs-info` instead. A policy is then only ever as good as its sources, and every number in a report can be traced back to one.

Each primitive's behaviour is Python code. Every claim or number that code relies on is an entry in one YAML rules registry with its provenance: source kind, URL, short quote, patch verified, date checked. Code refers to entries by id, and a test fails when a primitive uses an unregistered claim or an entry lacks provenance. The registry is the single source; pages in `docs/mechanics/` only hold long explanations and point at entry ids.

Which sources can admit a rule is ADR-0005.

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q2, [Design grill round 3: modules, verification, process](https://github.com/Rasslabsya4el/crafting-system/issues/4) Q20.
