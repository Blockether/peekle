#!/usr/bin/env python3
"""Generic autocomplete logic with improved architecture."""

from collections import defaultdict, deque
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from .autocomplete_config import AutocompleteConfig, CompletionType
from .matching_strategies import CompositeMatchStrategy


class SelectionHistory:
    """Tracks user selections to improve ranking."""

    def __init__(self, max_history: int = 100):
        """Initialize selection history."""
        self._max_history = max_history
        self._selection_counts: Dict[str, int] = defaultdict(int)
        self._recent_selections: deque = deque(maxlen=max_history)
        self._context_selections: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record_selection(self, item: str, context: Optional[str] = None) -> None:
        """Record a user selection."""
        self._selection_counts[item] += 1
        self._recent_selections.append(item)

        if context:
            self._context_selections[context][item] += 1

    def get_selection_score(self, item: str, context: Optional[str] = None) -> float:
        """Get selection-based score boost for an item."""
        base_score = self._selection_counts.get(item, 0) * 0.1

        # Boost for recent selections
        recency_boost = 0.0
        for i, recent_item in enumerate(reversed(self._recent_selections)):
            if recent_item == item:
                recency_boost += (1.0 / (i + 1)) * 0.05
                break

        # Context-specific boost
        context_boost = 0.0
        if context:
            context_boost = self._context_selections[context].get(item, 0) * 0.2

        return base_score + recency_boost + context_boost

    def clear(self) -> None:
        """Clear selection history."""
        self._selection_counts.clear()
        self._recent_selections.clear()
        self._context_selections.clear()


class CompletionCache:
    """LRU cache for completion results."""

    def __init__(self, size: int = 100):
        """Initialize cache."""
        self._size = size
        self._cache: Dict[str, List[Tuple[str, str]]] = {}
        self._order: deque = deque()

    def get(self, key: str) -> Optional[List[Tuple[str, str]]]:
        """Get cached result."""
        if key in self._cache:
            # Move to end (most recently used)
            self._order.remove(key)
            self._order.append(key)
            return self._cache[key]
        return None

    def put(self, key: str, value: List[Tuple[str, str]]) -> None:
        """Store result in cache."""
        if key in self._cache:
            self._order.remove(key)
        elif len(self._order) >= self._size:
            # Remove least recently used
            oldest = self._order.popleft()
            del self._cache[oldest]

        self._cache[key] = value
        self._order.append(key)

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._order.clear()


class AutocompleteCore:
    """Generic autocomplete logic provider."""

    def __init__(self, config: Optional[AutocompleteConfig] = None):
        """Initialize with configuration."""
        self._config = config or AutocompleteConfig()
        self._completions: Dict[str, str] = {}  # completion_text -> completion_type
        self._cache = CompletionCache(self._config.CACHE_SIZE)
        self._selection_history = SelectionHistory(self._config.MAX_SELECTION_HISTORY)
        self._matching_strategy = CompositeMatchStrategy()

    def upsert_completions(
        self,
        completions: Dict[str, str] | List[str],
        completion_type: str = CompletionType.CUSTOM,
        replace_all: bool = False,
    ) -> None:
        """Update or insert completions.

        Args:
            completions: Either a dict mapping text to type, or a list of texts
            completion_type: Type for all completions (used only with list input)
            replace_all: If True, replaces all existing completions; if False, updates/adds
        """
        if replace_all:
            self._completions.clear()

        if isinstance(completions, dict):
            self._completions.update(completions)
        else:
            for comp in completions:
                self._completions[comp] = completion_type

        self._cache.clear()

    def clear_completions(self) -> None:
        """Clear all completions."""
        self._completions.clear()
        self._cache.clear()

    def record_selection(self, item: str, context: Optional[str] = None) -> None:
        """Record a user selection for learning."""
        self._selection_history.record_selection(item, context)
        # Clear cache to update rankings
        self._cache.clear()

    @lru_cache(maxsize=100)
    def _extract_context(self, text: str, cursor_position: int) -> Optional[str]:
        """Extract context from text around cursor position."""
        if not text or cursor_position < 0:
            return None

        # Simple context: previous token before cursor
        before_cursor = text[:cursor_position]
        tokens = before_cursor.split()

        if len(tokens) >= 2:
            # Return previous token as context
            return tokens[-2]
        return None

    def get_completions(
        self,
        prefix: str,
        context: Optional[str] = None,
        full_text: Optional[str] = None,
        cursor_position: Optional[int] = None,
    ) -> List[Tuple[str, str]]:
        """
        Get completion suggestions with improved context awareness.

        Args:
            prefix: The prefix to match
            context: Optional context string
            full_text: Full text content for context extraction
            cursor_position: Cursor position in full text

        Returns:
            List of (completion_text, completion_type) tuples
        """
        if not prefix:
            return []

        # Try to extract context if not provided
        if context is None and full_text and cursor_position is not None:
            context = self._extract_context(full_text, cursor_position)

        # Create cache key including context
        cache_key = f"{prefix}:{context}" if context else prefix

        # Check cache
        cached_result = self._cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Collect all candidates
        all_candidates = self._collect_candidates()

        # Score and filter matches
        scored_suggestions = self._score_candidates(prefix, all_candidates, context)

        # Sort and deduplicate
        unique_suggestions = self._deduplicate_suggestions(scored_suggestions)

        # Cache and return
        self._cache.put(cache_key, unique_suggestions)
        return unique_suggestions

    def _collect_candidates(self) -> List[Tuple[str, str]]:
        """Collect all completion candidates."""
        return [(text, comp_type) for text, comp_type in self._completions.items()]

    def _score_candidates(
        self, prefix: str, candidates: List[Tuple[str, str]], context: Optional[str]
    ) -> List[Tuple[float, str, str]]:
        """Score candidates based on matching and history."""
        scored = []

        for candidate, comp_type in candidates:
            is_match, base_score = self._matching_strategy.match(prefix, candidate, self._config)

            if is_match:
                # Apply selection history boost
                history_boost = self._selection_history.get_selection_score(candidate, context)
                final_score = base_score - (history_boost * self._config.SELECTION_WEIGHT_BOOST)

                # Type-based prioritization can be customized here if needed

                scored.append((final_score, candidate, comp_type))

        return scored

    def _deduplicate_suggestions(self, scored_suggestions: List[Tuple[float, str, str]]) -> List[Tuple[str, str]]:
        """Sort and deduplicate suggestions."""
        # Sort by score (lower is better), then alphabetically
        scored_suggestions.sort(key=lambda x: (x[0], x[1]))

        seen = set()
        unique = []
        for _, name, comp_type in scored_suggestions:
            if name not in seen:
                seen.add(name)
                unique.append((name, comp_type))
                if len(unique) >= self._config.MAX_SUGGESTIONS:
                    break

        return unique

    @property
    def config(self) -> AutocompleteConfig:
        """Get configuration (read-only)."""
        return self._config
