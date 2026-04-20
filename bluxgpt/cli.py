import typer
from rich import print

app = typer.Typer()

@app.command()
def version():
    print("[bold green]BluxGPT v1.0.0[/bold green]")

@app.command()
def status():
    print("BluxGPT status: OK (minimal build)")

@app.command()
def ask(query: str):
    print(f"[bold cyan]Query:[/bold cyan] {query}")
    print("[yellow]Response:[/yellow] (stub — AI not wired yet)")

if __name__ == "__main__":
    app()
