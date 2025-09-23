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
from typing import Any, Dict, List, Optional, Tuple

from attr import dataclass
from jedi import Interpreter
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
    TextArea,
    Tree,
    Rule,
)
from textual.widgets.tree import TreeNode

from blockether_peekle.utils import format_value
from blockether_peekle.widgets.autocomplete import (
    PathAutocomplete,
    PathOption,
    TargetState,
    TextAreaAutocomplete,
    TextAreaOption,
)


@dataclass
class LoadFileScreenState:
    path: Path
    variable_name: str


class LoadFilePathInput(PathAutocomplete):
    _extensions = [".pkl", ".pickle", ".p"]

    def get_candidates(self, target_state: TargetState) -> list[PathOption]:
        candidates = super().get_candidates(target_state)

        return [
            item
            for item in candidates
            if os.path.isdir(item.path) or item.value.endswith(tuple(self._extensions))
        ]

    def post_completion(self) -> None:
        if not self.target.value.endswith(
            tuple(self._extensions)
        ) or not os.path.isfile(self.target.value):
            return super().post_completion()

        self.post_message(self.Submitted(self.target.value))


class LoadFileScreen(ModalScreen[LoadFileScreenState]):
    DEFAULT_CSS = """
    LoadFileScreen {
        align: center middle;
    }

    #dialog {
        padding-left: 1;
        width: 90%;
        height: auto;
        border: thick $background 60%;
        background: $surface;
    }

    Container {
        height: auto;
    }

    #dialog-path {
        margin-bottom: 1;
    }
    """

    @on(LoadFilePathInput.Submitted)
    def handle_load_file_path_input_submitted(
        self, message: LoadFilePathInput.Submitted
    ) -> None:
        """Handle submitted code from the input."""
        self.query("#varname").focus()

    @on(Input.Submitted)
    def handle_input_submitted(self, message: Input.Submitted) -> None:
        """Handle submitted code from the input."""
        if message.input.id == "varname":
            self.dismiss(
                LoadFileScreenState(
                    path=Path(self.query_one(LoadFilePathInput).target.value),
                    variable_name=message.input.value.strip(),
                )
            )

    def compose(self) -> ComposeResult:
        input_widget = Input(placeholder="~/")

        yield Widget(
            Container(
                Label("Pickle file path"),
                input_widget,
                LoadFilePathInput(target=input_widget),
                id="dialog-path",
            ),
            Container(
                Label("Variable name"),
                Input(placeholder="Variable name", id="varname", value="x"),
                id="dialog-varname",
            ),
            id="dialog",
        )

    def key_escape(self) -> None:
        self.app.pop_screen()


class PeekleRepl(Container):
    DEFAULT_CSS = """
    RichLog {
        overflow-y: auto !important;
        height: auto;
        max-height: 95%;
    }

    TextArea {
        padding: 0 !important;
    }
    """

    class QueryExecuted(Message):
        """Query executed message."""

        def __init__(self, query: str, result: Any) -> None:
            self.query = query
            self.result = result
            super().__init__()

    _locals: reactive[Dict[str, Any]] = reactive({})
    _locals_data_variable: reactive[str] = reactive("x")

    def on_mount(self) -> None:
        if self._text_area_widget:
            self._text_area_widget.focus()

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
                    return None

                # Single statement handling
                elif len(parsed.body) == 1:
                    stmt = parsed.body[0]

                    # Check if it's an import statement
                    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                        exec(query, self._locals, self._locals)
                        self.query_one(RichLog).write(f"[green]✓[/green] {query}")
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
                        self.query_one(RichLog).write(
                            f"[green]✓[/green] {var_name} = {format_value(result)}"
                        )
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
                        return None

                    # Check if it's an expression statement
                    elif isinstance(stmt, ast.Expr):
                        # Try to evaluate as expression
                        result = eval(
                            compile(ast.Expression(stmt.value), "<string>", "eval"),
                            self._locals,
                            self._locals,
                        )
                        return result

                    # Otherwise execute as statement
                    else:
                        exec(query, self._locals, self._locals)
                        self.query_one(RichLog).write("[green]✓[/green] Executed")
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

    def update_locals_data(self, variable_name: str, data: Any) -> None:
        """When data changes, update locals and completions."""
        if data is None:
            return

        self._locals.pop(self._locals_data_variable, None)
        self._locals.update({variable_name: data})

        self._locals_data_variable = variable_name

    @on(TextAreaAutocomplete.Submitted)
    def handle_text_area_submitted(
        self, message: TextAreaAutocomplete.Submitted
    ) -> None:
        """Handle submitted code from the text area."""
        self.query_one(RichLog).write(f">>> {message.text.strip()}")
        result = self.execute_query(message.text)

        if result is None:
            return

        self.post_message(self.QueryExecuted(message.text, result))

        tree = RichTree(f"[bold]{type(result).__name__}[/bold]")
        tree.add(format_value(result))
        self.query_one(RichLog).write(tree)

    def candidates_callback(self, state: TargetState) -> list[TextAreaOption]:
        row, col = state.cursor_position
        script = Interpreter(state.text, [self._locals])
        completions = script.complete(line=row + 1, column=col, fuzzy=True)

        type_colors = {
            "module": "bold green",
            "class": "bold yellow",
            "instance": "bold blue",
            "function": "bold cyan",
            "param": "bold magenta",
            "path": "bold green",
            "keyword": "bold red",
            "property": "bold blue",
            "statement": "bold cyan",
        }

        return [
            TextAreaOption(
                f"{c.name} [{type_colors.get(c.type, 'bold magenta')}]{c.type}[/{type_colors.get(c.type, 'bold magenta')}]",
                c.name,
                c.get_completion_prefix_length(),
            )
            for c in completions
        ]

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True)

        self._text_area_widget = TextArea.code_editor(
            language="python",
            tab_behavior="focus",
            show_line_numbers=False,
            compact=True,
        )
        yield self._text_area_widget
        yield TextAreaAutocomplete(
            self._text_area_widget, candidates=self.candidates_callback
        )


class PeekleTree(Container):
    # Constants for lazy loading
    _MAX_INITIAL_ITEMS = 100  # Show first N items initially

    def __init__(self) -> None:
        self._tree: Tree[Dict[str, Any]] = Tree("No data")
        self._node_cache: Dict[int, Any] = {}  # Cache node data by node id
        super().__init__()

    def update_tree_data(self, label: str, data: Any) -> None:
        """When data changes, update tree."""
        self._node_cache.clear()  # Clear cache when data changes
        self._tree.reset(label)
        self._tree.root.expand()

        if data is not None:
            # Store root data in cache
            self._node_cache[id(self._tree.root)] = data
            # Build only the first level
            self._build_tree_level(data, self._tree.root)

    def _is_expandable(self, obj: Any) -> bool:
        """Check if an object should be expandable in the tree."""
        return isinstance(obj, (dict, list, tuple, set)) or (
            hasattr(obj, "__dict__") and not isinstance(obj, type)
        )

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

    def _build_tree_level(
        self, obj: Any, parent_node: TreeNode, start_index: int = 0
    ) -> None:
        """Build only one level of the tree (for lazy loading)."""
        if isinstance(obj, dict):
            items = list(obj.items())[
                start_index : start_index + self._MAX_INITIAL_ITEMS
            ]
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
                    attrs = {
                        k: v for k, v in vars(obj).items() if not k.startswith("_")
                    }
            else:
                attrs = {k: v for k, v in vars(obj).items() if not k.startswith("_")}

            items = list(attrs.items())[
                start_index : start_index + self._MAX_INITIAL_ITEMS
            ]
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

    BINDINGS = [
        Binding(key="ctrl+l", action="trigger_load_file_menu", description="Load file"),
    ]

    _filepath: reactive[Optional[Path]] = reactive(None)
    _data: reactive[Any] = reactive(None)
    _variable_name: reactive[str] = reactive("x")

    def __init__(self, filepath: Optional[Path] = None) -> None:
        self._text_area_widget: Optional[TextAreaAutocomplete] = None
        super().__init__()
        self._filepath = filepath

    def on_mount(self) -> None:
        self.title = "Peekle"

        if self._filepath:
            self._load_file(self._filepath)

    def action_trigger_load_file_menu(self) -> None:
        def on_load_file(data: LoadFileScreenState | None) -> None:
            if data is None:
                return

            self._load_file(data.path, data.variable_name)

        self.push_screen(LoadFileScreen(), on_load_file)

    def _load_file(self, filepath: Path, variable_name: str = "x") -> None:
        """Load a pickle file."""
        try:
            if filepath:
                self._filepath = filepath
                self._variable_name = variable_name

                with open(filepath, "rb") as f:
                    self._data = pickle.load(f)

                    self.notify(
                        f"[green]✓[/green] Loaded: {filepath} [dim]Type: {type(self._data).__name__}[/dim]"
                    )

                self.query_one(PeekleRepl).update_locals_data(
                    self._variable_name, self._data
                )
                self.query_one(PeekleTree).update_tree_data(
                    self._variable_name, self._data
                )

        except Exception as e:
            self.notify(f"[red]✗[/red] Error loading {filepath} file: {e}")
            self._data = None
            self._filepath = None

    @on(PeekleRepl.QueryExecuted)
    def handle_query_executed(self, message: PeekleRepl.QueryExecuted) -> None:
        """Handle query executed message to update tree."""
        self.query_one(PeekleTree).update_tree_data(message.query, message.result)

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield PeekleRepl()
        yield PeekleTree()
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
  - By default, your data is available as 'x'
  - Press Tab for autocomplete
        """,
    )

    parser.add_argument("file", nargs="?", help="Pickle file to load")

    parser.add_argument(
        "--debug", action="store_true", help="Enable debug mode with full tracebacks"
    )

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
