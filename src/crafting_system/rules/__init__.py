"""The registry of admitted mechanics with provenance (ADR-0004). May import only: data."""

from .registry import (
    HistoryEntry,
    RegistryError,
    Rule,
    SourceKind,
    UnknownRuleError,
    get_rule,
    load_registry,
    rule_by_id,
)

__all__ = [
    "HistoryEntry",
    "RegistryError",
    "Rule",
    "SourceKind",
    "UnknownRuleError",
    "get_rule",
    "load_registry",
    "rule_by_id",
]
