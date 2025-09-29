from collections.abc import Sequence
from typing import Any, Callable, Dict

from textual.content import Content
from textual.widgets import TextArea

from .autocomplete import Autocomplete, AutocompleteOption, TargetState


class TextAreaOption(AutocompleteOption):
    def __init__(
        self,
        prompt: str | Content,
        value: str,
        completion_prefix_length: int,
        meta: Dict[str, Any] | None = None,
        id: str | None = None,
        disabled: bool = False,
    ) -> None:
        self.value = value
        self.completion_prefix_length = completion_prefix_length
        self.meta = meta or {}
        super().__init__(prompt, id, disabled)


class TextAreaAutocomplete(Autocomplete[TextArea]):
    def __init__(
        self,
        target: TextArea,
        candidates: Callable[[TargetState], Sequence[TextAreaOption]] | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            target=target,
            candidates=candidates,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )

    def apply_completion(self, option: TextAreaOption, state: TargetState) -> None:
        """Apply the completion to the target widget.

        This method updates the state of the target widget to the reflect
        the value the user has chosen from the dropdown list.
        """
        target = self.target
        row, col = state.cursor_position
        # Calculate the start position by going back completion_prefix_length characters
        start_col = max(0, col - option.completion_prefix_length)
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
        target.replace(option.value, start_location, end_location, maintain_selection_offset=False)

        # We need to rebuild here because we've prevented the Changed events
        # from being sent to the target widget, meaning AutoComplete won't spot
        # intercept that message, and would not trigger a rebuild like it normally
        # does when a Changed event is received.
        new_target_state = self._get_target_state()
        self._rebuild_options(new_target_state)
