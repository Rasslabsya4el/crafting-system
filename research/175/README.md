# Ticket #175: the recombinator's selection exponent from the guide author's sheet

- `build_rows.py RAW_DIR MODS_JSON rows.json` reads the author's tabs (CSV exports of the public sheet, not kept in the
  repo) and the pinned `mods.json`, and writes `rows.json`: one record per (combine, side) with the pooled entries,
  their spawn weights, the kept mods and, for a side that cannot be used, the reason.
- `fit.py rows.json fit_result.json --boot N --sim N --seed S` fits `alpha`, the profile-likelihood intervals, the
  sensitivity runs, the goodness-of-fit checks and the bootstrap. Standard library only; `python -I`.
- `rows.json` is the extract; `fit_result.json` is the output of the run on GitHub (`run.yml`) quoted by the note
  `docs/research/2026-11-01-recombinator-selection-exponent.md`.
