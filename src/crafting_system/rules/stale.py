"""Which claims were last verified on a patch older than the pinned one (step 6 of the patch update).

A claim keeps the patch it was last checked on in `patch_verified`. After the pin moves to a new
patch, every claim older than the pin is a claim nobody has re-read against the new patch yet;
`stale_rules` lists them and `python -m crafting_system.rules stale` prints the list.
"""

from collections.abc import Mapping
from pathlib import Path

from crafting_system.data import PIN_FILE, load_pin

from .registry import PATCH_PATTERN, RegistryError, Rule, load_registry, patch_order_key


def stale_rules(registry: Mapping[str, Rule], pinned: str) -> list[Rule]:
    """The rules of `registry` whose `patch_verified` is older than the patch `pinned`, in registry order.

    A rule verified on the pinned patch or on a later one is not stale.
    """
    if not PATCH_PATTERN.fullmatch(pinned):
        raise RegistryError(f"the pinned version {pinned!r} is not a patch like \"3.29.3.3\"")
    limit = patch_order_key(pinned)
    return [rule for rule in registry.values() if patch_order_key(rule.patch_verified) < limit]


def render_stale(stale: list[Rule], total: int, pinned: str) -> str:
    """The text `rules stale` prints: a header, then one line per rule with the url to re-read."""
    if not stale:
        return f"All {total} claims were verified on {pinned} or later."
    lines = [f"{len(stale)} of {total} claims were last verified before {pinned}:"]
    width = max(len(rule.id) for rule in stale)
    lines += [
        f"  {rule.id.ljust(width)}  {rule.patch_verified}  {rule.source_kind.value}  {rule.url}"
        for rule in stale
    ]
    return "\n".join(lines)


def stale_report(claims: Path | None = None, pin_file: Path = PIN_FILE) -> str:
    """Load the claims (the shipped ones when `claims` is None) and the pin, and return the text of `rules stale`."""
    registry = load_registry(claims)
    pinned = load_pin(pin_file).version
    return render_stale(stale_rules(registry, pinned), len(registry), pinned)
