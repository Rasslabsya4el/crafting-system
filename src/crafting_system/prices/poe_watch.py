"""poe.watch for the current league: `/exchange/ratios`, then `/get`, then `/history` (#40). STUB."""

from collections.abc import Sequence

from .fallbacks import Context, Gap, StageResult
from .http_json import GetJson

BASE_URL = "https://api.poe.watch"


def poe_watch_stage(get_json: GetJson, context: Context, gaps: Sequence[Gap]) -> StageResult:
    return StageResult()
