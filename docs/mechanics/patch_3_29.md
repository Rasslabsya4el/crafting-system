# 3.29 crafting availability and changed actions

Status: documented patch deltas, incomplete action algorithms. Read 2026-09-20.
Source: S39, official 3.29.0 notes, https://www.pathofexile.com/forum/view-thread/3985332.
Confidence: `documented`. These conditions apply to 3.29; Q3 still asks which patch the
prototype targets. A cached CoE action name does not establish current availability.

| family | change in 3.29 | exact algorithm still needed |
|---|---|---|
| Corruption sockets | Vaal converts one random white socket; Locus converts all white sockets to non-white | colour weights and no-white edge case; Q18, corruption.md |
| Synthesis | Harvest synthesis removed; synthesis-implicit beast reroll is unique-only | eligible unique pools and reroll weights |
| Synthesised legacy items | Old Standard synthesised items remain blocked for fracture currency despite shorter item text | complete per-action matrix Q9 |
| Fractured Fossil | Fractures a random modifier; excludes fractured and influenced items | selection/order inside resonator, mod-count gate |
| Beast splitting | Replaced by fracturing one mod on rare Talisman with at least 4 mods, or two with at least 6 | selection distribution and imprint interaction |
| Talisman conversion | Amulet-to-Talisman craft replaced by rare-Talisman imprint | restore legality and irreversible transitions |
| Bench rerolls | Three random mods for 3 Chaos, or one random mod for 8 Chaos, on rares | selection versus value reroll, protection rules |

These are patch notes, not complete executable specifications. No uniform sampling, replacement
order, side protection, success rate or market price follows from the word random. The numerical
gates/costs above are quoted game-input quantities from S39, not economy estimates. Worked
probability examples await the listed rules; implementing those paths now would be unsourced.

Cross-source discrepancy: S3 retains old synthesis/split names and old white-socket categories.
Keep the offline inventory unchanged as evidence; Q18/Q19 record why those entries cannot be
used as current 3.29 rules. Ordinary fossil multipliers, unchanged actions and old Standard
items must not be silently reclassified solely from these deltas.
