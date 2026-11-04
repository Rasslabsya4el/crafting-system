"""The diary of the measurement chain (ticket #399): one plain Russian comment on issue #398 per finished step.

`build_text` is the whole text, a pure function. `main` posts it with `gh issue comment`, and a failed post only
prints to stderr: a diary failure never fails the chain. `--dry-run` prints the text instead.
"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

STEPS = ["bloat", "routes", "coverage", "repeats", "mutation"]
TOTAL = len(STEPS)
NAMES = {
    "bloat": "раздутие состояний",
    "routes": "таблица эталонных маршрутов",
    "coverage": "карта покрытия",
    "repeats": "повторы всех тестов",
    "mutation": "мутационное тестирование",
}
# Minutes a step is expected to take. Mutation has no full estimate: it fills the machines up to the deadline.
ESTIMATE_MINUTES = {"bloat": 180, "routes": 90, "coverage": 120, "repeats": 240, "mutation": None}
TRIAL_MINUTES = {"bloat": 10, "routes": 10, "coverage": 10, "repeats": 15, "mutation": 10}
DEADLINE = "до дедлайна 2026-11-06 06:00 UTC (09:00 МСК)"
RESULT_WORDS = {"success": "успешно", "failure": "упал", "cancelled": "отменён", "skipped": "пропущен"}
MOSCOW_OFFSET = timedelta(hours=3)


def result_word(result: str) -> str:
    """The Russian word for a job result; an unknown result is written as it came."""
    return RESULT_WORDS.get(result, result)


def ends_at(step: str, trial: bool, now: datetime) -> str:
    """When a step that starts at `now` is expected to end: a time 'около HH:MM UTC (HH:MM МСК), DD.MM',
    or the deadline text for the full mutation step."""
    minutes = (TRIAL_MINUTES if trial else ESTIMATE_MINUTES)[step]
    if minutes is None:
        return DEADLINE
    end_utc = now + timedelta(minutes=minutes)
    end_msk = end_utc + MOSCOW_OFFSET
    return f"около {end_utc:%H:%M} UTC ({end_msk:%H:%M} МСК), {end_msk:%d.%m}"


def read_headline(path: Path) -> str | None:
    """The first line of a step's headline.txt, or None when the artifact or the line is missing."""
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return lines[0] if lines else None


def build_text(done, result, art_dir, trial, run_url, results, now) -> str:
    """The comment for one event of the chain.

    done: "none" (the chain started), a step name (that step finished), or "report" (the chain finished).
    result: the job result of the finished step (success, failure, cancelled, skipped).
    art_dir: the folder holding each step's artifact in `<step>/headline.txt`.
    results: a dict of step name to job result, for the report (or None).
    now: the current time, timezone-aware UTC.
    """
    kind = "пробный прогон" if trial else "полный прогон"
    if done == "none":
        first = STEPS[0]
        return (
            f"Цепочка замеров запущена ({kind}). Шаг 1 из {TOTAL}: {NAMES[first]}, "
            f"конец ожидается {ends_at(first, trial, now)}.\n"
            f"Запуск: {run_url}"
        )
    if done == "report":
        text = "Цепочка закончена."
        if results:
            parts = [f"{NAMES[step]} — {result_word(results[step])}" for step in STEPS if step in results]
            text += " Итоги шагов: " + "; ".join(parts) + "."
        return f"{text} Сводка: артефакт measure-report на странице запуска {run_url}"

    index = STEPS.index(done)
    lines = [f"Шаг {index + 1} из {TOTAL} ({NAMES[done]}): {result_word(result)}."]
    headline = read_headline(Path(art_dir) / done / "headline.txt")
    lines.append(f"Главное: {headline}" if headline else "Итогов нет.")
    if index + 1 < TOTAL:
        following = STEPS[index + 1]
        lines.append(f"Дальше шаг {index + 2}: {NAMES[following]}, конец {ends_at(following, trial, now)}.")
    lines.append(f"Запуск: {run_url}")
    return "\n".join(lines)


def post(issue: int, text: str) -> None:
    """Post the comment with the gh CLI (GH_TOKEN and GH_REPO come from the environment)."""
    subprocess.run(["gh", "issue", "comment", str(issue), "--body", text], check=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Post one step's diary comment for the measurement chain (#399).")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--done", required=True, choices=["none", *STEPS, "report"])
    parser.add_argument("--result", required=True)
    parser.add_argument("--art", default="art", help="folder of the downloaded artifacts, one folder per step")
    parser.add_argument("--trial", required=True, choices=["true", "false"])
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--results", help='JSON of step name to job result, for --done report')
    parser.add_argument("--dry-run", action="store_true", help="print the text instead of posting it")
    args = parser.parse_args(argv)
    try:
        results = json.loads(args.results) if args.results else None
        text = build_text(
            args.done, args.result, args.art, args.trial == "true", args.run_url, results,
            datetime.now(UTC),
        )
        if args.dry_run:
            print(text)
            return 0
        post(args.issue, text)
    except Exception as error:  # a diary failure never fails the chain
        print(f"measure_diary: the comment was not posted: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
