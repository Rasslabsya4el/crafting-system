"""Build the website's image, start it and plan one request through it on the real data (#969). Linux only, on a runner: a heavy run,

    python .github/scripts/heavy_dispatch.py run --ref <branch> --runners 1 --timeout-minutes 45 \
        --command 'uv run --no-sync python .github/scripts/web_docker_smoke.py --out $OUT_DIR'

never on the owner's PC. What it does, as `docs/web.md` tells an operator to:

1. `docker build -t crafting-site .`
2. puts a price file into the volume `/site` (`/site/data/prices.json`) with a one-off container;
3. `docker run -d -p 8000:8000 -v <volume>:/site crafting-site`: the container fetches the pinned game data into the volume, then serves;
4. waits for `GET /api/v1/poe1`, posts the target (YAML read and sent as JSON, without its `price_file`), follows the job to its end with
   the API's own wait, reads the route, its policy and its page, and posts the same request again, which must come from the store.

Everything it read goes to `--out` (the info, the job, the route, the page, the container's log). Exit 0 only when the job is done, the
page is served and the second request is answered from the store.
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

IMAGE = "crafting-site"
NAME = "crafting-site-smoke"
VOLUME = "crafting-site-smoke"
BASE = "http://127.0.0.1:8000/api/v1/poe1"


def docker(*arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    print("+ docker", " ".join(arguments), flush=True)
    return subprocess.run(["docker", *arguments], check=check, text=True)


def call(method: str, url: str, body: dict | None = None, timeout: float = 90.0) -> tuple[int, str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prices", type=Path, default=Path("tests/fixtures/prices/routes-allflame-2026-11-10.json"))
    parser.add_argument("--target", type=Path, default=Path("examples/targets/r12-lightning-amulet.yaml"))
    parser.add_argument("--start-minutes", type=float, default=15.0, help="how long the container may take to fetch the data and serve")
    parser.add_argument("--plan-minutes", type=float, default=20.0, help="how long the plan may take")
    args = parser.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    docker("build", "-t", IMAGE, ".")
    docker("volume", "create", VOLUME)
    prices = args.prices.resolve()
    docker(
        "run", "--rm", "-v", f"{VOLUME}:/site", "-v", f"{prices.parent}:/in:ro", "--entrypoint", "sh", IMAGE,
        "-c", f"mkdir -p /site/data && cp '/in/{prices.name}' /site/data/prices.json",
    )  # fmt: skip
    docker("rm", "-f", NAME, check=False)  # a container left by an earlier run on the same machine
    docker("run", "-d", "--name", NAME, "-p", "8000:8000", "-v", f"{VOLUME}:/site", IMAGE)
    try:
        return smoke(args, out)
    finally:
        with (out / "container.log").open("w", encoding="utf-8") as log:
            subprocess.run(["docker", "logs", NAME], stdout=log, stderr=subprocess.STDOUT, check=False)
        docker("rm", "-f", NAME, check=False)


def smoke(args: argparse.Namespace, out: Path) -> int:
    deadline = time.monotonic() + args.start_minutes * 60
    while True:
        try:
            status, text = call("GET", BASE, timeout=10)
            if status == 200:
                break
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        running = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", NAME], capture_output=True, text=True, check=False)
        if running.stdout.strip() != "true":
            print("the container has stopped before it served", flush=True)
            return 1
        if time.monotonic() > deadline:
            print(f"the server did not answer within {args.start_minutes} minutes", flush=True)
            return 1
        time.sleep(5)
    (out / "info.json").write_text(text, encoding="utf-8")
    print("info:", text, flush=True)

    target = yaml.safe_load(args.target.read_text(encoding="utf-8"))
    target.pop("price_file", None)
    status, text = call("POST", f"{BASE}/jobs", {"target": target})
    print("posted:", status, text[:500], flush=True)
    if status not in (200, 202):
        return 1
    job = json.loads(text)
    deadline = time.monotonic() + args.plan_minutes * 60
    while job["state"] in ("queued", "running", "standing"):
        if time.monotonic() > deadline:
            print(f"the job owes an answer after {args.plan_minutes} minutes: {job}", flush=True)
            return 1
        status, text = call("GET", f"{BASE}/jobs/{job['id']}?wait=60&seen={job['state']}")
        job = json.loads(text)
        print("job:", job["state"], json.dumps(job.get("standing")), flush=True)
    (out / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    if job["state"] != "done":
        print("the job ended", job["state"], job.get("error"), flush=True)
        return 1

    status, text = call("GET", "http://127.0.0.1:8000" + job["route"]["url"])
    (out / "route.json").write_text(text, encoding="utf-8")
    route = json.loads(text)
    print("route:", json.dumps({key: route[key] for key in ("id", "price_age", "page_url")}), flush=True)
    print("totals:", json.dumps(route["summary"]["totals"])[:1000], flush=True)
    status, page = call("GET", "http://127.0.0.1:8000" + route["page_url"])
    (out / "route.html").write_text(page, encoding="utf-8")
    if status != 200 or "<html" not in page:
        print("the route page was not served:", status, flush=True)
        return 1

    status, text = call("POST", f"{BASE}/jobs", {"target": target})
    again = json.loads(text)
    print("again:", status, again["state"], again["from_store"], flush=True)
    if status != 200 or not again["from_store"] or again["route"]["id"] != route["id"]:
        return 1
    print("SMOKE OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
