#!/usr/bin/env python3
"""Configuration management for autocomplete system."""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AutocompleteConfig:
    """Configuration for autocomplete behavior."""

    # Fuzzy matching configuration
    MAX_FUZZY_DISTANCE: int = 2
    NO_MATCH_SCORE: int = 999999
    DISTANCE_SCORE_MULTIPLIER: int = 10
    FIRST_CHAR_MISMATCH_PENALTY: int = 5

    # Display configuration
    MIN_PREFIX_LENGTH: int = 1
    MAX_SUGGESTIONS: int = 20
    DEBOUNCE_TIME: float = 0.1

    # Cache configuration
    CACHE_SIZE: int = 100

    # UI configuration
    OPTION_LIST_MAX_HEIGHT: int = 10
    OPTION_LIST_MIN_WIDTH: int = 20
    OPTION_TEXT_WIDTH: int = 20

    # Learning configuration
    SELECTION_WEIGHT_BOOST: float = 0.5
    MAX_SELECTION_HISTORY: int = 100


@dataclass(frozen=True)
class CompletionType:
    """Type definitions for completions."""

    KEYWORD: str = "keyword"
    CLASS: str = "class"
    FUNCTION: str = "func"
    VARIABLE: str = "var"
    CUSTOM: str = "custom"
    MODULE: str = "module"
    PARAMETER: str = "param"


@dataclass(frozen=True)
class CompletionColors:
    """Color scheme for completion types."""

    KEYWORD: str = "[bold magenta]"
    CLASS: str = "[bold cyan]"
    FUNCTION: str = "[bold yellow]"
    VARIABLE: str = "[bold green]"
    CUSTOM: str = "[bold white]"
    MODULE: str = "[bold blue]"
    PARAMETER: str = "[dim white]"
    DEFAULT: str = "[dim]"

    @classmethod
    def get_color(cls, completion_type: str) -> str:
        """Get color for a completion type."""
        type_map: Dict[str, str] = {
            CompletionType.KEYWORD: cls.KEYWORD,
            CompletionType.CLASS: cls.CLASS,
            CompletionType.FUNCTION: cls.FUNCTION,
            CompletionType.VARIABLE: cls.VARIABLE,
            CompletionType.CUSTOM: cls.CUSTOM,
            CompletionType.MODULE: cls.MODULE,
            CompletionType.PARAMETER: cls.PARAMETER,
        }
        return type_map.get(completion_type, cls.DEFAULT)
