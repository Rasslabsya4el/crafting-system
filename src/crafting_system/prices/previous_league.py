"""The previous league at the same league age, then Standard (#40). STUB."""

from collections.abc import Sequence

from .fallbacks import Context, Gap, StageResult
from .http_json import GetJson


def previous_league_stage(get_json: GetJson, context: Context, gaps: Sequence[Gap]) -> StageResult:
    return StageResult()
