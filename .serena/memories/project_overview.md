# Peekle Project Overview

## Purpose
Peekle is a powerful REPL (Read-Eval-Print Loop) tool for exploring pickle files with rich formatting, query capabilities, intellisense, and interactive Python expressions. It provides an interactive environment to inspect and understand serialized Python objects stored in pickle format.

## Tech Stack
- **Language**: Python 3.12+
- **UI Framework**: Textual (terminal UI library)
- **Key Dependencies**:
  - `jedi` (>=0.19.2) - For intellisense/autocomplete
  - `rich` (>=14.1.0) - For rich text formatting
  - `textual[syntax]` (>=6.1.0) - For the terminal UI
- **Build System**: setuptools
- **Package Manager**: uv (NOT pip)

## Main Features
- Tree View: Hierarchical visualization of pickle data structures
- REPL Interface: Full Python REPL with access to loaded data as variable `x`
- Deep Inspection: Navigate nested data structures
- Context-Aware Suggestions: Smart completions based on object types
- Full Python Expressions: Execute any Python code including imports
- Persistent Environment: Variables and imports persist across commands

## Entry Points
- Main script: `blockether_peekle` (console script)
- Module entry: `src/blockether_peekle/main.py`
- Usage: `uv run blockether_peekle data.pkl`

## Project Structure
```
blockether-peekle/
├── src/
│   └── blockether_peekle/
│       ├── main.py              # Main application entry
│       ├── utils/                # Utility modules
│       │   └── format_value.py  # Value formatting utilities
│       └── widgets/              # UI widgets
│           └── autocomplete/     # Autocomplete functionality
│               ├── autocomplete.py
│               ├── text_area_autocomplete.py
│               └── path_autocomplete.py
├── tests/                        # Test suite
│   └── blockether_peekle/
│       └── widgets/
│           └── text_area_autocomplete/
├── docs/                         # Documentation
├── pyproject.toml               # Project configuration
├── CLAUDE.md                    # Development guidelines
└── README.md                    # Project documentation
```

## Key Components
- **LoadFileScreen**: Initial screen for file selection
- **PeekleRepl**: REPL interface component  
- **PeekleTree**: Tree view for data visualization
- **PeekleApp**: Main application class
- **Autocomplete System**: Context-aware suggestion system