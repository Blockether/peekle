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
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.highlighter import ReprHighlighter
from rich.tree import Tree as RichTree
from textual import log, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
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

from blockether_peekle.utils import format_value
from blockether_peekle.widgets import TextAreaAutocomplete
from blockether_peekle.widgets.text_area_autocomplete.autocomplete_config import (
    CompletionType,
)


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

        self._locals.update(
            {
                "print": self.query_one(RichLog).write,
            }
        )

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
                # First try to parse as exec mode to handle multi-line statements
                parsed = ast.parse(query, mode="exec")

                # Handle multiple statements
                if len(parsed.body) > 1:
                    # Execute all statements
                    exec(query, self._locals, self._locals)
                    self.query_one(RichLog).write("[green]✓[/green] Executed")
                    self._update_locals_completions()
                    return None

                # Single statement handling
                elif len(parsed.body) == 1:
                    stmt = parsed.body[0]

                    # Check if it's an import statement
                    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                        exec(query, self._locals, self._locals)
                        self.query_one(RichLog).write(f"[green]✓[/green] {query}")
                        self._update_locals_completions()
                        return None

                    # Check if it's an assignment
                    elif isinstance(stmt, ast.Assign):
                        exec(query, self._locals, self._locals)
                        target = stmt.targets[0]
                        if isinstance(target, ast.Name):
                            var_name = target.id
                        else:
                            var_name = str(target)
                        result = self._locals.get(var_name)
                        self.query_one(RichLog).write(f"[green]✓[/green] {var_name} = {format_value(result)}")
                        self._update_locals_completions()
                        return result

                    # Check if it's a function/class definition or other statement
                    elif isinstance(
                        stmt,
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

                    # Check if it's an expression statement
                    elif isinstance(stmt, ast.Expr):
                        # Try to evaluate as expression
                        result = eval(compile(ast.Expression(stmt.value), '<string>', 'eval'), self._locals, self._locals)
                        return result

                    # Otherwise execute as statement
                    else:
                        exec(query, self._locals, self._locals)
                        self.query_one(RichLog).write("[green]✓[/green] Executed")
                        self._update_locals_completions()
                        return None

                # Empty input
                else:
                    return None

            except SyntaxError:
                # If parsing fails, try as expression
                result = eval(query, self._locals, self._locals)
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
        self.query_one(RichLog).write(f">>> {message.text.strip()}")
        result = self.execute_query(message.text)

        if result is None:
            return

        tree = RichTree(f"[bold]{type(result).__name__}[/bold]")
        tree.add(format_value(result))
        self.query_one(RichLog).write(tree)

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True)

        self._text_area_widget = TextAreaAutocomplete(language="python", show_line_numbers=False)
        yield self._text_area_widget


class PeekleTree(Container):
    _filepath: reactive[Optional[Path]] = reactive(None)
    _data: reactive[Any] = reactive(None)

    # Constants for lazy loading
    _MAX_INITIAL_ITEMS = 100  # Show first N items initially

    def __init__(self) -> None:
        self._tree: Tree[Dict[str, Any]] = Tree("No data")
        self._node_cache: Dict[int, Any] = {}  # Cache node data by node id
        super().__init__()

    def watch__data(self, data: Any) -> None:
        """When data changes, update tree."""
        self._node_cache.clear()  # Clear cache when data changes
        self._tree.reset(self._filepath.name if self._filepath else "No data")
        self._tree.root.expand()

        if data is not None:
            # Store root data in cache
            self._node_cache[id(self._tree.root)] = data
            # Build only the first level
            self._build_tree_level(data, self._tree.root)

    def _is_expandable(self, obj: Any) -> bool:
        """Check if an object should be expandable in the tree."""
        return isinstance(obj, (dict, list, tuple, set)) or (hasattr(obj, "__dict__") and not isinstance(obj, type))

    def _get_object_summary(self, obj: Any) -> str:
        """Get a summary representation of an object."""
        if isinstance(obj, dict):
            return f"[dim]({len(obj)} items)[/dim]"
        elif isinstance(obj, (list, tuple, set)):
            return f"[dim]({len(obj)} items)[/dim]"
        elif hasattr(obj, "__dict__"):
            attrs_count = len([k for k in vars(obj).keys() if not k.startswith("_")])
            return f"[dim]({attrs_count} attributes)[/dim]"
        else:
            return format_value(obj)

    def _build_tree_level(self, obj: Any, parent_node: TreeNode, start_index: int = 0) -> None:
        """Build only one level of the tree (for lazy loading)."""
        if isinstance(obj, dict):
            items = list(obj.items())[start_index : start_index + self._MAX_INITIAL_ITEMS]
            for key, value in items:
                key_str = f"[bold cyan]{repr(key)}[/bold cyan]"
                value_type = f"[bold magenta]{type(value).__name__}[/bold magenta]"

                if self._is_expandable(value):
                    # Create expandable node without children
                    label = f"{key_str}: {value_type} {self._get_object_summary(value)}"
                    node = parent_node.add(
                        label,
                        data={"value": value, "loaded": False},
                        expand=False,
                        allow_expand=True,
                    )
                    # Cache the value for later expansion
                    self._node_cache[id(node)] = value
                else:
                    value_str = format_value(value)
                    parent_node.add_leaf(f"{key_str}: {value_str}")

            if len(obj) > start_index + self._MAX_INITIAL_ITEMS:
                remaining = len(obj) - start_index - self._MAX_INITIAL_ITEMS
                node = parent_node.add(
                    f"[bold yellow]... load {min(remaining, self._MAX_INITIAL_ITEMS)} more items (of {remaining} total)[/bold yellow]",
                    data={
                        "more_items": True,
                        "parent_obj": obj,
                        "next_index": start_index + self._MAX_INITIAL_ITEMS,
                        "obj_type": "dict",
                    },
                    expand=False,
                    allow_expand=True,
                )

        elif isinstance(obj, (list, tuple, set)):
            items = list(obj)[start_index : start_index + self._MAX_INITIAL_ITEMS]
            for i, item in enumerate(items, start=start_index):
                item_type = f"[bold magenta]{type(item).__name__}[/bold magenta]"

                if self._is_expandable(item):
                    label = f"[{i}]: {item_type} {self._get_object_summary(item)}"
                    node = parent_node.add(
                        label,
                        data={"value": item, "loaded": False},
                        expand=False,
                        allow_expand=True,
                    )
                    self._node_cache[id(node)] = item
                else:
                    value_str = format_value(item)
                    parent_node.add_leaf(f"[{i}]: {value_str}")

            if len(obj) > start_index + self._MAX_INITIAL_ITEMS:
                remaining = len(obj) - start_index - self._MAX_INITIAL_ITEMS
                node = parent_node.add(
                    f"[bold yellow]... load {min(remaining, self._MAX_INITIAL_ITEMS)} more items (of {remaining} total)[/bold yellow]",
                    data={
                        "more_items": True,
                        "parent_obj": obj,
                        "next_index": start_index + self._MAX_INITIAL_ITEMS,
                        "obj_type": "list",
                    },
                    expand=False,
                    allow_expand=True,
                )

        elif hasattr(obj, "__dict__"):
            # For objects with attributes
            if hasattr(obj, "model_dump"):
                try:
                    attrs = obj.model_dump()
                except Exception:
                    attrs = {k: v for k, v in vars(obj).items() if not k.startswith("_")}
            else:
                attrs = {k: v for k, v in vars(obj).items() if not k.startswith("_")}

            items = list(attrs.items())[start_index : start_index + self._MAX_INITIAL_ITEMS]
            for key, value in items:
                key_str = f"[bold magenta]{key}[/bold magenta]"
                value_type = f"[bold cyan]{type(value).__name__}[/bold cyan]"

                if self._is_expandable(value):
                    label = f"{key_str}: {value_type} {self._get_object_summary(value)}"
                    node = parent_node.add(
                        label,
                        data={"value": value, "loaded": False},
                        expand=False,
                        allow_expand=True,
                    )
                    self._node_cache[id(node)] = value
                else:
                    value_str = format_value(value)
                    parent_node.add_leaf(f"{key_str}: {value_str}")

            if len(attrs) > start_index + self._MAX_INITIAL_ITEMS:
                remaining = len(attrs) - start_index - self._MAX_INITIAL_ITEMS
                node = parent_node.add(
                    f"[bold yellow]... load {min(remaining, self._MAX_INITIAL_ITEMS)} more attributes (of {remaining} total)[/bold yellow]",
                    data={
                        "more_items": True,
                        "parent_obj": attrs,
                        "next_index": start_index + self._MAX_INITIAL_ITEMS,
                        "obj_type": "attrs",
                    },
                    expand=False,
                    allow_expand=True,
                )
        else:
            parent_node.add_leaf(format_value(obj))

    @on(Tree.NodeExpanded)
    def handle_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Load children when a node is expanded."""
        node = event.node

        # Check if node has data
        if node.data and isinstance(node.data, dict):
            # Handle "more items" nodes
            if node.data.get("more_items"):
                parent_obj = node.data["parent_obj"]
                next_index = node.data["next_index"]

                # Remove this node and add the next batch of items to parent
                parent = node.parent
                if parent:
                    # Remove the "more items" node
                    node.remove()
                    # Add the next batch of items
                    self._build_tree_level(parent_obj, parent, start_index=next_index)

            # Handle regular expandable nodes
            elif not node.data.get("loaded", True):
                # Get cached value
                value = self._node_cache.get(id(node))
                if value is not None:
                    # Clear existing children (in case of placeholder)
                    node.remove_children()
                    # Build children for this node
                    self._build_tree_level(value, node)
                    # Mark as loaded
                    node.data["loaded"] = True

    def compose(self) -> ComposeResult:
        yield self._tree


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
        yield PeekleTree().data_bind(PeekleApp._data, PeekleApp._filepath)
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
