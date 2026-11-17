"""The list of the target files that named methods before #405 (`tests/former_keys.py`) names only files that exist and carry no key."""

import re

from former_keys import FORMER_KEYS, ROOT


def test_every_file_of_the_list_exists_names_no_methods_and_had_some():
    for path, methods in FORMER_KEYS.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        assert not re.search(r"(?m)^actions\s*:", text), f"{path} names methods again: the parser refuses the key (#405)"
        assert methods, f"{path}: an entry with no former methods would plan with none"
