"""No absolute path in code or committed config (ADR-0014).

Reads every git-tracked file of a code or config kind and fails on a drive letter path, a UNC
path, a home directory, or a POSIX absolute path under a system directory. Docs (.md) are not
scanned. The bad samples below are assembled from pieces so their literal text never appears in
this file, which the scan reads like any other.
"""

import re
import subprocess
from pathlib import Path, PurePosixPath

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

SCANNED_SUFFIXES = {
    ".py", ".toml", ".yml", ".yaml", ".json", ".cfg", ".ini",
    ".ps1", ".psm1", ".sh", ".bash", ".bat", ".cmd", ".txt", ".env",
}  # fmt: skip
SCANNED_NAMES = {"uv.lock", ".python-version", ".gitattributes", ".gitignore", ".env"}


def is_scanned(name: str) -> bool:
    """Whether a tracked file (by name, case-insensitive) is a code or config kind."""
    lowered = PurePosixPath(name).name.lower()
    return (
        PurePosixPath(lowered).suffix in SCANNED_SUFFIXES
        or lowered in SCANNED_NAMES
        or lowered.startswith(".env.")
    )


SYSTEM_DIRS = (
    "tmp", "var", "opt", "srv", "mnt", "etc", "usr", "media",
    "dev", "proc", "run", "bin", "sbin", "lib", "Volumes",
)  # fmt: skip

# Web and other URLs are not paths; a URL ends at whitespace, a quote, a comma, a parenthesis or
# an angle bracket, so a path written right after one is still seen. `file:` URLs are kept,
# since they carry real paths.
URL = re.compile(r"\b(?!file:)[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'`,()<>]*")

# What may not come right before the slash that starts an absolute POSIX-style path.
NOT_BEFORE_SLASH = r"(?<![\w./~:)\]}-])"

# Each rule: (kind, pattern). The patterns are written so that their own text does not match.
RULES = (
    # a letter, a colon, then a backslash or a single slash; the `(?!/)` keeps the colon-slash
    # of `https://` and `file:///` out of it
    ("drive letter path", re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:(?:\\|/(?!/))")),
    # Git Bash / MSYS spelling of a drive: one letter between slashes, then a name
    ("MSYS drive path", re.compile(NOT_BEFORE_SLASH + r"/[A-Za-z]/(?=[\w.$-])")),
    ("UNC path", re.compile(r"\\{2,}[\w.$-]+\\+[\w$-]")),
    # the same with forward slashes; the lookbehind keeps the slashes of `scheme://` out
    ("UNC path", re.compile(r"(?<![:/\w])//[\w.$-]+/[\w$-]")),
    ("home directory", re.compile(NOT_BEFORE_SLASH + r"/(?:home|Users|root)/")),
    ("home directory", re.compile(r"(?<!\w)~[/\\]")),
    ("home directory", re.compile(r"\$\{?" + "HOME" + r"\b")),
    ("home directory", re.compile("%" + "USERPROFILE" + "%")),
    ("home directory", re.compile("%" + "(?:LOCAL)?APPDATA" + "%")),
    (
        "system directory path",
        re.compile(NOT_BEFORE_SLASH + r"/(?:" + "|".join(SYSTEM_DIRS) + r")/"),
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
    *[
        ("/" + name + "/data", "system directory path")
        for name in ("dev", "proc", "run", "bin", "sbin", "lib", "Volumes")
    ],
    ("/" + "c" + "/Us" + "ers/anton/data", "MSYS drive path"),
    ("/" + "D" + "/work", "MSYS drive path"),
    ("path='/" + "e" + "/work'", "MSYS drive path"),
    ("/" + "/" + "fileserver/share", "UNC path"),
    ("'/" + "/" + "fileserver/share/x'", "UNC path"),
    ("%" + "APPDATA" + "%\\x", "home directory"),
    ("%" + "LOCALAPPDATA" + "%\\x", "home directory"),
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
    # too many false positives to flag: drive-relative and root-relative-looking names
    "C:work",
    "Z:foo",
    "/data",
    "/data/x",
    "/app",
    "/workspace/x",
    # near misses of the MSYS drive and forward-slash UNC rules
    "s/a/b/",
    "a/c/b",
    "{a}/b/{c}",
    "/cc/x",
    "/c",
    "/c/",
    "a//b/c",
    "https://x.com/c/y",
    "https://host/share",
    "src/lib/x",
    "src/bin/run",
    "src/dev/null",
]

URL_FOLLOWERS = ['"', "'", ",", ")", "(", "<", ">", " ", "`", "\t"]


@pytest.mark.parametrize("separator", URL_FOLLOWERS)
def test_a_path_written_right_after_a_url_is_still_flagged(separator):
    sample = "https://a.b/c" + separator + WIN_BACK

    assert find_absolute_paths(sample) == ["drive letter path"]


@pytest.mark.parametrize(
    "sample",
    [
        '{"u":"https://x.com","p":"' + "C" + ":" + "\\\\" + 'work"}',
        'get("https://a.b/c","' + "C" + ":" + "\\\\" + 'work")',
        "[https://a.b](" + WIN_FWD + ")",
    ],
)
def test_a_path_next_to_a_url_in_code_is_flagged(sample):
    assert find_absolute_paths(sample) == ["drive letter path"]


@pytest.mark.parametrize(
    "name",
    [
        "a.py",
        "pyproject.toml",
        "CONF.TOML",
        "x.Yml",
        "x.yaml",
        "x.JSON",
        "setup.cfg",
        "tox.INI",
        "run.ps1",
        "mod.psm1",
        "run.sh",
        "run.bash",
        "run.bat",
        "run.cmd",
        "notes.txt",
        "LICENSE.TXT",
        "x.env",
        ".env",
        ".ENV",
        ".env.local",
        ".env.production",
        "sub/dir/a.JSON",
        "uv.lock",
        ".python-version",
        ".gitattributes",
        ".gitignore",
    ],
)
def test_code_and_config_kinds_are_scanned(name):
    assert is_scanned(name)


@pytest.mark.parametrize(
    "name", ["README.md", "notes.MD", "a.png", "environment", "env.md", "a.lockfile", "src/a.pyc"]
)
def test_docs_and_binaries_are_not_scanned(name):
    assert not is_scanned(name)


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
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            capture_output=True,
            encoding="utf-8",  # not the locale's: file names may be non-ASCII
            check=False,
        )
    except FileNotFoundError:
        pytest.fail("git is not installed or not on PATH; the absolute-path guard needs `git ls-files`")
    if result.returncode != 0:
        pytest.fail(f"`git ls-files` failed in {repo_root.name}: {result.stderr.strip()}")
    names = [name for name in result.stdout.split("\0") if name]
    return [
        repo_root / name
        for name in names
        if is_scanned(name) and (repo_root / name).is_file()
    ]


def scan(files: list[Path], repo_root: Path) -> list[str]:
    problems = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            for kind in find_absolute_paths(line):
                problems.append(f"{path.relative_to(repo_root).as_posix()}:{number}: {kind}")
    return problems


def test_tracked_file_with_a_non_ascii_name_is_listed(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "données.toml").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("docs\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)

    listed = [path.name for path in tracked_files(tmp_path)]

    assert listed == ["données.toml"]


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
