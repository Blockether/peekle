#!/usr/bin/env python3
"""
A powerful REPL for exploring pickle files with rich formatting,
query capabilities, intellisense, and interactive Python expressions.
"""

import argparse
import ast
import builtins
import keyword
import os
import pickle
import re
import sys
import traceback
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, Optional, List

from rich.highlighter import ReprHighlighter
from rich.tree import Tree as RichTree
from textual import on, log
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from blockether_peekle.widgets import TextAreaAutocomplete
from blockether_peekle.widgets.text_area_autocomplete.autocomplete_config import CompletionType


class PeekleApp(App):
    ENABLE_COMMAND_PALETTE = False

    filepath: reactive[Optional[Path]] = reactive(None)
    data: reactive[Any] = reactive(None) 

    def __init__(self, filepath: Optional[Path] = None) -> None:
        self._text_area_widget: Optional[TextAreaAutocomplete] = None
        super().__init__()
        self.filepath = filepath

    def on_mount(self) -> None:
        self.title = "Peekle"
        self.mutate_reactive(PeekleApp.filepath)

        if self._text_area_widget:
            self._setup_python_completions()

    def _setup_python_completions(self) -> None:
        """Set up Python REPL-specific completions."""
        if not self._text_area_widget:
            return

        completions: Dict[str, str] = {}

        # Add Python keywords
        for kw in keyword.kwlist:
            completions[kw] = CompletionType.KEYWORD

        # Add Python builtins
        for name in dir(builtins):
            if not name.startswith("_"):
                try:
                    obj = getattr(builtins, name)
                    if isinstance(obj, type):
                        completions[name] = CompletionType.CLASS
                    elif callable(obj):
                        completions[name] = CompletionType.FUNCTION
                    else:
                        completions[name] = CompletionType.VARIABLE
                except (AttributeError, TypeError):
                    completions[name] = CompletionType.VARIABLE

        # Set all completions at once
        self._text_area_widget.set_completions(completions)

    def watch_filepath(self, old_filepath: Optional[Path], new_filepath: Optional[Path]) -> None:
        """Load a pickle file."""
        try:
            if new_filepath:
                with open(new_filepath, "rb") as f:
                    self.data = pickle.load(f)
                    self.mutate_reactive(PeekleApp.data)
        except Exception:
            self.data = None
            self._filepath = None

    def watch_data(self, old_data: Any, new_data: Any) -> None:
        """React to data changes."""
        if self._text_area_widget:
            # TODO: Add 'data' variable to completions
            self._text_area_widget.add_completions(["data"], CompletionType.VARIABLE)

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        self._text_area_widget = TextAreaAutocomplete(
            language="python",
            show_line_numbers=False
        )
        yield self._text_area_widget
        yield Footer(show_command_palette=False)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="A powerful REPL for exploring pickle files with rich formatting, query capabilities, intellisense, and interactive Python expressions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Start REPL without loading a file
  %(prog)s data.pkl           # Open a pickle file
  %(prog)s data.pkl --debug   # Enable debug mode

Usage:
  uv run blockether_peekle data.pkl

In the REPL:
  - Your data is available as 'x'
  - Press Tab for autocomplete
        """,
    )

    parser.add_argument("file", nargs="?", help="Pickle file to load")

    parser.add_argument("--debug", action="store_true", help="Enable debug mode with full tracebacks")

    args = parser.parse_args()

    try:
        if args.file:
            filepath = Path(args.file)
            if not filepath.exists():
                print(f"Error: File '{filepath}' not found")
                sys.exit(1)
            viewer = PeekleApp(filepath)
        else:
            viewer = PeekleApp()

        viewer.run()

    except Exception as e:
        print(f"Fatal error: {e}")
        if args.debug:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
