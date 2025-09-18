from typing import Any, Optional


def format_value(value: Any, max_length: Optional[int] = None) -> str:
    """Format a value for display with colors visible in both dark and light themes."""
    if value is None:
        return "[bold magenta]None[/bold magenta]"
    elif isinstance(value, bool):
        return f"[bold cyan]{value}[/bold cyan]"
    elif isinstance(value, (int, float)):
        return f"[bold blue]{value}[/bold blue]"
    elif isinstance(value, str):
        if max_length is not None and len(value) > max_length:
            value = value[:max_length] + "..."
        return f"[bold green]{repr(value)}[/bold green]"
    elif isinstance(value, bytes):
        return f"[bold red]<bytes: {len(value)} bytes>[/bold red]"
    else:
        str_repr = str(value)
        if max_length is not None and len(str_repr) > max_length:
            str_repr = str_repr[:max_length] + "..."
        return f"[bold yellow]{str_repr}[/bold yellow]"
