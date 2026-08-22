import click

from src import __version__
from src.cli.client import DaemonClient, read_runtime
from src.exceptions import DaemonConnectionError


def get_client() -> DaemonClient:
    try:
        return DaemonClient.connect()
    except DaemonConnectionError as ex:
        raise click.ClickException(str(ex))


@click.group()
@click.version_option(__version__, prog_name="gsc")
@click.option(
    "--json", "as_json", is_flag=True, help="Emit machine-readable JSON output"
)
@click.pass_context
def cli(ctx, as_json):
    """gamesave-cloud: snapshots, branches and cloud sync for game saves."""
    ctx.ensure_object(dict)
    ctx.obj = {"as_json": as_json}


# ---- daemon lifecycle ------------------------------------------------------


@cli.group()
def daemon():
    """Manage the background daemon."""


@daemon.command("start")
@click.option("-p", "--port", type=int, default=None, help="Port to listen on")
def daemon_start(port):
    from src.cli.client import start_daemon

    try:
        actual = start_daemon(port=port)
    except Exception as ex:
        raise click.ClickException(str(ex))
    click.echo(f"Daemon started on 127.0.0.1:{actual}")


@daemon.command("stop")
def daemon_stop():
    from src.cli.client import stop_daemon

    if stop_daemon():
        click.echo("Daemon stopped")
    else:
        click.echo("Daemon was not running")


@daemon.command("status")
def daemon_status():
    rt = read_runtime()
    if not rt:
        click.echo("Not running (no runtime descriptor)")
        return
    click.echo(f"pid={rt['pid']} port={rt['port']} host={rt['host']}")
    try:
        client = DaemonClient(f"http://{rt['host']}:{rt['port']}")
        health = client.get("/health")
        click.echo(
            f"health={health.get('status')} "
            f"version={health.get('version')}"
        )
    except Exception as ex:
        click.echo(f"not answering: {ex}")


# register other command groups


def register_commands() -> None:
    from src.cli.games import register as register_games
    from src.cli.remote import register as register_remote

    register_games(cli)
    register_remote(cli)


register_commands()


if __name__ == "__main__":
    cli()
