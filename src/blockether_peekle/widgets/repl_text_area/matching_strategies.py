#!/usr/bin/env python3
"""Matching strategies for autocomplete suggestions."""

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from .autocomplete_config import AutocompleteConfig


class MatchingStrategy(ABC):
    """Abstract base class for matching strategies."""

    @abstractmethod
    def match(self, prefix: str, target: str, config: AutocompleteConfig) -> Tuple[bool, int]:
        """
        Check if target matches prefix and return match score.

        Args:
            prefix: The prefix to match against
            target: The target string to check
            config: Autocomplete configuration

        Returns:
            Tuple of (is_match, score) where lower score is better
        """
        pass


class ExactMatchStrategy(MatchingStrategy):
    """Strategy for exact prefix matching."""

    def match(self, prefix: str, target: str, config: AutocompleteConfig) -> Tuple[bool, int]:
        """Check for exact prefix match."""
        if target.lower().startswith(prefix.lower()):
            return (True, 0)
        return (False, config.NO_MATCH_SCORE)


class SubstringMatchStrategy(MatchingStrategy):
    """Strategy for substring matching."""

    def match(self, prefix: str, target: str, config: AutocompleteConfig) -> Tuple[bool, int]:
        """Check for substring match."""
        prefix_lower = prefix.lower()
        target_lower = target.lower()

        position = target_lower.find(prefix_lower)
        if position >= 0:
            # Score based on position (earlier is better)
            return (True, position * 2)
        return (False, config.NO_MATCH_SCORE)


class FuzzyMatchStrategy(MatchingStrategy):
    """Strategy for fuzzy matching using optimized Levenshtein distance."""

    def __init__(self) -> None:
        """Initialize fuzzy matcher with cache."""
        self._distance_cache: Dict[Tuple[str, str], int] = {}

    @lru_cache(maxsize=1000)
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance with caching.

        Uses dynamic programming with space optimization.
        """
        if not s1:
            return len(s2)
        if not s2:
            return len(s1)

        # Ensure s1 is the shorter string for space optimization
        if len(s1) > len(s2):
            s1, s2 = s2, s1

        # Use only two rows instead of full matrix
        previous_row = list(range(len(s2) + 1))
        current_row = [0] * (len(s2) + 1)

        for i, c1 in enumerate(s1, 1):
            current_row[0] = i
            for j, c2 in enumerate(s2, 1):
                # Deletion, insertion, substitution costs
                if c1 == c2:
                    current_row[j] = previous_row[j - 1]
                else:
                    current_row[j] = 1 + min(
                        previous_row[j],  # deletion
                        current_row[j - 1],  # insertion
                        previous_row[j - 1],  # substitution
                    )
            previous_row, current_row = current_row, previous_row

        return previous_row[-1]

    def match(self, prefix: str, target: str, config: AutocompleteConfig) -> Tuple[bool, int]:
        """Check for fuzzy match within threshold."""
        prefix_lower = prefix.lower()
        target_lower = target.lower()

        # First check exact prefix match
        if target_lower.startswith(prefix_lower):
            return (True, 0)

        # Check substring match
        substring_pos = target_lower.find(prefix_lower)
        if substring_pos > 0:
            return (True, substring_pos * 2)

        # Skip if target is much shorter than prefix
        if len(target_lower) < len(prefix_lower) - config.MAX_FUZZY_DISTANCE:
            return (False, config.NO_MATCH_SCORE)

        # Check fuzzy match
        comparison_length = min(len(prefix_lower), len(target_lower))
        distance = self._levenshtein_distance(prefix_lower[:comparison_length], target_lower[:comparison_length])

        # Add penalty for remaining prefix characters
        if len(prefix_lower) > len(target_lower):
            distance += len(prefix_lower) - len(target_lower)

        if distance <= config.MAX_FUZZY_DISTANCE and len(prefix) >= config.MIN_PREFIX_LENGTH:
            score = distance * config.DISTANCE_SCORE_MULTIPLIER
            # Add penalty if first character doesn't match
            if prefix_lower[0] != target_lower[0]:
                score += config.FIRST_CHAR_MISMATCH_PENALTY
            return (True, score)

        return (False, config.NO_MATCH_SCORE)


class CompositeMatchStrategy(MatchingStrategy):
    """Composite strategy that tries multiple strategies in order."""

    def __init__(self, strategies: Optional[List[MatchingStrategy]] = None):
        """Initialize with a list of strategies."""
        if strategies is None:
            strategies = [
                ExactMatchStrategy(),
                SubstringMatchStrategy(),
                FuzzyMatchStrategy(),
            ]
        self._strategies = strategies

    def match(self, prefix: str, target: str, config: AutocompleteConfig) -> Tuple[bool, int]:
        """Try each strategy and return the best match."""
        best_match = False
        best_score = config.NO_MATCH_SCORE

        for strategy in self._strategies:
            is_match, score = strategy.match(prefix, target, config)
            if is_match and score < best_score:
                best_match = True
                best_score = score
                # Short circuit on perfect match
                if score == 0:
                    break

        return (best_match, best_score)
