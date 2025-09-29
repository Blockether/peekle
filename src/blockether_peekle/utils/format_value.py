from typing import Any


def format_value(value: Any, max_length: int = 80) -> str:
    """Format a value for display with colors visible in both dark and light themes."""
    if value is None:
        return "[bold magenta]None[/bold magenta]"
    elif isinstance(value, bool):
        return f"[bold cyan]{value}[/bold cyan]"
    elif isinstance(value, (int, float)):
        return f"[bold blue]{value}[/bold blue]"
    elif isinstance(value, str):
        if len(value) > max_length:
            value = value[:max_length] + "..."
        return f"[bold green]{repr(value)}[/bold green]"
    elif isinstance(value, bytes):
        return f"[bold red]<bytes: {len(value)} bytes>[/bold red]"
    elif isinstance(value, dict):
        items = list(value.items())[:4]
        formatted_items = [f"{k}: {type(v).__name__}" for k, v in items]
        if len(value) > 4:
            formatted_items.append("...")
        return f"[bold yellow]{{{', '.join(formatted_items)}}}[/bold yellow]"
    else:
        str_repr = str(value)
        if len(str_repr) > max_length:
            str_repr = str_repr[:max_length] + "..."
        return f"[bold yellow]{str_repr}[/bold yellow]"
