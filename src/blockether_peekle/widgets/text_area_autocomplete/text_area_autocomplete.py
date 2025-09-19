from __future__ import annotations

from dataclasses import dataclass
from operator import itemgetter
from typing import (
    Callable,
    ClassVar,
    Sequence,
    cast,
)
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.content import Content
from textual.css.query import NoMatches
from textual.geometry import Offset, Region, Spacing
from textual.style import Style
from textual.widget import Widget
from textual.widgets import TextArea, OptionList
from textual.widgets.text_area import Location
from textual.widgets.option_list import Option
from textual.message import Message


@dataclass
class TargetState:
    text: str
    """The content in the target widget."""

    cursor_position: Location
    """The cursor position in the target widget."""


class AutocompleteOption(Option):
    def __init__(
        self,
        prompt: str | Content,
        value: str,
        completion_prefix_length: int,
        id: str | None = None,
        disabled: bool = False,
    ) -> None:
        self.value = value
        self.completion_prefix_length = completion_prefix_length

        super().__init__(prompt, id, disabled)


class AutocompleteOptionHit(AutocompleteOption):
    """A dropdown item which matches the current search string - in other words
    AutoComplete.match has returned a score greater than 0 for this item.
    """


class AutoCompleteList(OptionList):
    pass


class TextAreaAutocomplete(Widget):
    BINDINGS = [
        Binding("escape", "hide", "Hide dropdown", show=False),
    ]

    DEFAULT_CSS = """\
    TextAreaAutocomplete {
        height: auto;
        width: auto;
        max-height: 12;
        display: none;
        background: $surface;
        overlay: screen;

        & AutoCompleteList {
            width: auto;
            height: auto;
            border: none;
            padding: 0;
            margin: 0;
            scrollbar-size-vertical: 1;
            text-wrap: nowrap;
            color: $foreground;
            background: transparent;
        }

        & .autocomplete--highlight-match {
            text-style: bold;
        }

    }
    """

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "autocomplete--highlight-match",
    }

    class Submitted(Message):
        """TextArea submitted message."""

        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def __init__(
        self,
        target: TextArea,
        candidates: Callable[[TargetState], list[AutocompleteOption]] | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """An autocomplete widget.

        Args:
            target: An TextArea instance or a selector string used to query an TextArea instance.
                If a selector is used, remember that widgets are not available until the widget has been mounted (don't
                use the selector in `compose` - use it in `on_mount` instead).
            candidates: The candidates to match on, or a function which returns the candidates to match on.
                If set to None, the candidates will be fetched by directly calling the `get_candidates` method,
                which is what you'll probably want to do if you're subclassing AutoComplete and supplying your
                own custom `get_candidates` method.
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self._target = target

        # Users can supply strings as a convenience for the simplest cases,
        # so let's convert them to AutocompleteOptions.
        self.candidates: (
            list[AutocompleteOption]
            | Callable[[TargetState], list[AutocompleteOption]]
            | None
        )
        """The candidates to match on, or a function which returns the candidates to match on."""
        self.candidates = candidates

        self._target_state = TargetState("", (0, 0))
        """Cached state of the target TextArea."""

    def compose(self) -> ComposeResult:
        option_list = AutoCompleteList()
        option_list.can_focus = False
        yield option_list

    def on_mount(self) -> None:
        # Subscribe to the target widget's reactive attributes.
        self.target.message_signal.subscribe(self, self._listen_to_messages)  # type: ignore
        self._subscribe_to_target()
        self._handle_target_update()
        self.set_interval(0.2, lambda: self.call_after_refresh(self._align_to_target))

    def _submit(self) -> None:
        """Submit the current text area content."""
        if not self.target:
            return

        text = self.target.text
        self.post_message(self.Submitted(text))
        self.target.clear()
        self.action_hide()

    def _listen_to_messages(self, event: events.Event) -> None:
        """Listen to some events of the target widget."""

        if isinstance(event, events.Key) and event.key == "ctrl+enter":
            self._submit()

        try:
            option_list = self.option_list
        except NoMatches:
            # This can happen if the event is an Unmount event
            # during application shutdown.
            return

        if isinstance(event, events.Key) and option_list.option_count:
            displayed = self.display
            highlighted = option_list.highlighted or 0
            if event.key == "down":
                # Check if there's only one item and it matches the search string
                if option_list.option_count == 1:
                    search_string = self.get_search_string(self._get_target_state())
                    first_option = option_list.get_option_at_index(0).prompt
                    text_from_option = (
                        first_option.plain
                        if isinstance(first_option, Text)
                        else first_option
                    )
                    if text_from_option == search_string:
                        # Don't prevent default behavior in this case
                        return

                # If you press `down` while in an TextArea and the autocomplete is currently
                # hidden, then we should show the dropdown.
                event.prevent_default()
                event.stop()
                if displayed:
                    highlighted = (highlighted + 1) % option_list.option_count
                else:
                    self.display = True
                    highlighted = 0

                option_list.highlighted = highlighted

            elif event.key == "up":
                if displayed:
                    event.prevent_default()
                    event.stop()
                    highlighted = (highlighted - 1) % option_list.option_count
                    option_list.highlighted = highlighted
            elif event.key == "enter":
                event.prevent_default()
                event.stop()
                self._complete(option_index=highlighted)
            elif event.key == "tab":
                event.prevent_default()
                event.stop()
                self._complete(option_index=highlighted)
            elif event.key == "escape":
                if displayed:
                    event.prevent_default()
                    event.stop()
                self.action_hide()

        if isinstance(event, TextArea.Changed):
            # We suppress Changed events from the target widget, so that we don't
            # handle change events as a result of performing a completion.
            self._handle_target_update()

    def action_hide(self) -> None:
        self.styles.display = "none"

    def action_show(self) -> None:
        self.styles.display = "block"

    def _complete(self, option_index: int) -> None:
        """Do the completion (i.e. insert the selected item into the target TextArea).

        This is when the user highlights an option in the dropdown and presses tab or enter.
        """
        if not self.display or self.option_list.option_count == 0:
            return

        option_list = self.option_list
        highlighted = option_index
        option = cast(AutocompleteOption, option_list.get_option_at_index(highlighted))
        with self.prevent(TextArea.Changed):
            self.apply_completion(
                option.value, option.completion_prefix_length, self._get_target_state()
            )
        self.post_completion()

    def post_completion(self) -> None:
        """This method is called after a completion is applied. By default, it simply hides the dropdown."""
        self.action_hide()

    def apply_completion(
        self, value: str, completion_prefix_length: int, state: TargetState
    ) -> None:
        """Apply the completion to the target widget.

        This method updates the state of the target widget to the reflect
        the value the user has chosen from the dropdown list.
        """
        target = self.target
        row, col = state.cursor_position
        # Calculate the start position by going back completion_prefix_length characters
        start_col = max(0, col - completion_prefix_length)
        start_location = (row, start_col)

        # Find the end of the current word (in case cursor is in the middle)
        text = state.text
        line = text.split("\n")[row] if "\n" in text else text
        end_col = col

        # Move end_col forward to include any remaining characters of the current word
        while end_col < len(line) and (line[end_col].isalnum() or line[end_col] == "_"):
            end_col += 1

        end_location = (row, end_col)

        # Replace from the start of the prefix to the end of the word
        target.replace(
            value, start_location, end_location, maintain_selection_offset=False
        )

        # We need to rebuild here because we've prevented the Changed events
        # from being sent to the target widget, meaning AutoComplete won't spot
        # intercept that message, and would not trigger a rebuild like it normally
        # does when a Changed event is received.
        new_target_state = self._get_target_state()
        self._rebuild_options(new_target_state)

    @property
    def target(self) -> TextArea:
        """The resolved target widget."""
        if isinstance(self._target, TextArea):
            return self._target
        else:
            target = self.screen.query_one(self._target)
            assert isinstance(target, TextArea)
            return target

    def _subscribe_to_target(self) -> None:
        """Attempt to subscribe to the target widget, if it's available."""
        target = self.target
        self.watch(target, "has_focus", self._handle_focus_change)
        self.watch(target, "selection", self._align_and_rebuild)

    def _align_and_rebuild(self) -> None:
        self._align_to_target()
        self._target_state = self._get_target_state()
        self._rebuild_options(self._target_state)

    def _align_to_target(self) -> None:
        """Align the dropdown to the position of the cursor within
        the target widget, and constrain it to be within the screen."""
        x, y = self.target.cursor_screen_offset
        dropdown = self.option_list
        width, height = dropdown.outer_size

        # Constrain the dropdown within the screen.
        x, y, _width, _height = Region(x - 1, y + 1, width, height).constrain(
            "inside",
            "none",
            Spacing.all(0),
            self.screen.scrollable_content_region,
        )
        self.absolute_offset = Offset(x, y)
        self.refresh(layout=True)

    def _get_target_state(self) -> TargetState:
        """Get the state of the target widget."""
        target = self.target
        return TargetState(
            text=target.text,
            cursor_position=target.cursor_location,
        )

    def _handle_focus_change(self, has_focus: bool) -> None:
        """Called when the focus of the target widget changes."""
        if not has_focus:
            self.action_hide()
        else:
            target_state = self._get_target_state()
            self._rebuild_options(target_state)

    def _handle_target_update(self) -> None:
        """Called when the state (text or cursor position) of the target is updated.

        Here we align the dropdown to the target, determine if it should be visible,
        and rebuild the options in it.
        """
        self._target_state = self._get_target_state()
        search_string = self.get_search_string(self._target_state)

        # Determine visibility after the user makes a change in the
        # target widget (e.g. typing in a character in the TextArea).
        self._rebuild_options(self._target_state)
        self._align_to_target()

        if self.should_show_dropdown(search_string):
            self.action_show()
        else:
            self.action_hide()

    def should_show_dropdown(self, search_string: str) -> bool:
        """
        Determine whether to show or hide the dropdown based on the current state.

        This method can be overridden to customize the visibility behavior.

        Args:
            search_string: The current search string.

        Returns:
            bool: True if the dropdown should be shown, False otherwise.
        """
        option_list = self.option_list
        option_count = option_list.option_count

        if len(search_string) == 0 or option_count == 0:
            return False
        elif option_count == 1:
            first_option = option_list.get_option_at_index(0).prompt
            text_from_option = (
                first_option.plain if isinstance(first_option, Text) else first_option
            )
            return text_from_option != search_string
        else:
            return True

    def _rebuild_options(self, target_state: TargetState) -> None:
        """Rebuild the options in the dropdown.

        Args:
            target_state: The state of the target widget.
        """
        option_list = self.option_list
        option_list.clear_options()
        if self.target.has_focus:
            candidates = self.get_candidates(target_state)
            if candidates:
                option_list.add_options(candidates)
                option_list.highlighted = 0

    def get_search_string(self, target_state: TargetState) -> str:
        """This value will be passed to the match function.

        This could be, for example, the text in the target widget, or a substring of that text.

        Returns:
            The search string that will be used to filter the dropdown options.
        """
        return target_state.text

    def get_candidates(self, target_state: TargetState) -> list[AutocompleteOption]:
        """Get the candidates to match against."""
        candidates = self.candidates
        if isinstance(candidates, Sequence):
            return list(candidates)
        elif candidates is None:
            raise NotImplementedError(
                "You must implement get_candidates in your TextAreaAutocomplete subclass, because candidates is None"
            )
        else:
            # candidates is a callable
            return candidates(target_state)

    @property
    def option_list(self) -> AutoCompleteList:
        return self.query_one(AutoCompleteList)

    @on(OptionList.OptionSelected, "AutoCompleteList")
    def _apply_completion(self, event: OptionList.OptionSelected) -> None:
        # Handles click events on dropdown items.
        self._complete(event.option_index)
