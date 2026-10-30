"""Reading YAML with line numbers.

`yaml.safe_load` keeps no positions, so the target file is read by a `SafeLoader` that builds `LineMap`
and `LineList` objects: a dict and a list that also know the 1-based line they start on and the line of
each key or entry. Scalars have no line of their own; an error about one is reported at its key or
entry. Anything wrong with the YAML itself becomes a `TargetError`. Merge keys (`<<`) are refused, since
an override through one would look like a key written twice. Anchors (`&name`) and aliases (`*name`) are
refused before any node is built: an alias makes the parser walk the same node again at every use, so a
short file could take minutes and gigabytes to read.
"""

import yaml
import yaml.reader
from yaml.events import AliasEvent, NodeEvent

from .errors import TargetError

MERGE_TAG = "tag:yaml.org,2002:merge"


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

    def compose_node(self, parent, index):
        # Refused while the event is read, before any alias is expanded or node built.
        event = self.peek_event()
        if isinstance(event, AliasEvent):
            raise TargetError(
                f"{self.source}:{event.start_mark.line + 1}: aliases `*{event.anchor}` are not supported;"
                " write the value out"
            )
        if isinstance(event, NodeEvent) and event.anchor is not None:
            raise TargetError(
                f"{self.source}:{event.start_mark.line + 1}: anchors `&{event.anchor}` are not supported;"
                " write the value out"
            )
        return super().compose_node(parent, index)

    def construct_line_map(self, node: yaml.MappingNode) -> LineMap:
        for key_node, _ in node.value:
            if key_node.tag == MERGE_TAG:
                raise TargetError(
                    f"{self.source}:{key_node.start_mark.line + 1}: merge keys `<<` are not supported;"
                    " write the keys out"
                )
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

    Raises `TargetError` for invalid YAML, a character not allowed in text, a key written twice, a key
    that is not text, a merge key (`<<`), an anchor (`&name`) or an alias (`*name`), and nesting too deep
    to read.
    """
    loader = None
    try:
        loader = _LineLoader(text, source)
        return loader.get_single_data()
    except yaml.reader.ReaderError as error:
        line = text.count("\n", 0, error.position) + 1 if isinstance(error.position, int) else 1
        character = f" (U+{ord(error.character):04X})" if isinstance(error.character, str) else ""
        raise TargetError(
            f"{source}:{line}: the file contains a character that is not allowed in text{character};"
            " remove it"
        ) from None
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        line = mark.line + 1 if mark is not None else 1
        problem = getattr(error, "problem", None) or "the YAML could not be read"
        raise TargetError(f"{source}:{line}: not valid YAML: {problem}") from None
    except RecursionError:
        raise TargetError(f"{source}:1: the file is nested too deeply to read") from None
    finally:
        if loader is not None:
            loader.dispose()
