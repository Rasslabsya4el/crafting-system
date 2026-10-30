# English in the repo; "family" and "mod type", never a bare "group"

Docs, ADRs, the glossary, code and issues are in English; chat with the owner is in Russian; modifier names and stat text stay in the game's original English everywhere, in chat too.

"Family" is the exclusion group: the wiki's group/family, repoe `groups`; an item never holds two mods that share a family. "Mod type" is repoe `type`. The bare word "group" is not used: Path of Building calls the mod type its `group`, and confusing the two under-excludes (ADR-0003). The terms are defined in [GLOSSARY.md](../../GLOSSARY.md).

Origin: [Design grill round 3: modules, verification, process](https://github.com/Rasslabsya4el/crafting-system/issues/4) Q24; the family rule from the wiki's [Modifier](https://www.poewiki.net/wiki/Modifier) page, "Group/family", recorded in [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2).
