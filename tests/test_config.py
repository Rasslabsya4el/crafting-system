"""Config: data, cache and output directories from env vars > config file > built-in defaults."""

import codecs
import dataclasses
from pathlib import Path

import pytest

from crafting_system.config import Config, find_project_root, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def write_toml(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_built_in_defaults_are_inside_the_project_when_there_is_no_config_file(tmp_path):
    config = load_config(env={}, project_root=tmp_path)

    assert config == Config(
        data_dir=tmp_path / "local" / "data",
        cache_dir=tmp_path / "local" / "cache",
        output_dir=tmp_path / "local" / "output",
    )


def test_directories_are_absolute_paths(tmp_path):
    config = load_config(env={}, project_root=tmp_path)

    assert all(p.is_absolute() for p in (config.data_dir, config.cache_dir, config.output_dir))


def test_config_is_frozen(tmp_path):
    config = load_config(env={}, project_root=tmp_path)

    with pytest.raises(dataclasses.FrozenInstanceError):
        config.data_dir = tmp_path  # type: ignore[misc]


def test_project_file_overrides_defaults_and_is_resolved_against_the_project_root(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndata = "d"\ncache = "sub/c"\noutput = "o"\n')

    config = load_config(env={}, project_root=tmp_path)

    assert config == Config(tmp_path / "d", tmp_path / "sub" / "c", tmp_path / "o")


def test_keys_missing_from_the_file_fall_back_to_defaults(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndata = "d"\n')

    config = load_config(env={}, project_root=tmp_path)

    assert config.data_dir == tmp_path / "d"
    assert config.cache_dir == tmp_path / "local" / "cache"


def test_file_without_a_paths_table_gives_the_defaults(tmp_path):
    write_toml(tmp_path / "crafting.toml", "# nothing set\n")

    assert load_config(env={}, project_root=tmp_path) == Config(
        tmp_path / "local" / "data", tmp_path / "local" / "cache", tmp_path / "local" / "output"
    )


def test_env_beats_file_per_directory(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndata = "from-file"\ncache = "cache-file"\n')

    config = load_config(env={"CRAFTING_DATA_DIR": "from-env"}, project_root=tmp_path)

    assert config.data_dir == tmp_path / "from-env"
    assert config.cache_dir == tmp_path / "cache-file"
    assert config.output_dir == tmp_path / "local" / "output"


def test_each_env_var_sets_its_own_directory(tmp_path):
    env = {
        "CRAFTING_DATA_DIR": "a",
        "CRAFTING_CACHE_DIR": "b",
        "CRAFTING_OUTPUT_DIR": "c",
    }

    config = load_config(env=env, project_root=tmp_path)

    assert config == Config(tmp_path / "a", tmp_path / "b", tmp_path / "c")


def test_absolute_env_path_is_kept(tmp_path):
    elsewhere = tmp_path / "elsewhere" / "data"

    config = load_config(env={"CRAFTING_DATA_DIR": str(elsewhere)}, project_root=tmp_path / "proj")

    assert config.data_dir == elsewhere


def test_empty_env_value_counts_as_unset(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndata = "from-file"\n')

    config = load_config(env={"CRAFTING_DATA_DIR": ""}, project_root=tmp_path)

    assert config.data_dir == tmp_path / "from-file"


def test_crafting_config_replaces_the_project_file(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndata = "project-file"\ncache = "project-cache"\n')
    other = write_toml(tmp_path / "elsewhere" / "mine.toml", '[paths]\ndata = "mine"\n')

    config = load_config(env={"CRAFTING_CONFIG": str(other)}, project_root=tmp_path)

    assert config.data_dir == tmp_path / "elsewhere" / "mine"  # against the config file's directory
    assert config.cache_dir == tmp_path / "local" / "cache"  # the project file is not read


def test_relative_crafting_config_is_taken_against_the_project_root(tmp_path):
    write_toml(tmp_path / "conf" / "mine.toml", '[paths]\ndata = "x"\n')

    config = load_config(env={"CRAFTING_CONFIG": "conf/mine.toml"}, project_root=tmp_path)

    assert config.data_dir == tmp_path / "conf" / "x"


def test_env_beats_the_file_named_by_crafting_config(tmp_path):
    other = write_toml(tmp_path / "mine.toml", '[paths]\ndata = "mine"\n')
    env = {"CRAFTING_CONFIG": str(other), "CRAFTING_DATA_DIR": "env-data"}

    assert load_config(env=env, project_root=tmp_path).data_dir == tmp_path / "env-data"


def test_empty_crafting_config_counts_as_unset(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndata = "project-file"\n')

    config = load_config(env={"CRAFTING_CONFIG": ""}, project_root=tmp_path)

    assert config.data_dir == tmp_path / "project-file"


def test_crafting_config_naming_a_missing_file_is_an_error_that_names_it(tmp_path):
    missing = tmp_path / "nope.toml"

    with pytest.raises(ValueError, match="nope.toml"):
        load_config(env={"CRAFTING_CONFIG": str(missing)}, project_root=tmp_path)


def test_invalid_toml_is_an_error_that_names_the_file(tmp_path):
    write_toml(tmp_path / "crafting.toml", "[paths\ndata = ")

    with pytest.raises(ValueError, match="crafting.toml"):
        load_config(env={}, project_root=tmp_path)


def test_unknown_key_in_paths_is_an_error_naming_file_and_key(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndta = "typo"\n')

    with pytest.raises(ValueError, match=r"crafting\.toml.*dta"):
        load_config(env={}, project_root=tmp_path)


def test_unknown_top_level_table_is_an_error_naming_file_and_key(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[path]\ndata = "typo"\n')

    with pytest.raises(ValueError, match=r"crafting\.toml.*path"):
        load_config(env={}, project_root=tmp_path)


@pytest.mark.parametrize("value", ["3", "true", '["a"]', "{ x = 1 }", '""', '"   "', '"\\t"'])
def test_non_string_or_empty_value_is_an_error_naming_file_and_key(tmp_path, value):
    write_toml(tmp_path / "crafting.toml", f"[paths]\ncache = {value}\n")

    with pytest.raises(ValueError, match=r"crafting\.toml.*cache"):
        load_config(env={}, project_root=tmp_path)


def test_recombinator_junk_craft_is_off_by_default(tmp_path):
    assert load_config(env={}, project_root=tmp_path).recombinator_junk_craft is False


def test_recombinator_junk_craft_true_is_read_from_the_planner_table(tmp_path):
    write_toml(tmp_path / "crafting.toml", "[planner]\nrecombinator_junk_craft = true\n")

    assert load_config(env={}, project_root=tmp_path).recombinator_junk_craft is True


@pytest.mark.parametrize("value", ["1", '"yes"', '"true"'])
def test_non_bool_recombinator_junk_craft_is_an_error_naming_file_and_key(tmp_path, value):
    write_toml(tmp_path / "crafting.toml", f"[planner]\nrecombinator_junk_craft = {value}\n")

    with pytest.raises(ValueError, match=r"crafting\.toml.*recombinator_junk_craft"):
        load_config(env={}, project_root=tmp_path)


def test_load_config_creates_no_directories(tmp_path):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndata = "d"\n')
    before = sorted(tmp_path.rglob("*"))

    load_config(env={"CRAFTING_OUTPUT_DIR": "o"}, project_root=tmp_path)

    assert sorted(tmp_path.rglob("*")) == before


def test_env_defaults_to_the_process_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CRAFTING_DATA_DIR", "from-process-env")
    monkeypatch.delenv("CRAFTING_CONFIG", raising=False)

    assert load_config(project_root=tmp_path).data_dir == tmp_path / "from-process-env"


def test_project_root_is_found_from_the_package_location(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # prove the current directory is not what is used

    config = load_config(env={})

    assert config.data_dir == REPO_ROOT / "local" / "data"


def test_without_a_pyproject_in_the_searched_folders_the_current_directory_is_the_root(
    monkeypatch, tmp_path
):
    # `search_up_to` keeps the walk inside tmp_path, wherever pytest put it (it may be inside
    # a project that does have a pyproject.toml)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert find_project_root(start=nested, search_up_to=tmp_path) == Path.cwd()


def test_the_nearest_pyproject_above_start_is_the_root(tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "a" / "pyproject.toml").write_text("", encoding="utf-8")

    assert find_project_root(start=nested, search_up_to=tmp_path) == tmp_path / "a"


def test_a_pyproject_at_the_search_limit_counts(tmp_path):
    nested = tmp_path / "a"
    nested.mkdir()
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")

    assert find_project_root(start=nested, search_up_to=tmp_path) == tmp_path


def test_a_pyproject_above_the_search_limit_is_not_looked_at(monkeypatch, tmp_path):
    limit = tmp_path / "a"
    nested = limit / "b"
    nested.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.chdir(nested)

    assert find_project_root(start=nested, search_up_to=limit) == Path.cwd()


def test_config_file_with_a_utf8_bom_is_accepted(tmp_path):
    (tmp_path / "crafting.toml").write_bytes(codecs.BOM_UTF8 + b'[paths]\ndata = "d"\n')

    assert load_config(env={}, project_root=tmp_path).data_dir == tmp_path / "d"


def test_config_file_that_is_not_utf8_is_an_error_naming_the_file(tmp_path):
    # what PowerShell 5.1's `>` writes
    (tmp_path / "crafting.toml").write_bytes('[paths]\ndata = "d"\n'.encode("utf-16"))

    with pytest.raises(ValueError, match=r"crafting\.toml.*UTF-8") as caught:
        load_config(env={}, project_root=tmp_path)

    assert not isinstance(caught.value, UnicodeDecodeError)


@pytest.mark.parametrize("blank", [" ", "   ", "\t", " \t "])
def test_whitespace_only_env_value_counts_as_unset(tmp_path, blank):
    write_toml(tmp_path / "crafting.toml", '[paths]\ndata = "from-file"\n')
    env = {"CRAFTING_DATA_DIR": blank, "CRAFTING_CONFIG": blank}

    assert load_config(env=env, project_root=tmp_path).data_dir == tmp_path / "from-file"


@pytest.fixture
def home(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("USERPROFILE", str(home_dir))
    return home_dir


TILDE = "~"


def test_leading_tilde_in_an_env_value_is_the_home_folder(tmp_path, home):
    env = {"CRAFTING_DATA_DIR": TILDE + "/data", "CRAFTING_CACHE_DIR": TILDE}

    config = load_config(env=env, project_root=tmp_path / "proj")

    assert config.data_dir == home / "data"
    assert config.cache_dir == home


def test_leading_tilde_in_a_config_value_is_the_home_folder(tmp_path, home):
    write_toml(tmp_path / "crafting.toml", f'[paths]\ndata = "{TILDE}/data"\n')

    assert load_config(env={}, project_root=tmp_path).data_dir == home / "data"


def test_leading_tilde_in_crafting_config_is_the_home_folder(tmp_path, home):
    write_toml(home / "mine.toml", '[paths]\ndata = "x"\n')

    config = load_config(env={"CRAFTING_CONFIG": TILDE + "/mine.toml"}, project_root=tmp_path)

    assert config.data_dir == home / "x"


def test_a_tilde_that_is_not_leading_stays_a_plain_name(tmp_path, home):
    config = load_config(env={"CRAFTING_DATA_DIR": "a/" + TILDE + "/b"}, project_root=tmp_path)

    assert config.data_dir == tmp_path / "a" / TILDE / "b"


def test_committed_crafting_toml_holds_the_built_in_defaults():
    committed = load_config(env={}, project_root=REPO_ROOT)

    assert (REPO_ROOT / "crafting.toml").is_file()
    assert committed == Config(
        REPO_ROOT / "local" / "data",
        REPO_ROOT / "local" / "cache",
        REPO_ROOT / "local" / "output",
    )
    assert "local/data" in (REPO_ROOT / "crafting.toml").read_text(encoding="utf-8")


def test_config_module_imports_no_layer():
    import ast

    from crafting_system import config as config_module

    tree = ast.parse(Path(config_module.__file__).read_text(encoding="utf-8"))
    absolute = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    }
    relative = [
        node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level > 0
    ]

    assert not [name for name in absolute if name.startswith("crafting_system")]
    assert relative == []


# --- the planner settings (ADR-0040 memory_strands, ADR-0059 recipe_starts, ADR-0060 max_imprints) ---------------------------------------------------


def test_recipe_starts_is_on_by_default_and_memory_strands_off(tmp_path):
    config = load_config(env={}, project_root=tmp_path)

    assert config.recipe_starts is True and config.memory_strands is False


def test_recipe_starts_can_be_turned_off_in_the_planner_table(tmp_path):
    write_toml(tmp_path / "crafting.toml", "[planner]\nrecipe_starts = false\nmemory_strands = true\n")

    config = load_config(env={}, project_root=tmp_path)

    assert config.recipe_starts is False and config.memory_strands is True


@pytest.mark.parametrize("value", ['"no"', "0", "[]"])
def test_recipe_starts_must_be_true_or_false(tmp_path, value):
    write_toml(tmp_path / "crafting.toml", f"[planner]\nrecipe_starts = {value}\n")

    with pytest.raises(ValueError, match="recipe_starts.*true or false"):
        load_config(env={}, project_root=tmp_path)


def test_max_imprints_is_one_by_default(tmp_path):
    config = load_config(env={}, project_root=tmp_path)

    assert config.max_imprints == 1


def test_max_imprints_can_be_set_in_the_planner_table(tmp_path):
    write_toml(tmp_path / "crafting.toml", "[planner]\nmax_imprints = 2\n")

    config = load_config(env={}, project_root=tmp_path)

    assert config.max_imprints == 2


@pytest.mark.parametrize("value", ["0", "-1", "1.5", '"2"', "true"])
def test_max_imprints_must_be_a_whole_number_of_at_least_one(tmp_path, value):
    write_toml(tmp_path / "crafting.toml", f"[planner]\nmax_imprints = {value}\n")

    with pytest.raises(ValueError, match="'max_imprints' must be a whole number of at least 1"):
        load_config(env={}, project_root=tmp_path)


def test_an_unknown_planner_key_names_all_known_settings(tmp_path):
    write_toml(tmp_path / "crafting.toml", "[planner]\nrecipe_start = false\n")

    with pytest.raises(ValueError, match="known: memory_strands, recipe_starts, recombinator_junk_craft, max_imprints"):
        load_config(env={}, project_root=tmp_path)
