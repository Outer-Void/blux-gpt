import typer

app = typer.Typer()

@app.command()
def main(msg: str = "Hello"):
    print(f"BluxGPT: {msg}")

if __name__ == "__main__":
    app()
