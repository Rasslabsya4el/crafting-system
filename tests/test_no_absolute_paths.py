"""No absolute path in code or committed config (ADR-0014).

Reads every git-tracked file of a code or config kind and fails on a drive letter path, a UNC
path, a home directory, or a POSIX absolute path under a system directory. Docs (.md) are not
scanned. The bad samples below are assembled from pieces so their literal text never appears in
this file, which the scan reads like any other.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

SCANNED_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".json", ".cfg", ".ini"}
SCANNED_NAMES = {"uv.lock", ".python-version", ".gitattributes", ".gitignore"}

SYSTEM_DIRS = ("tmp", "var", "opt", "srv", "mnt", "etc", "usr", "media")

# Web and other URLs are not paths. `file:` URLs are kept, since they carry real paths.
URL = re.compile(r"\b(?!file:)[A-Za-z][A-Za-z0-9+.-]*://\S*")

# Each rule: (kind, pattern). The patterns are written so that their own text does not match.
RULES = (
    # a letter, a colon, then a backslash or a single slash; the `(?!/)` keeps the colon-slash
    # of `https://` and `file:///` out of it
    ("drive letter path", re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:(?:\\|/(?!/))")),
    ("UNC path", re.compile(r"\\{2,}[\w.$-]+\\+[\w$-]")),
    ("home directory", re.compile(r"(?<![\w.-])/(?:home|Users|root)/")),
    ("home directory", re.compile(r"(?<!\w)~[/\\]")),
    ("home directory", re.compile(r"\$\{?" + "HOME" + r"\b")),
    ("home directory", re.compile("%" + "USERPROFILE" + "%")),
    (
        "system directory path",
        re.compile(r"(?<![\w./~-])/(?:" + "|".join(SYSTEM_DIRS) + r")/"),
    ),
)


def find_absolute_paths(text: str) -> list[str]:
    """Kinds of absolute path found in `text`, in order of appearance (URLs are ignored)."""
    text = URL.sub(" ", text)
    hits = [(match.start(), kind) for kind, rule in RULES for match in rule.finditer(text)]
    return [kind for _, kind in sorted(hits)]


# Bad samples, built so that the finished text is not contiguous in this source.
WIN_BACK = "C" + ":" + "\\" + "work" + "\\" + "data"
WIN_FWD = "D" + ":" + "/" + "work/data"
WIN_JSON_ESCAPED = '"E' + ":" + "\\\\" + 'work"'
FILE_URL_DRIVE = "file" + ":///" + "C" + ":/" + "work"
UNC = "\\\\" + "fileserver" + "\\" + "share"
WIN_HOME = "C" + ":" + "\\" + "Users" + "\\" + "anton"

BAD_SAMPLES = [
    (WIN_BACK, "drive letter path"),
    (WIN_FWD, "drive letter path"),
    (WIN_JSON_ESCAPED, "drive letter path"),
    (FILE_URL_DRIVE, "drive letter path"),
    (WIN_HOME, "drive letter path"),
    (UNC, "UNC path"),
    ("/ho" + "me/anton/data", "home directory"),
    ("/Us" + "ers/anton/data", "home directory"),
    ("/ro" + "ot/data", "home directory"),
    ("~" + "/data", "home directory"),
    ("~" + "\\data", "home directory"),
    ("$" + "HOME/data", "home directory"),
    ("${" + "HOME}/data", "home directory"),
    ("%" + "USERPROFILE" + "%\\data", "home directory"),
    *[("/" + name + "/data", "system directory path") for name in SYSTEM_DIRS],
]

GOOD_SAMPLES = [
    "https://github.com/Rasslabsya4el/crafting-system",
    "http://example.com/" + "tmp" + "/x",
    "https://example.com/" + "ho" + "me/page",
    "ssh://git@host/" + "var" + "/repo",
    "local/data",
    "./local/cache",
    "../output",
    "src/crafting_system/config.py",
    "docs/" + "etc" + "/notes",
    "../" + "usr" + "/share",
    "a/" + "tmp" + "/b",
    "key: value",
    "a:b",
    "ratio 1:2",
    'pattern = "x+y"',
    "",
]


@pytest.mark.parametrize(("sample", "kind"), BAD_SAMPLES)
def test_detector_flags_each_kind_of_absolute_path(sample, kind):
    assert find_absolute_paths(sample) == [kind]


@pytest.mark.parametrize(
    "sample",
    [
        "path = '" + WIN_BACK + "'",
        "open('" + "/t" + "mp/x" + "')",
        "see " + "~" + "/notes for more",
        "dir=" + "/va" + "r/log",
    ],
)
def test_detector_flags_paths_inside_code(sample):
    assert find_absolute_paths(sample) != []


@pytest.mark.parametrize("sample", GOOD_SAMPLES)
def test_detector_passes_urls_and_relative_paths(sample):
    assert find_absolute_paths(sample) == []


def tracked_files(repo_root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"], cwd=repo_root, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        pytest.fail("git is not installed or not on PATH; the absolute-path guard needs `git ls-files`")
    if result.returncode != 0:
        pytest.fail(f"`git ls-files` failed in {repo_root.name}: {result.stderr.strip()}")
    names = [name for name in result.stdout.split("\0") if name]
    return [
        repo_root / name
        for name in names
        if (Path(name).suffix in SCANNED_SUFFIXES or Path(name).name in SCANNED_NAMES)
        and (repo_root / name).is_file()
    ]


def scan(files: list[Path], repo_root: Path) -> list[str]:
    problems = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            for kind in find_absolute_paths(line):
                problems.append(f"{path.relative_to(repo_root).as_posix()}:{number}: {kind}")
    return problems


def test_scan_reports_file_and_line_of_a_bad_path(tmp_path):
    bad = tmp_path / "settings.toml"
    bad.write_text("fine = 1\ndata = '" + WIN_BACK + "'\n", encoding="utf-8")

    assert scan([bad], tmp_path) == ["settings.toml:2: drive letter path"]


def test_scan_reads_the_code_and_config_kinds_of_the_repo():
    names = {path.relative_to(REPO_ROOT).as_posix() for path in tracked_files(REPO_ROOT)}

    assert {
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".gitattributes",
        ".gitignore",
        "crafting.toml",
        ".github/workflows/ci.yml",
        "src/crafting_system/config.py",
        "tests/test_no_absolute_paths.py",
    } <= names
    assert not [name for name in names if name.endswith(".md")]


def test_missing_git_fails_with_a_clear_message(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda *args, **kwargs: None)

    with pytest.raises(pytest.fail.Exception, match="git is not installed"):
        tracked_files(REPO_ROOT)


def test_no_absolute_path_in_tracked_code_or_config():
    problems = scan(tracked_files(REPO_ROOT), REPO_ROOT)

    assert problems == []
