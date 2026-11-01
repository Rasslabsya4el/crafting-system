"""Craft of Exile's emulator, run headless from a local copy of the site (ticket #198).

    python tools/coe_emulator/emulator.py fetch            # copy the site into .claude/scratch/coe/site/
    python tools/coe_emulator/emulator.py run check.json   # run one or more checks, JSON on stdout

Needs Python with Playwright and its Chromium (`pip install playwright`, `playwright install
chromium`); nothing of the project. `fetch` opens the live page once in headless Chromium and keeps
every file the page loads from craftofexile.com (scripts, data, styles; no images, no ads); it
writes `manifest.json` with the date and the SHA256 of every file. `run` serves the page only from
that copy (any request outside it fails), opens the Emulator tab, loads `driver.js` and calls it.
The copy is third-party code: it stays in `.claude/scratch/` (git-ignored) and is never committed.

A check file is one check or a list of them:

    {"id": "...",
     "item": {"item": "Titanium Spirit Shield", "ilvl": 100, "quality": 20, "rarity": "rare",
              "influences": ["shaper"], "mods": [{"aid": "2008", "tindex": 7, "bench": 0, "frac": 0}]},
     "donor": {...an item spec, only for the Awakener's Orb...},
     "legal": true,
     "apply": [{"craft": {"action": "harvest", "subaction": "hreroll", "ssaction": "6"}, "repeats": 1000}]}

The answer per check: the built item, the legal-action table (when asked) and, per craft, the
counts of the resulting items by their mods (and the refusals by their message).
"""

import argparse
import datetime
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
DRIVER = HERE / "driver.js"
SITE = "https://www.craftofexile.com"
START = SITE + "/?game=poe1"
HOSTS = ("www.craftofexile.com", "craftofexile.com")
SKIPPED = ("image", "media", "font")


def default_copy() -> Path:
    """`.claude/scratch/coe/site` of the main checkout (also from a worktree of `.claude/worktrees/`)."""
    if os.environ.get("CRAFTING_COE_SITE"):
        return Path(os.environ["CRAFTING_COE_SITE"])
    root = HERE.parents[1]
    if root.parent.name == "worktrees" and root.parent.parent.name == ".claude":
        root = root.parents[2]
    return root / ".claude" / "scratch" / "coe" / "site"


def local_path(copy: Path, url: str) -> Path:
    relative = urlparse(url).path.lstrip("/") or "index.html"
    return copy / relative


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(copy: Path) -> dict:
    copy.mkdir(parents=True, exist_ok=True)
    kept = {}

    def handle(route, request):
        if urlparse(request.url).hostname not in HOSTS or request.resource_type in SKIPPED:
            return route.abort()
        response = route.fetch()
        body = response.body()
        if response.status == 200:
            target = local_path(copy, request.url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            kept[str(target.relative_to(copy)).replace("\\", "/")] = request.url
        route.fulfill(response=response, body=body)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.route("**/*", handle)
        page.goto(START, wait_until="load")
        page.wait_for_function("typeof poecd == 'object' && typeof poec_simApplyCraftGO == 'function'")
        page.click("#emulatorTab")
        page.wait_for_timeout(1500)
        browser.close()
    manifest = {
        "fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "start": START,
        "files": {name: {"url": url, "sha256": sha256(copy / name)} for name, url in sorted(kept.items())},
    }
    (copy / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


class Emulator:
    """The emulator page, open headless on the local copy."""

    def __init__(self, copy: Path) -> None:
        if not (copy / "packages" / "package.js").is_file():
            raise SystemExit(f"no local copy in {copy}; run `emulator.py fetch` first")
        self.copy = copy
        self.errors: list[str] = []
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch()
        self.page = self._browser.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.route("**/*", self._serve)
        self.page.goto(START, wait_until="load")
        self.page.wait_for_function("typeof poecd == 'object' && typeof poec_simApplyCraftGO == 'function'")
        self.page.click("#emulatorTab")
        self.page.wait_for_function("typeof poec_simPickBaseGroup == 'function'")
        self.page.evaluate(DRIVER.read_text(encoding="utf-8"))

    def _serve(self, route, request) -> None:
        if urlparse(request.url).hostname not in HOSTS:
            return route.abort()
        target = local_path(self.copy, request.url)
        if target.is_file():
            return route.fulfill(path=str(target))
        return route.fulfill(status=404, body="")

    def call(self, name: str, *arguments):
        return self.page.evaluate(f"(args) => coeh.{name}(...args)", list(arguments))

    def check(self, check: dict) -> dict:
        started = time.time()
        answer = {"id": check.get("id")}
        donor = None
        if check.get("donor"):
            donor = self.call("build", check["donor"])["exported"]
            answer["donor"] = self.call("describe")
        built = self.call("build", check["item"])
        answer["item"] = built["item"]
        if built["notices"]:
            answer["build_notices"] = built["notices"]
        if check.get("legal"):
            answer["legal"] = self.call("legal")
        answer["apply"] = []
        for step in check.get("apply", []):
            result = self.call("apply", step["craft"], step.get("repeats", 1), {"donor": donor})
            answer["apply"].append({"craft": step["craft"], **result})
        answer["seconds"] = round(time.time() - started, 2)
        if self.errors:
            answer["page_errors"] = self.errors[:]
            self.errors.clear()
        return answer

    def close(self) -> None:
        self._browser.close()
        self._playwright.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=("fetch", "run"))
    parser.add_argument("checks", nargs="?", help="a check file (JSON); stdin when absent")
    parser.add_argument("--copy", type=Path, default=None, help="folder of the local copy")
    arguments = parser.parse_args()
    copy = arguments.copy or default_copy()
    if arguments.command == "fetch":
        manifest = fetch(copy)
        print(json.dumps({"copy": str(copy), **manifest}, indent=1))
        return
    text = Path(arguments.checks).read_text(encoding="utf-8") if arguments.checks else sys.stdin.read()
    checks = json.loads(text)
    emulator = Emulator(copy)
    try:
        answers = [emulator.check(one) for one in (checks if isinstance(checks, list) else [checks])]
    finally:
        emulator.close()
    manifest = copy / "manifest.json"
    version = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else None
    print(json.dumps({"copy": version and {"fetched": version["fetched"], "package.js": version["files"].get("packages/package.js", {}).get("sha256")}, "checks": answers}, indent=1))


if __name__ == "__main__":
    main()
