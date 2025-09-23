from __future__ import annotations

import os
from collections.abc import Sequence
from os import DirEntry
from pathlib import Path
from typing import Any, Callable

from textual.cache import LRUCache
from textual.content import Content
from textual.widgets import Input

from .autocomplete import Autocomplete, AutocompleteOption, TargetState


class PathOption(AutocompleteOption):
    def __init__(self, prompt: str | Content, value: str, path: Path) -> None:
        self.value = value
        self.path = path
        super().__init__(prompt, value)


def default_path_input_sort_key(item: PathOption) -> tuple[bool, bool, str]:
    """Sort key function for results within the dropdown.

    Args:
        item: The PathOption to get a sort key for.

    Returns:
        A tuple of (is_dotfile, is_file, lowercase_name) for sorting.
    """
    name = item.path.name
    is_dotfile = name.startswith(".")
    return (not item.path.is_dir(), not is_dotfile, name.lower())


class PathAutocomplete(Autocomplete[Input]):
    def __init__(
        self,
        target: Input,
        path: str | Path = ".",
        *,
        show_dotfiles: bool = True,
        sort_key: Callable[[PathOption], Any] = default_path_input_sort_key,
        folder_prefix: Content = Content("📂"),
        file_prefix: Content = Content("📄"),
        cache_size: int = 100,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            target=target,
            candidates=None,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.path = Path(path) if isinstance(path, str) else path
        self.show_dotfiles = show_dotfiles
        self.sort_key = sort_key
        self.folder_prefix = folder_prefix
        self.file_prefix = file_prefix
        self._directory_cache: LRUCache[str, list[DirEntry[str]]] = LRUCache(cache_size)

    def get_candidates(self, target_state: TargetState) -> Sequence[PathOption]:
        """Get the candidates for the current path segment.

        This is called each time the input changes or the cursor position changes
        """
        row, col = target_state.cursor_position
        current_input = target_state.text[:col]

        # Expand tilde if present
        if current_input.startswith("~"):
            current_input = os.path.expanduser(current_input)

        if "/" in current_input:
            last_slash_index = current_input.rindex("/")
            path_segment = current_input[:last_slash_index] or "/"
            search_prefix = current_input[last_slash_index + 1 :]
            directory = (
                self.path / path_segment
                if path_segment != "/"
                else Path(path_segment)
                if path_segment.startswith("/")
                else self.path / path_segment
            )
        else:
            directory = self.path
            search_prefix = current_input

        # Use the directory path as the cache key
        cache_key = str(directory)
        cached_entries = self._directory_cache.get(cache_key)

        if cached_entries is not None:
            entries = cached_entries
        else:
            try:
                entries = list(os.scandir(directory))
                self._directory_cache[cache_key] = entries
            except OSError:
                return []

        results: list[PathOption] = []
        for entry in entries:
            # Only include the entry name, not the full path
            completion = entry.name
            if not self.show_dotfiles and completion.startswith("."):
                continue
            # Filter based on search prefix
            if search_prefix and not completion.lower().startswith(
                search_prefix.lower()
            ):
                continue
            if entry.is_dir():
                completion += "/"
            results.append(
                PathOption(
                    Content.assemble(
                        self.folder_prefix if entry.is_dir() else self.file_prefix,
                        completion,
                    ),
                    completion,
                    path=Path(entry.path),
                )
            )

        results.sort(key=self.sort_key)
        return results

    def get_search_string(self, target_state: TargetState) -> str:
        """Return only the current path segment for searching in the dropdown."""
        row, col = target_state.cursor_position
        current_input = target_state.text[:col]

        # Expand tilde if present
        if current_input.startswith("~"):
            current_input = os.path.expanduser(current_input)

        if "/" in current_input:
            last_slash_index = current_input.rindex("/")
            search_string = current_input[last_slash_index + 1 :]
            return search_string
        else:
            return current_input

    def apply_completion(self, option: PathOption, state: TargetState) -> None:
        """Apply the completion by replacing only the current path segment."""
        target = self.target
        current_input = state.text
        cursor_position = state.cursor_position
        row, col = cursor_position

        # There's a slash before the cursor, so we only want to replace
        # the text after the last slash with the selected value
        try:
            replace_start_index = current_input.rindex("/", 0, col)
        except ValueError:
            # No slashes, so we do a full replacement
            new_value = option.path.name
            new_cursor_position = len(option.path.name)
        else:
            # Keep everything before and including the slash before the cursor.
            path_prefix = current_input[: replace_start_index + 1]
            new_value = path_prefix + option.path.name
            new_cursor_position = len(path_prefix) + len(option.path.name)

        with self.prevent(Input.Changed):
            target.value = new_value
            target.cursor_position = new_cursor_position

    def post_completion(self) -> None:
        if not self.target.value.endswith("/"):
            self.action_hide()

    def should_show_dropdown(self, search_string: str) -> bool:
        default_behavior = super().should_show_dropdown(search_string)

        return (
            default_behavior
            or (search_string == "" and self.target.value != "")
            and self.option_list.option_count > 1
        )

    def clear_directory_cache(self) -> None:
        """Clear the directory cache. If you know that the contents of the directory have changed,
        you can call this method to invalidate the cache.
        """
        self._directory_cache.clear()
        target_state = self._get_target_state()
        self._rebuild_options(target_state)
