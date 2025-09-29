<h2 align="center">
  Peekle
</h2>

<div align="center">
A powerful REPL for exploring pickle files with rich formatting, query capabilities, intellisense, and interactive Python expressions.
</div>

<div align="center">
  <h2>
    <a href="https://pypi.org/project/blockether-peekle/"><img src="https://img.shields.io/pypi/v/blockether-peekle?color=%23007ec6&label=pypi%20package" alt="Package version"></a>
    <a href="https://pypi.org/project/blockether-peekle/"><img src="https://img.shields.io/pypi/pyversions/blockether-peekle" alt="Supported Python versions"></a>
    <a href="https://github.com/Blockether/catalyst/blob/main/LICENSE">
      <img src="https://img.shields.io/badge/license-MIT-green" alt="License - MIT">
    </a>
  </h2>
</div>

<div align="center">
  <h3>
  
[Why Peekle?](#why-peekle) • [Quick Start](#quick-start) • [Features](#features) • [Roadmap](#roadmap)

  </h3>
</div>

## Why Peekle?

Pickle files are a common way to serialize and store complex Python objects, but they can be difficult to inspect and understand. Peekle provides an interactive REPL environment that allows you to explore pickle files in a user-friendly way.

## Quick Start

Install Peekle directly from GitHub (PyPI release coming soon):

```bash
# Using uv (recommended)
uv add "blockether-peekle @ git+https://github.com/Blockether/peekle.git"

# Or using pip
pip install "blockether-peekle @ git+https://github.com/Blockether/peekle.git"
```

Then, open Peekle with a pickle file:

```bash
uv run blockether_peekle data.pkl
```

## Features

- **Tree View**: Hierarchical visualization of pickle data structures with expandable nodes
- **REPL Interface**: Full Python REPL with access to loaded data as variable `x`
- **Deep Inspection**: Navigate through nested dictionaries, lists, tuples, sets, and custom objects
- **Context-Aware Suggestions**: Smart completions based on object types and attributes
- **Full Python Expressions**: Execute any Python code including imports, assignments, function definitions and built-in functions
- **Persistent Environment**: Variables and imports persist across commands

## Roadmap

TODO

## Special Thanks

- [ptpython](https://github.com/prompt-toolkit/ptpython)
- [textual-autocomplete](https://github.com/darrenburns/textual-autocomplete)
