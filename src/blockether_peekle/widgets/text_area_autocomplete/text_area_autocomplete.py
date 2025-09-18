#!/usr/bin/env python3
"""Generic TextArea widget with autocomplete functionality."""

import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Tuple

from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.css.query import NoMatches
from textual.geometry import Offset, Size
from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import OptionList, TextArea
from textual.widgets.option_list import Option

from .autocomplete_config import AutocompleteConfig, CompletionColors
from .autocomplete_core import AutocompleteCore


@dataclass
class CompletionContext:
    """Context information for completion."""

    cursor_row: int
    cursor_col: int
    word_start: int
    word_end: int
    prefix: str
    full_line: str
    previous_token: Optional[str] = None


class DebouncedWorker:
    """Thread-safe debounced timer management."""

    def __init__(self, delay: float):
        """Initialize with debounce delay."""
        self._delay = delay
        self._lock = Lock()
        self._current_timer: Optional[Timer] = None
        self._latest_time: float = 0.0

    def schedule(self, container: Container, callback: Callable, *args: Any) -> None:
        """Schedule a debounced callback."""
        with self._lock:
            current_time = time.time()
            self._latest_time = current_time

            # Cancel previous timer
            if self._current_timer:
                self._current_timer.stop()

            # Schedule new callback
            self._current_timer = container.set_timer(
                self._delay,
                lambda: self._execute_if_latest(current_time, callback, *args),
            )

    def _execute_if_latest(self, scheduled_time: float, callback: Callable, *args: Any) -> None:
        """Execute callback only if no newer one was scheduled."""
        with self._lock:
            if scheduled_time == self._latest_time:
                callback(*args)
                self._current_timer = None

    def cancel(self) -> None:
        """Cancel any pending timer."""
        with self._lock:
            if self._current_timer:
                self._current_timer.stop()
            self._current_timer = None


class PositionCalculator:
    """Calculate optimal position for autocomplete popup."""

    def __init__(self, config: AutocompleteConfig):
        """Initialize with configuration."""
        self._config = config

    def calculate_position(
        self,
        context: CompletionContext,
        container_size: Size,
        suggestion_count: int,
        char_width: int = 1,
        char_height: int = 1,
    ) -> Tuple[Offset, Size]:
        """
        Calculate optimal position and size for popup.

        Returns:
            Tuple of (offset, size) for the popup
        """
        # Calculate initial position
        x = min(context.cursor_col * char_width, container_size.width - 30)
        y = (context.cursor_row + 1) * char_height

        # Calculate popup dimensions
        popup_height = min(self._config.OPTION_LIST_MAX_HEIGHT, suggestion_count)
        popup_width = max(self._config.OPTION_LIST_MIN_WIDTH, 30)

        # Adjust if popup would go off screen
        if y + popup_height > container_size.height - 2:
            # Show above cursor instead
            y = max(0, context.cursor_row * char_height - popup_height - 1)

        if x + popup_width > container_size.width:
            # Shift left to fit
            x = max(0, container_size.width - popup_width - 2)

        return (Offset(x, y), Size(popup_width, popup_height))


class TextAreaAutocomplete(Container):
    """Generic TextArea with autocomplete functionality."""

    DEFAULT_CSS = """
    TextAreaAutocomplete {
        height: 100%;
        width: 100%;
    }

    TextAreaAutocomplete > TextArea {
        padding: 0;
        width: 100%;
        height: 100%;
    }

    TextAreaAutocomplete > .autocomplete-list {
        layer: above;
        background: $surface;
        border: solid $primary;
        max-height: 10;
        width: auto;
        min-width: 20;
        display: none;
        scrollbar-size: 1 1;
    }

    TextAreaAutocomplete > .autocomplete-list.visible {
        display: block;
    }

    TextAreaAutocomplete > .autocomplete-list:focus {
        border: solid $accent;
    }
    """

    class CompletionSelected(Message):
        """Message sent when a completion is selected."""

        def __init__(self, completion: str, completion_type: str, context: Optional[str] = None):
            """Initialize with completion details."""
            super().__init__()
            self.completion = completion
            self.completion_type = completion_type
            self.context = context

    class Submitted(Message):
        """TextArea submitted message."""

        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    # Reactive properties for state management
    _showing_completions = reactive(False)
    _just_completed = reactive(False)

    def __init__(
        self,
        *args: Any,
        config: Optional[AutocompleteConfig] = None,
        completion_provider: Optional[Callable[[str, Optional[str]], List[Tuple[str, str]]]] = None,
        language: str = "python",
        show_line_numbers: bool = False,
        **kwargs: Any,
    ):
        """Initialize with optional configuration and completion provider.

        Args:
            config: Configuration for autocomplete behavior
            completion_provider: Callback that returns [(text, type)] given (prefix, context)
            language: Language for syntax highlighting
            show_line_numbers: Whether to show line numbers in the text area
        """
        super().__init__(*args, **kwargs)
        self._config = config or AutocompleteConfig()
        self._autocomplete_core = AutocompleteCore(self._config, completion_provider)
        self._position_calculator = PositionCalculator(self._config)
        self._debounced_worker = DebouncedWorker(self._config.DEBOUNCE_TIME)
        self._current_context: Optional[CompletionContext] = None
        self._text_area: Optional[TextArea] = None
        self._option_list: Optional[OptionList] = None
        self._language = language
        self._show_line_numbers = show_line_numbers
        self._completion_types: Dict[str, str] = {}  # Track types for completions

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        self._text_area = TextArea.code_editor(
            language=self._language,
            compact=True,
            show_line_numbers=self._show_line_numbers,
            tab_behavior="focus",
        )
        self._option_list = OptionList(classes="autocomplete-list", compact=True)
        yield self._text_area
        yield self._option_list

    def on_mount(self) -> None:
        """Set up bindings when mounted."""
        if not self._option_list:
            return

        self._option_list.add_class("hidden")

    def _extract_completion_context(self, text_area: TextArea) -> Optional[CompletionContext]:
        """Extract context for completion from text area."""
        cursor_row, cursor_col = text_area.cursor_location
        document = text_area.document

        if cursor_row >= len(document.lines):
            return None

        current_line = document.lines[cursor_row]

        # Find word boundaries
        word_start = cursor_col
        word_end = cursor_col

        # Check for word before cursor
        if cursor_col > 0 and self._is_word_char(current_line[cursor_col - 1]):
            # Find start of word
            word_start = cursor_col - 1
            while word_start > 0 and self._is_word_char(current_line[word_start - 1]):
                word_start -= 1

            # Find end of word
            while word_end < len(current_line) and self._is_word_char(current_line[word_end]):
                word_end += 1

            prefix = current_line[word_start:cursor_col]

            if len(prefix) >= self._config.MIN_PREFIX_LENGTH:
                # Extract previous token for context
                before_word = current_line[:word_start].strip()
                previous_token = before_word.split()[-1] if before_word else None

                return CompletionContext(
                    cursor_row=cursor_row,
                    cursor_col=cursor_col,
                    word_start=word_start,
                    word_end=word_end,
                    prefix=prefix,
                    full_line=current_line,
                    previous_token=previous_token,
                )

        return None

    @staticmethod
    def _is_word_char(char: str) -> bool:
        """Check if character is part of a word."""
        return char.isalnum() or char == "_"

    def _check_autocomplete(self) -> None:
        """Check if autocomplete should be triggered."""
        if self._just_completed:
            self._just_completed = False
            return

        if not self._text_area:
            return

        context = self._extract_completion_context(self._text_area)

        if context:
            self._current_context = context
            self._show_completions(context)
        else:
            self._hide_completions()

    @on(TextArea.Changed)
    def handle_text_changed(self, event: TextArea.Changed) -> None:
        """Handle text changes with debouncing."""
        event.stop()
        self._debounced_worker.schedule(self, self._check_autocomplete)

    @on(events.Key)
    def handle_cursor_movement(self, event: events.Key) -> None:
        """Handle cursor movement keys."""
        if event.key in ["left", "right"] and not self._showing_completions:
            self.call_after_refresh(self._check_autocomplete)

    def _show_completions(self, context: CompletionContext) -> None:
        """Show completion options."""
        if not self._option_list:
            return

        # Get completions with context
        completions = self._autocomplete_core.get_completions(
            prefix=context.prefix,
            context=context.previous_token,
            full_text=context.full_line,
            cursor_position=context.cursor_col,
        )

        if not completions:
            self._hide_completions()
            return

        # Clear and populate option list
        self._option_list.clear_options()

        for completion_text, completion_type in completions:
            # Format option with color and type
            color = CompletionColors.get_color(completion_type)
            match_indicator = ""
            if not completion_text.lower().startswith(context.prefix.lower()):
                match_indicator = "~"

            formatted = (
                f"{match_indicator}{completion_text:<{self._config.OPTION_TEXT_WIDTH}} " f"{color}{completion_type}[/]"
            )
            self._option_list.add_option(Option(formatted, id=completion_text))
            # Store type for later retrieval
            self._completion_types[completion_text] = completion_type

        # Calculate and set position
        try:
            offset, size = self._position_calculator.calculate_position(context, self.size, len(completions))

            self._option_list.styles.offset = offset
            self._option_list.styles.width = size.width
            self._option_list.styles.height = size.height

            self._option_list.remove_class("hidden")
            self._option_list.add_class("visible")
            self._showing_completions = True

            # Highlight first item
            if self._option_list.option_count > 0:
                self._option_list.highlighted = 0

        except (AttributeError, ValueError):
            self._hide_completions()

    def _hide_completions(self) -> None:
        """Hide the completion list."""
        if self._option_list:
            self._option_list.remove_class("visible")
            self._option_list.add_class("hidden")
        self._showing_completions = False
        self._current_context = None

    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        if event.key == "ctrl+enter":
            self._submit()

        if not self._showing_completions or not self._option_list:
            return

        if self._option_list.option_count == 0:
            return

        handled = True

        if event.key == "down":
            self._option_list.action_cursor_down()
        elif event.key == "up":
            self._option_list.action_cursor_up()
        elif event.key == "tab":
            self._accept_completion()
        elif event.key == "escape":
            self._hide_completions()
        else:
            handled = False

        if handled:
            event.stop()
            event.prevent_default()

    @on(OptionList.OptionSelected)
    def handle_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle selection of a completion option."""
        if not self._showing_completions:
            return

        event.stop()
        if event.option.id:
            self._insert_completion(str(event.option.id))

    def _submit(self) -> None:
        """Submit the current text area content."""
        if not self._text_area:
            return

        text = self._text_area.text
        self.post_message(self.Submitted(text))
        self._text_area.clear()
        self._hide_completions()

    def _accept_completion(self) -> None:
        """Accept the currently highlighted completion."""
        if not self._option_list or self._option_list.highlighted is None:
            return

        option = self._option_list.get_option_at_index(self._option_list.highlighted)
        if option and option.id:
            self._insert_completion(str(option.id))

    def _insert_completion(self, completion: str) -> None:
        """Insert the selected completion into the text area."""
        if not self._current_context or not self._text_area:
            return

        context = self._current_context

        # Build new line with completion
        current_line = self._text_area.document.lines[context.cursor_row]
        new_line = current_line[: context.word_start] + completion + current_line[context.word_end :]

        # Replace the line
        self._text_area.replace(new_line, (context.cursor_row, 0), (context.cursor_row, len(current_line)))

        # Move cursor to end of completion
        new_cursor_col = context.word_start + len(completion)
        self._text_area.cursor_location = (context.cursor_row, new_cursor_col)

        # Record selection for learning
        self._autocomplete_core.record_selection(completion, context.previous_token)

        # Post completion message
        completion_type = self._get_completion_type(completion)
        self.post_message(self.CompletionSelected(completion, completion_type, context.previous_token))

        self._just_completed = True
        self._hide_completions()

    def _get_completion_type(self, completion: str) -> str:
        """Get the type of a completion."""
        return self._completion_types.get(completion, "custom")

    @on(events.Blur)
    def handle_blur(self, event: events.Blur) -> None:
        """Hide completions when text area loses focus."""
        if event._sender == self._text_area:
            self._hide_completions()

    def action_complete(self) -> None:
        """Action to trigger completion."""
        if self._showing_completions:
            self._accept_completion()
        else:
            # Force autocomplete check
            self._check_autocomplete()

    def set_completion_provider(
        self, provider: Callable[[str, Optional[str]], List[Tuple[str, str]]]
    ) -> None:
        """Set or update the completion provider callback.

        Args:
            provider: Callback that returns [(text, type)] given (prefix, context)
        """
        self._autocomplete_core.set_completion_provider(provider)

    @property
    def text_area(self) -> Optional[TextArea]:
        """Get the underlying TextArea widget."""
        return self._text_area

    @property
    def autocomplete_core(self) -> AutocompleteCore:
        """Get the autocomplete core for direct access if needed."""
        return self._autocomplete_core
