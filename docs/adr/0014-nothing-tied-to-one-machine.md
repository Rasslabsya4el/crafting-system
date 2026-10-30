# Nothing is tied to one machine

Owner requirement: the repo installs and runs on any Windows or Linux machine, a Linux server included, with no hard-coded paths and no speed assumptions about the owner's machine.

- `pyproject.toml`, a `uv` lock file and one pinned Python; one-command install on Windows and Linux.
- No absolute path in code or committed config. Data, cache and output directories come from a config file or environment variables, with git-ignored defaults inside the project.
- No timing assertions in tests. A separate benchmark command records results with machine info and tracks the goal of about 1 minute per benchmark query without failing anything.
- GitHub Actions runs the tests on Ubuntu and Windows for every pull request; `.gitattributes` fixes line endings.
- Docker only once an HTTP service exists, which v1 does not have (ADR-0015).

Origin: [Design grill round 1: foundations](https://github.com/Rasslabsya4el/crafting-system/issues/2) Q9 (owner requirement), [Design grill round 2: data, batches, repo](https://github.com/Rasslabsya4el/crafting-system/issues/3) Q14.
