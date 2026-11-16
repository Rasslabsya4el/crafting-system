# The website's service

The planner behind an HTTP API (#961, OR-35, OR-36): a user's request becomes a job, the job runs the planner's one entry
(`planner.plan_target`) in a worker process, and the finished route is stored with its page and answers every later identical request.
The code is `src/crafting_system/web/`; it holds no planning code and no page code (the figures, the JSON policy and the route page are the
command's own: `cli.build_report`, `cli.policy_document`, `cli.route_page`). There is no frontend yet: the site's pages call this API.

## Run it

On a machine with the repository (Linux for the site; Windows works too):

```
uv sync --extra web
uv run python -m crafting_system.data fetch        # once: the pinned game data
uv run python -m crafting_system.web --host 0.0.0.0 --port 8000 --workers 2
```

The prices are the configured price file with its overrides, as for the command (`crafting.toml`, `CRAFTING_DATA_DIR`). With Docker:

```
docker build -t crafting-site .
docker run -p 8000:8000 -v crafting-site:/site crafting-site
```

The volume `/site` holds the game data cache, the price file (`/site/data/prices.json`) and the store (`/site/output/web/site.sqlite3`).
The container fetches the pinned game data into the volume itself on its first start. The price file it does not fetch yet: until the
scheduled refresh runs beside the service (OR-9, #337), the operator puts it into the volume, once, with a one-off container that copies a
file from the host:

```
docker run --rm -v crafting-site:/site -v "$PWD/prices:/in:ro" --entrypoint sh crafting-site -c "mkdir -p /site/data && cp /in/prices.json /site/data/prices.json"
```

A file replaced there later (a refresh writes a new file and moves it over the old one in one step) is picked up by the running server at
its next request; no restart (see "A price refresh" below). `.github/scripts/web_docker_smoke.py` does all of this on a Linux runner and
plans one request through the container (#969).

| Setting | Flag | Environment | Default |
|---|---|---|---|
| address | `--host` | `CRAFTING_WEB_HOST` | `127.0.0.1` |
| port | `--port` | `CRAFTING_WEB_PORT` | `8000` |
| plans run at once | `--workers` | `CRAFTING_WEB_WORKERS` | `1` |
| the store's SQLite file | `--db` | `CRAFTING_WEB_DB` | `<output>/web/site.sqlite3` |

The limits of one plan are the machine's planner settings, as for the command (OR-40): `time_limit_seconds` and `memory_limit_mb` of the
`[planner]` table of `crafting.toml` (default 600 s and 80% of the machine's memory). The memory limit is per plan, so a machine that runs
several plans at once sets it to its share. Each plan also uses the cores `CRAFTING_WORKERS` gives it (default: all).

## The API

JSON in and out, under `/api/v1/<game>/`; the game is `poe1` (Path of Exile 2 gets its own service beside it, OR-50). An error is
`{"error": "<what is wrong>"}` with 400 or 404.

**Submit a request.** The target is a JSON object with the keys of a target file (`examples/targets/`, `src/crafting_system/targets`),
without `price_file`. `methods` and `settings` are optional; what is left out is the machine's planner setting.

```
POST /api/v1/poe1/jobs
{"target": {"base": "Paua Amulet", "item_level": 84, "influence": [],
            "requirements": [{"stat": "+1 to Level of all Lightning Skill Gems"}, {"family": "LightningResistance", "min_tier": "any"}],
            "start_item": {"rarity": "rare", "mods": [{"mod": "LightningResist2", "values": [14], "fractured": true}]},
            "start": "bought"},
 "methods": {"recipe_starts": true, "strands": false},
 "settings": {"start_price": null, "price_source": "both"}}

202 {"id": "3f2a…", "state": "queued", "from_store": false, "standing": null, "route": null, "error": null, "request": {…}, "key": "…", …}
```

A request already answered comes back at once with `200` and a job that is `done` with `"from_store": true`. A request identical to one
still queued or running gets that job, so two identical requests at once plan once. A request that cannot be planned as written (an unknown
key, a mod that does not exist, a base the game data lacks) is `400` at once, in the target parser's words.

**Follow a job.** `GET /api/v1/poe1/jobs/<id>` gives its state: `queued`, `running`, `standing` (a plan exists while the proof goes on,
OR-39), `done`, `failed` or `stopped`. `?wait=30` holds the answer up to 30 seconds (at most 60) until the job has ended; with
`&seen=standing` until its state is not that one. A page polls this way without a tight loop.

```
GET /api/v1/poe1/jobs/3f2a…?wait=30&seen=running
200 {"state": "standing",
     "standing": {"plan_cost_without_start": 1234.5, "lower_bound_without_start": 1220.0, "gap": 0.0119, "rounds": 4, "seconds": 2.1}, …}
```

The standing figures are the search's own (`planner.Standing`): the mean cost of the best plan so far and the figure no plan can cost less
than, both without the start item's price, and the proved gap between them. A plan with start options says where each option's search
stands in turn. A job that is `done` names its route; one that `failed` holds the planner's own words in `error`.

**Stop a job.** `POST /api/v1/poe1/jobs/<id>/stop`: a queued job never starts; a running one's worker process is killed. The job is
`stopped`, nothing is stored, and the same request asked again is planned again.

**Read routes.**

```
GET /api/v1/poe1/routes?limit=20&offset=0      stored routes, newest first
GET /api/v1/poe1/routes/<id>                   the request and its figures (`summary`: answer, totals, start, prices, limits, search)
GET /api/v1/poe1/routes/<id>/policy            the JSON policy, as the command writes it
GET /api/v1/poe1/routes/<id>/page              the route page (HTML), as the command writes it
GET /api/v1/poe1                               the game data version, the price snapshot and the machine settings in use
```

**How old the prices are.** Every job, every route and `GET /api/v1/poe1` carry `price_age`: the price snapshot behind it and how old it is
on the server's day, with a warning once it is past the age the command warns at (`prices.MAX_AGE_DAYS`, 7 days; judged by
`prices.stale_warning`), so a page can say so when the scheduled refresh has stalled (#976):

```
"price_age": {"league": "Mirage", "fetched_at": "2026-11-02T06:00:00Z", "age_days": 9, "max_age_days": 7, "stale": true,
              "warning": "The prices are 9 days old (the Mirage price snapshot of 2026-11-02); prices older than 7 days may be out of date."}
```

A job's is its route's once it has one, else that of the snapshot it is planned with while it owes an answer, else `null` (a failed or
stopped job). A route names the snapshot it was planned on in `summary.snapshot`; a route stored before that has `null`.

## The store and its key

Jobs and routes live behind a small repository interface (`web.Store`); the beta's is one SQLite file (`web.SqliteStore`). A server
database replaces it by implementing the same methods; nothing else changes. The store keeps every job, so a server restarted while plans
were running queues them again.

A request's key is the SHA-256 of one canonical JSON text (sorted keys) of:

- the game, the target's canonical form, the method switches and the settings, each with its default filled in (so a request that
  spells out a default and one that leaves it out are the same request);
- the machine's planner settings that change an answer: the proof gap, the time and memory limits, the imprint cap, the recombinator
  variant, the price-gap flag;
- the price snapshot: its league, the time it was fetched and a digest of every price in it (a hand override changes it);
- the game data version and the planner version.

Why these: a route is reused only where it is the answer the planner would give now. A new price snapshot, a patch or a new planner makes
the old route stale, so each of them is in the key. The calendar day is not in it: a plan judges a price's age on the day its
snapshot was fetched (`World.price_day`), so a route stays the answer for as long as its snapshot stands (OR-36). A worker keys its route on the inputs it read itself, so a route planned after a price refresh is stored under the
new snapshot, never under the one the request was keyed with.

The target's canonical form (`web.target_form`, #966) is the parsed target, not the JSON sent: every selector is the set of mods it counts
and the tiers it accepts, so a stat text and the family id it stands for, a key written at its default (`influence: []`) or left out, and the
required entries in another order give one key. The store keeps the request as it was written.

**A price refresh** (#968). The world names the files it was read from that a refresh replaces (the price file and its overrides) and how
they stood before the read. Each request first compares them with the files as they stand: when they changed, the service loads a new
world, and new requests are keyed and planned on the new snapshot without a restart. A new file that cannot be read (broken) leaves the old
snapshot in use and is not tried again until the files change once more; the fault goes to the server's log.

## Not built yet

The pages of the site (the item builder, the route list, the job view), accounts and auth, the economy modes (#323), reading the stash
(OR-48), the "notably better" replacement of a shown plan and the "keep searching" button (OR-39, #914), and a plan shown from the
standing before its route closes (the standing gives the figures, not yet the route).
