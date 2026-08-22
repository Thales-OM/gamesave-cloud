import json

import click

from src.cli.main import get_client
from src.cli.output import print_table


def _echo_json(data):
    click.echo(json.dumps(data, indent=2, default=str))


def _maybe_json(ctx, data):
    if ctx.obj and ctx.obj.get("as_json"):
        _echo_json(data)
        return True
    return False


@click.group("remote")
def remote():
    """Configure and use remote storage destinations."""


@remote.command("types")
def types():
    """List available storage backend types."""
    from src.storage import STORAGE_REGISTRY

    for name, cls in sorted(STORAGE_REGISTRY.items()):
        click.echo(f"{name:12s} {cls.__doc__.strip().splitlines()[0]}")


@remote.command("add")
@click.argument("type_name")
@click.argument("name")
@click.option(
    "--for-game",
    "game",
    default=None,
    help="Also assign this remote to a game",
)
@click.option(
    "--push/--no-push",
    "assign_push",
    default=True,
    help="Assign as the game's push target (with --for-game)",
)
@click.option(
    "--opt",
    "opts",
    multiple=True,
    help="Non-secret option as key=value (repeatable)",
)
@click.pass_context
def add(ctx, type_name, name, game, assign_push, opts):
    """
    Register a remote destination. Missing options are prompted for;
    secrets are stored in the OS keyring.
    """
    from src.exceptions import StorageNotRegisteredError
    from src.storage import get_storage_class

    try:
        fields = get_storage_class(type_name).fields()
    except StorageNotRegisteredError as ex:
        raise click.ClickException(str(ex))

    provided = {}
    for pair in opts:
        if "=" not in pair:
            raise click.ClickException(f"--opt expects key=value: {pair}")
        k, _, v = pair.partition("=")
        provided[k.strip()] = v.strip()

    from src.auth.credentials import resolve_credentials

    resolved = resolve_credentials(
        fields=fields,
        provided=provided,
        remote_id=f"new:{name}",
        persist_secrets=False,
    )
    secrets = {
        f.name: resolved[f.name]
        for f in fields
        if f.secret and f.name in resolved
    }
    options = {
        f.name: resolved[f.name]
        for f in fields
        if not f.secret and f.name in resolved
    }

    client = get_client()
    result = client.post(
        "/remotes",
        {
            "type": type_name,
            "name": name,
            "options": options,
        },
    )
    remote_id = result["id"]

    # Persist secrets under the real remote id now that it exists.
    from src.auth.credentials import store_secret

    if secrets:
        click.echo("Storing credentials in OS keyring...")
    for field_name, value in secrets.items():
        store_secret(remote_id, field_name, value)

    if game:
        s = client.status()
        match = next(
            (g for g in s["games"] if g["name"].lower() == game.lower()), None
        )
        if not match:
            raise click.ClickException(f"Game not found: {game}")
        _set_game_remote(
            client, match["id"], remote_id if assign_push else None
        )
        click.echo(f"Assigned to '{match['name']}'")

    click.echo(f"Remote '{name}' added ({type_name}, id={remote_id})")


def _set_game_remote(client, game_id, remote_id):
    """Persist game.remote_id through the games API."""
    # The API does not expose partial updates; go through remove+add is
    # destructive - instead use dedicated endpoint below.
    client.post(f"/games/{game_id}/remote", {"remote_id": remote_id})


@remote.command("list")
@click.pass_context
def list_remotes(ctx):
    client = get_client()
    data = client.get("/remotes")["remotes"]
    if _maybe_json(ctx, {"remotes": data}):
        return
    if not data:
        click.echo("No remotes configured. Add one: gsc remote add")
        return
    print_table(
        ["NAME", "TYPE", "USED BY"],
        [[r["name"], r["type"], ", ".join(r["used_by"]) or "-"] for r in data],
    )


@remote.command("remove")
@click.argument("name_or_id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
def remove(name_or_id, yes):
    """Remove a remote and its stored secrets."""
    from src.auth.credentials import delete_secrets
    from src.storage import get_storage_class

    client = get_client()
    remotes = {r["id"]: r for r in client.get("/remotes")["remotes"]}
    match = next(
        (
            r
            for rid, r in remotes.items()
            if rid == name_or_id or r["name"].lower() == name_or_id.lower()
        ),
        None,
    )
    if not yes:
        click.confirm(f"Remove remote '{name_or_id}'?", abort=True)
    result = client.delete(f"/remotes/{name_or_id}")
    if match:
        try:
            fields = get_storage_class(match["type"]).fields()
            delete_secrets(match["id"], fields)
        except Exception:
            pass
    click.echo(result["message"])


@remote.command("test")
@click.argument("name_or_id")
def test(name_or_id):
    client = get_client()
    try:
        result = client.request("POST", "/remotes/test", {"id": name_or_id})
    except RuntimeError as ex:
        raise click.ClickException(f"FAILED: {ex}")
    click.echo(f"OK: '{result.get('type')}' reachable")


@remote.command("status")
@click.argument("name_or_id")
@click.pass_context
def status(ctx, name_or_id):
    """Per-game sync state of a remote (latest artifact, counts)."""
    client = get_client()
    result = client.request("POST", f"/remotes/{name_or_id}/status", {})
    if _maybe_json(ctx, result):
        return
    click.echo(f"Remote '{result['remote']}':")
    for game, info in result["games"].items():
        latest = (info or {}).get("latest") or {}
        artifacts = (info or {}).get("artifacts")
        click.echo(
            f"  {game}: latest={latest.get('artifact', '-')} "
            f"pushed={latest.get('pushed_at', '-')} "
            f"(bundles on remote: {artifacts})"
        )


@remote.command("assign")
@click.argument("game")
@click.argument("name_or_id", required=False, default=None)
def assign(game, name_or_id):
    """Set (or clear, if omitted) the remote used by a game."""
    client = get_client()
    result = client.post(f"/games/{game}/remote", {"remote_id": name_or_id})
    click.echo(result["message"])


@click.command("push")
@click.argument("game", required=False, default=None)
@click.option(
    "-r",
    "--remote",
    default=None,
    help="Override the game's configured remote",
)
def push(game, remote):
    """Push history to remote storage (all synced games if GAME omitted)."""
    client = get_client()
    result = client.request("POST", "/push", {"game": game, "remote": remote})
    click.echo(result["message"])
    for name, artifact in result.get("artifacts", {}).items():
        click.echo(f"  {name}: {artifact}")


@click.command("pull")
@click.argument("game", required=False, default=None)
@click.option(
    "-r",
    "--remote",
    default=None,
    help="Override the game's configured remote",
)
def pull(game, remote):
    """Pull history from remote storage into local snapshots."""
    client = get_client()
    result = client.request("POST", "/pull", {"game": game, "remote": remote})
    click.echo(result["message"])


def register(group) -> None:
    group.add_command(remote)
    group.add_command(assign)
    group.add_command(push)
    group.add_command(pull)
