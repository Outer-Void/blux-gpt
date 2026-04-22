from __future__ import annotations

import json
import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from bluxgpt import __version__
from bluxgpt.core.client import BluxClient
from bluxgpt.core.config import ENV_PATH, load_settings
from bluxgpt.core.context import build_context, render_context_block, render_system_prompt
from bluxgpt.core.history import append_history, clear_history, read_history
from bluxgpt.core.logger import log_request
from bluxgpt.core.models import MODEL_REGISTRY, MODEL_ALIASES, resolve_model

app = typer.Typer(
    help="BluxGPT v1.0 — advisory AI CLI for the BLUX environment.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------

@app.command()
def version() -> None:
    """Print BluxGPT version."""
    console.print(f"[bold green]BluxGPT v{__version__}[/bold green]")
    blux10k = os.getenv("BLUX10K_VERSION", "")
    axiom = os.getenv("AXIOM_VERSION", "")
    if blux10k:
        console.print(f"  blux10k  {blux10k}")
    if axiom:
        console.print(f"  AXIOM    {axiom}")


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

@app.command()
def models() -> None:
    """List all configured models and their aliases."""
    console.print("[bold cyan]Model registry[/bold cyan]")
    for key, spec in MODEL_REGISTRY.items():
        console.print(f"  [green]{key}[/green]  [{spec.provider}]  {spec.description}")

    console.print()
    console.print("[bold cyan]Aliases[/bold cyan]")
    for alias, target in MODEL_ALIASES.items():
        console.print(f"  {alias}  →  {target}")


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

@app.command()
def status() -> None:
    """Show configuration status.

    Reports environment, model lane selection, and API key presence.
    This is a CONFIGURATION CHECK ONLY — provider connectivity is not verified.
    'set' means the key is present in your config file, nothing more.
    """
    settings = load_settings()
    ctx = build_context()

    console.print(Panel(
        Text.from_markup(
            f"[bold]BluxGPT v{__version__}[/bold]\n"
            f"platform     [cyan]{ctx.platform}[/cyan]\n"
            f"blux10k      [cyan]{ctx.blux10k_version or 'not detected'}[/cyan]\n"
            f"AXIOM        [cyan]{ctx.axiom_version or 'not installed'}[/cyan]\n"
            f"config file  [cyan]{ENV_PATH}[/cyan]"
        ),
        title="[bold cyan]BluxGPT — Configuration Status[/bold cyan]",
        border_style="cyan",
    ))

    console.print()
    console.print("[bold]Model lanes[/bold]")
    console.print(f"  default    {settings.default_model}")
    console.print(f"  cheap      {settings.cheap_model}")
    console.print(f"  fast       {settings.fast_model}")
    console.print(f"  reasoning  {settings.reasoning_model}")

    console.print()
    console.print("[bold]API keys[/bold]  [dim](config presence only — connectivity not verified)[/dim]")

    def _key_status(label: str, key: str) -> None:
        if key:
            masked = f"****{key[-4:]}"
            console.print(f"  {label:<14} [green]set[/green]  ({masked})")
        else:
            console.print(f"  {label:<14} [red]missing[/red]")

    _key_status("openai", settings.openai_api_key)
    _key_status("deepseek", settings.deepseek_api_key)
    _key_status("anthropic", settings.anthropic_api_key)

    console.print()
    console.print("[bold]Flags[/bold]")
    console.print(f"  context inject  {'on' if settings.context_inject else 'off'}")
    console.print(f"  log requests    {'on' if settings.log_requests else 'off'}")
    console.print(f"  AXIOM logging   {'on' if settings.axiom_logging else 'off'}")


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------

@app.command()
def ask(
    prompt: str = typer.Argument(..., help="The question or request to send to the AI."),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Model key or alias. Run 'blux models' for options.",
    ),
    no_context: bool = typer.Option(
        False, "--no-context",
        help="Skip injecting shell/env context into the prompt.",
    ),
) -> None:
    """Ask the AI a question. Advisory only — it suggests, never executes."""
    settings = load_settings()

    # Resolve model
    try:
        chosen_model = resolve_model(model or settings.default_model)
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    # Build full prompt
    full_prompt_parts = []

    # System prompt (context about the environment)
    full_prompt_parts.append(render_system_prompt())

    # Optional env context block
    if settings.context_inject and not no_context:
        ctx_block = render_context_block()
        if ctx_block:
            full_prompt_parts.append(ctx_block)

    full_prompt_parts.append(f"User request:\n{prompt}")
    full_prompt = "\n\n".join(full_prompt_parts)

    # Call the model
    client = BluxClient(settings)
    try:
        response = client.complete(full_prompt, chosen_model)
    except RuntimeError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        err_console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(code=1)

    # Print response
    console.print()
    console.print(Panel(
        response,
        title=f"[bold green]BluxGPT[/bold green] [dim]({chosen_model})[/dim]",
        border_style="green",
    ))

    # Persist
    append_history(chosen_model, prompt, response)
    if settings.log_requests:
        log_request(chosen_model, prompt, response)


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

@app.command()
def history(
    clear: bool = typer.Option(False, "--clear", help="Wipe conversation history."),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of entries to show."),
    raw: bool = typer.Option(False, "--raw", help="Output raw JSON instead of formatted."),
) -> None:
    """Show or clear conversation history."""
    if clear:
        clear_history()
        console.print("[yellow]History cleared.[/yellow]")
        return

    entries = read_history(limit=limit)
    if not entries:
        console.print("[dim]No history yet.[/dim]")
        return

    if raw:
        console.print(json.dumps(entries, indent=2, ensure_ascii=False))
        return

    for entry in entries:
        ts = entry.get("timestamp", "")[:19].replace("T", " ")
        m = entry.get("model", "?")
        p = entry.get("prompt", "")
        r = entry.get("response", "")
        console.print(f"[dim]{ts}[/dim]  [cyan]{m}[/cyan]")
        console.print(f"  [bold]Q:[/bold] {p[:120]}{'…' if len(p) > 120 else ''}")
        console.print(f"  [bold]A:[/bold] {r[:200]}{'…' if len(r) > 200 else ''}")
        console.print()


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

@app.command()
def uninstall() -> None:
    """Remove the BLUXGPT OVERLAY block from ~/.zshrc.local."""
    import shutil
    from pathlib import Path

    zsh_local = Path.home() / ".zshrc.local"
    block_start = "### >>> BLUXGPT OVERLAY >>>"
    block_end = "### <<< BLUXGPT OVERLAY <<<"

    if not zsh_local.exists():
        console.print("[dim]~/.zshrc.local does not exist. Nothing to do.[/dim]")
        raise typer.Exit(code=0)

    content = zsh_local.read_text(encoding="utf-8")
    if block_start not in content:
        console.print("[dim]BLUXGPT OVERLAY not found in ~/.zshrc.local. Nothing to do.[/dim]")
        raise typer.Exit(code=0)

    # Backup before modifying
    backup = zsh_local.with_suffix(".local.bak")
    shutil.copy2(zsh_local, backup)

    # Strip the block
    lines = content.splitlines(keepends=True)
    out_lines = []
    skip = False
    for line in lines:
        if line.rstrip() == block_start:
            skip = True
            continue
        if line.rstrip() == block_end:
            skip = False
            continue
        if not skip:
            out_lines.append(line)

    zsh_local.write_text("".join(out_lines), encoding="utf-8")

    console.print(f"[green]BLUXGPT OVERLAY removed from ~/.zshrc.local[/green]")
    console.print(f"[dim]Backup saved: {backup}[/dim]")
    console.print("[dim]Run 'source ~/.zshrc' or open a new terminal.[/dim]")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
