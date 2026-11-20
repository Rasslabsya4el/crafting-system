# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the "Label in our tracker" column to match whatever vocabulary you actually use.

## Labels of this repo beside the five roles

| Label | Meaning |
| ----- | ------- |
| `deferred` | A deferred method or site work (OR-37, OR-53); not taken |
| `needs-rewrite` | The need is real, the text prescribes the old pipeline or stale numbers; not taken until the dispatcher chat rewrites it |
| `critical-path` | Stands between today and a heavy reference craft (R04, R06, R11, R13, R14, R17, R20, R24) giving a proved, playable plan; taken first |
| `after-beta` | True and harmless to leave, not needed for the beta; taken only when nothing else waits |

A `ready-for-agent` ticket with neither `critical-path` nor `after-beta` is needed for the beta. A chat that files an issue gives it one of the two marks, or neither, by the same rule. The marks were first set by the triage of 2026-11-20, which the owner asked for (323 open issues sorted; the verdict of each is in its comments where it was closed, deferred or sent to rewrite).
