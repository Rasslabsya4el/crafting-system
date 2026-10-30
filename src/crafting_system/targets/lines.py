"""Reading YAML with line numbers.

`yaml.safe_load` keeps no positions, so the target file is read by a `SafeLoader` that builds `LineMap`
and `LineList` objects: a dict and a list that also know the 1-based line they start on and the line of
each key or entry. Scalars have no line of their own; an error about one is reported at its key or
entry. Syntax errors, duplicate keys and keys that are not text become `TargetError`.
"""

import yaml

from .errors import TargetError


class LineMap(dict):
    """A mapping read from YAML: `line` is where it starts, `key_lines` maps each key to its line."""

    def __init__(self, line: int) -> None:
        super().__init__()
        self.line = line
        self.key_lines: dict[str, int] = {}


class LineList(list):
    """A list read from YAML: `line` is where it starts, `item_lines` holds the line of each entry."""

    def __init__(self, line: int) -> None:
        super().__init__()
        self.line = line
        self.item_lines: list[int] = []


class _LineLoader(yaml.SafeLoader):
    def __init__(self, text: str, source: str) -> None:
        super().__init__(text)
        self.source = source

    def construct_line_map(self, node: yaml.MappingNode) -> LineMap:
        self.flatten_mapping(node)
        result = LineMap(node.start_mark.line + 1)
        for key_node, value_node in node.value:
            line = key_node.start_mark.line + 1
            key = self.construct_object(key_node, deep=True)
            if not isinstance(key, str):
                raise TargetError(f"{self.source}:{line}: every key must be text, got {key!r}")
            if key in result:
                raise TargetError(
                    f"{self.source}:{line}: {key}: this key is written twice in one mapping,"
                    f" first on line {result.key_lines[key]}"
                )
            result[key] = self.construct_object(value_node, deep=True)
            result.key_lines[key] = line
        return result

    def construct_line_list(self, node: yaml.SequenceNode) -> LineList:
        result = LineList(node.start_mark.line + 1)
        for child in node.value:
            result.append(self.construct_object(child, deep=True))
            result.item_lines.append(child.start_mark.line + 1)
        return result


_LineLoader.add_constructor("tag:yaml.org,2002:map", _LineLoader.construct_line_map)
_LineLoader.add_constructor("tag:yaml.org,2002:seq", _LineLoader.construct_line_list)


def load_with_lines(text: str, source: str) -> object:
    """Parse one YAML document into `LineMap`, `LineList` and plain scalars (None for an empty document).

    Raises `TargetError` for invalid YAML, for a key written twice and for a key that is not text.
    """
    loader = _LineLoader(text, source)
    try:
        return loader.get_single_data()
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        line = mark.line + 1 if mark is not None else 1
        problem = getattr(error, "problem", None) or "the YAML could not be read"
        raise TargetError(f"{source}:{line}: not valid YAML: {problem}") from None
    finally:
        loader.dispose()
