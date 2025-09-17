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
from textual.containers import Container

from blockether_peekle.widgets import TextAreaAutocomplete
from blockether_peekle.widgets.text_area_autocomplete.autocomplete_config import CompletionType
from blockether_peekle.utils import format_value


class PeekleRepl(Container):
    DEFAULT_CSS = """
    RichLog {
        overflow-y: auto !important;
        height: auto;
        max-height: 95%;
    }

    TextAreaAutocomplete > TextArea {
        height: auto;
    }
    """

    _data: reactive[Any] = reactive(None)
    _locals: reactive[Dict[str, Any]] = reactive({})

    def on_mount(self) -> None:
        if self._text_area_widget:
            self._setup_builtin_completions()

            if self._text_area_widget._text_area:
                self._text_area_widget._text_area.focus()

    def _setup_builtin_completions(self) -> None:
        """Set up Python REPL-specific completions."""
        if not self._text_area_widget:
            return
        
        self._locals.update({
            "print": self.query_one(RichLog).write,
        })

        completions: Dict[str, str] = {}

        # Add locals
        for name, obj in self._locals.items():
            if not name.startswith("_"):
                if isinstance(obj, type):
                    completions[name] = CompletionType.CLASS
                elif callable(obj):
                    completions[name] = CompletionType.FUNCTION
                else:
                    completions[name] = CompletionType.VARIABLE

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
        self._text_area_widget.upsert_completions(completions)

    def _update_locals_completions(self) -> None:
        completions: Dict[str, str] = {}

        # Add locals
        for name, obj in self._locals.items():
            if not name.startswith("_"):
                if isinstance(obj, type):
                    completions[name] = CompletionType.CLASS
                elif callable(obj):
                    completions[name] = CompletionType.FUNCTION
                else:
                    completions[name] = CompletionType.VARIABLE
        
        self._text_area_widget.upsert_completions(completions)

    def execute_query(self, query: str) -> Any:
        """Execute a Python expression or statement as a query on the data."""
        try:
            app = self.app
            assert isinstance(app, PeekleApp)

            # Try to parse the query
            try:
                parsed = ast.parse(query, mode="single")

                # Check if it's an import statement
                if isinstance(parsed.body[0], (ast.Import, ast.ImportFrom)):
                    exec(query, self._locals, self._locals)
                    self.query_one(RichLog).write(f"[green]✓[/green] {query}")
                    self._update_locals_completions()
                    return None

                # Check if it's an assignment
                elif isinstance(parsed.body[0], ast.Assign):
                    exec(query, self._locals, self._locals)
                    target = parsed.body[0].targets[0]
                    if isinstance(target, ast.Name):
                        var_name = target.id
                    else:
                        var_name = str(target)
                    result = self._locals.get(var_name)
                    self.query_one(RichLog).write(
                        f"[green]✓[/green] {var_name} = {format_value(result)}"
                    )
                    self._update_locals_completions()
                    # Update tree for assignment result
                    # app.run_worker(
                    #     app.query_one(ReplTree).render_tree(query, result),
                    #     exclusive=True,
                    # )
                    return result

                # Check if it's a function/class definition or other statement
                elif isinstance(
                    parsed.body[0],
                    (
                        ast.FunctionDef,
                        ast.ClassDef,
                        ast.For,
                        ast.While,
                        ast.With,
                        ast.If,
                    ),
                ):
                    exec(query, self._locals, self._locals)
                    self.query_one(RichLog).write("[green]✓[/green] Executed")
                    self._update_locals_completions()
                    return None

                # Otherwise try to evaluate as expression
                else:
                    result = eval(query, self._locals, self._locals)
                    # Update tree for expression result
                    # if result is not None:
                    #     app.run_worker(
                    #         app.query_one(ReplTree).render_tree(query, result),
                    #         exclusive=True,
                    #     )
                    return result

            except SyntaxError:
                # If parsing fails, try as expression
                result = eval(query, self._locals, self._locals)
                # Update tree for expression result
                # if result is not None:
                #     app.run_worker(
                #         app.query_one(ReplTree).render_tree(query, result),
                #         exclusive=True,
                #     )
                return result

        except Exception as e:
            self.query_one(RichLog).write(f"[red]Error:[/red] {e}")
            return None

    def watch__data(self, data: Any) -> None:
        """When data changes, update locals and completions."""
        self._locals.update({"x": data})
        self._update_locals_completions()

    @on(TextAreaAutocomplete.Submitted)
    def handle_text_area_submitted(self, message: TextAreaAutocomplete.Submitted) -> None:
        """Handle submitted code from the text area."""
        self.query_one(RichLog).write(f">>> {message.text}")
        result = self.execute_query(message.text)

        if result is None:
            return
        
        if isinstance(result, (str, int, float, bool, type(None), tuple, list, dict, set)):
            tree = RichTree(f"[bold]{type(result).__name__}[/bold]")
            tree.add(format_value(result))
            self.query_one(RichLog).write(tree)

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True)

        self._text_area_widget = TextAreaAutocomplete(
            language="python",
            show_line_numbers=False
        )
        yield self._text_area_widget


class PeekleApp(App):
    ENABLE_COMMAND_PALETTE = False

    _filepath: reactive[Optional[Path]] = reactive(None)
    _data: reactive[Any] = reactive(None)

    def __init__(self, filepath: Optional[Path] = None) -> None:
        self._text_area_widget: Optional[TextAreaAutocomplete] = None
        super().__init__()
        self._filepath = filepath

    def on_mount(self) -> None:
        self.title = "Peekle"
    
        if self._filepath:
            self._load_file(self._filepath)

    def _load_file(self, filepath: Path) -> None:
        """Load a pickle file."""
        try:
            if filepath:
                with open(filepath, "rb") as f:
                    self._data = pickle.load(f)

                    self.notify(f"[green]✓[/green] Loaded: {filepath} [dim]Type: {type(self._data).__name__}[/dim]")

        except Exception as e:
            self.notify(f"[red]✗[/red] Error loading {filepath} file: {e}")
            self._data = None
            self._filepath = None

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield PeekleRepl().data_bind(PeekleApp._data) 
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
