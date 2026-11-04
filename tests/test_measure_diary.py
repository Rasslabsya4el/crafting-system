"""The diary of the measurement chain (ticket #399): the Russian text posted to issue #398 after each step."""

import importlib.util
import subprocess
from datetime import UTC, datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "measure_diary.py"
spec = importlib.util.spec_from_file_location("measure_diary", SCRIPT)
measure_diary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_diary)

NOW = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
RUN_URL = "https://example/run/1"
DEADLINE = "до дедлайна 2026-11-06 06:00 UTC (09:00 МСК)"


def build(done, result, art, *, trial=False, results=None):
    return measure_diary.build_text(done, result, art, trial, RUN_URL, results, NOW)


def test_start_full_chain_names_bloat_and_its_end(tmp_path):
    # 180 minutes after 10:00 UTC is 13:00 UTC, which is 16:00 Moscow time on the same day
    text = build("none", "success", tmp_path / "art")
    assert text == (
        "Цепочка замеров запущена (полный прогон). Шаг 1 из 5: раздутие состояний, "
        "конец ожидается около 13:00 UTC (16:00 МСК), 02.11.\n"
        f"Запуск: {RUN_URL}"
    )


def test_start_trial_chain_uses_the_ten_minute_estimate(tmp_path):
    text = build("none", "success", tmp_path / "art", trial=True)
    assert text == (
        "Цепочка замеров запущена (пробный прогон). Шаг 1 из 5: раздутие состояний, "
        "конец ожидается около 10:10 UTC (13:10 МСК), 02.11.\n"
        f"Запуск: {RUN_URL}"
    )


def test_done_step_with_headline_names_the_next_step(tmp_path):
    art = tmp_path / "art"
    (art / "routes").mkdir(parents=True)
    (art / "routes" / "headline.txt").write_text("R10: 12 s, 310 MB\nвторая строка\n", encoding="utf-8")
    # coverage follows routes: 120 minutes after 10:00 UTC is 12:00 UTC, 15:00 Moscow time
    text = build("routes", "success", art)
    assert text == (
        "Шаг 2 из 5 (таблица эталонных маршрутов): успешно.\n"
        "Главное: R10: 12 s, 310 MB\n"
        "Дальше шаг 3: карта покрытия, конец около 12:00 UTC (15:00 МСК), 02.11.\n"
        f"Запуск: {RUN_URL}"
    )


def test_failed_step_with_no_artifact_says_no_results(tmp_path):
    text = build("bloat", "failure", tmp_path / "art")
    assert text == (
        "Шаг 1 из 5 (раздутие состояний): упал.\n"
        "Итогов нет.\n"
        "Дальше шаг 2: таблица эталонных маршрутов, конец около 11:30 UTC (14:30 МСК), 02.11.\n"
        f"Запуск: {RUN_URL}"
    )


def test_step_before_mutation_names_the_deadline_not_a_time(tmp_path):
    text = build("repeats", "success", tmp_path / "art")
    assert text == (
        "Шаг 4 из 5 (повторы всех тестов): успешно.\n"
        "Итогов нет.\n"
        f"Дальше шаг 5: мутационное тестирование, конец {DEADLINE}.\n"
        f"Запуск: {RUN_URL}"
    )


def test_mutation_step_has_no_next_step(tmp_path):
    art = tmp_path / "art"
    (art / "mutation").mkdir(parents=True)
    (art / "mutation" / "headline.txt").write_text("killed 12 of 20\n", encoding="utf-8")
    text = build("mutation", "cancelled", art)
    assert text == (
        "Шаг 5 из 5 (мутационное тестирование): отменён.\n"
        "Главное: killed 12 of 20\n"
        f"Запуск: {RUN_URL}"
    )


def test_report_lists_each_step_result(tmp_path):
    results = {
        "bloat": "success",
        "routes": "failure",
        "coverage": "success",
        "repeats": "success",
        "mutation": "cancelled",
    }
    text = build("report", "success", tmp_path / "art", results=results)
    assert text == (
        "Цепочка закончена. Итоги шагов: раздутие состояний — успешно; "
        "таблица эталонных маршрутов — упал; карта покрытия — успешно; "
        "повторы всех тестов — успешно; мутационное тестирование — отменён. "
        f"Сводка: артефакт measure-report на странице запуска {RUN_URL}"
    )


def test_report_without_results_omits_the_step_list(tmp_path):
    text = build("report", "success", tmp_path / "art")
    assert text == (
        "Цепочка закончена. Сводка: артефакт measure-report на странице запуска " + RUN_URL
    )


def test_posting_failure_still_exits_zero(monkeypatch, tmp_path, capsys):
    def refused(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ["gh"])

    monkeypatch.setattr(measure_diary.subprocess, "run", refused)
    code = measure_diary.main(
        ["--issue", "398", "--done", "none", "--result", "success", "--art", str(tmp_path),
         "--trial", "true", "--run-url", RUN_URL]
    )
    assert code == 0
    assert "not posted" in capsys.readouterr().err
