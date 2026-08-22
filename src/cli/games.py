import json

import click

from src.cli.main import get_client
from src.cli.output import print_table, truncate


def _echo_json(data):
    click.echo(json.dumps(data, indent=2, default=str))


def _maybe_json(ctx, data):
    if ctx.obj and ctx.obj.get("as_json"):
        _echo_json(data)
        return True
    return False


@click.command("add")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option(
    "-n", "--name", default=None, help="Display name (defaults to folder name)"
)
@click.option(
    "--no-autosnapshot",
    is_flag=True,
    help="Disable automatic snapshots for this game",
)
@click.pass_context
def add(ctx, path, name, no_autosnapshot):
    """Start tracking a game save folder."""
    client = get_client()
    result = client.add_game(
        path=path, name=name, auto_snapshot=not no_autosnapshot
    )
    game = result["game"]
    if _maybe_json(ctx, result):
        return
    click.echo(f"Added '{game['name']}' ({game['id'][:8]})")
    click.echo(f"  path: {game['path']}")
    click.echo(f"  auto snapshot: {'on' if game['auto_snapshot'] else 'off'}")


@click.command("games")
@click.pass_context
def games(ctx):
    """List tracked games."""
    client = get_client()
    rows = [
        (
            g["name"],
            g["id"][:8],
            g["path"],
            "on" if g["auto_snapshot"] else "off",
            g.get("remote_id") or "-",
        )
        for g in client.list_games()
    ]
    if not rows:
        click.echo("No games tracked yet. Add one: gsc add <path>")
        return
    print_table(["NAME", "ID", "PATH", "AUTO", "REMOTE"], rows)


@click.command("remove")
@click.argument("game")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
def remove(game, yes):
    """Stop tracking a game (snapshots in the vault are kept)."""
    client = get_client()
    if not yes:
        click.confirm(f"Remove game '{game}' from tracking?", abort=True)
    result = client.remove_game(game)
    click.echo(result["message"])


@click.command("status")
@click.argument("game", required=False, default=None)
@click.pass_context
def status(ctx, game):
    """Show daemon status; with GAME - show detailed engine state."""
    client = get_client()
    data = client.status() if game is None else None
    if data:
        if _maybe_json(ctx, data):
            return
        click.echo(f"daemon controller: {data['controller_status']}")
        print_table(
            ["GAME", "BRANCH", "SNAPSHOTS", "DIRTY", "REMOTE"],
            [
                [
                    g["name"],
                    g["engine"].get("branch", "?"),
                    g["engine"].get("snapshots", "?"),
                    "yes" if g["engine"].get("dirty") else "no",
                    g.get("remote_id") or "-",
                ]
                for g in data["games"]
            ],
        )
        return
    full = {
        g: x for g, x in ((g["name"], g) for g in client.status()["games"])
    }
    target = next(
        (v for k, v in full.items() if k.lower() == game.lower()), None
    )
    if target is None:
        raise click.ClickException(f"Game not found: {game}")
    if _maybe_json(ctx, target):
        return
    eng = target["engine"]
    click.echo(f"{target['name']}  [{eng.get('branch')}]")
    click.echo(f"  path:       {target['path']}")
    click.echo(f"  repo:       {eng.get('repo_path')}")
    click.echo(f"  snapshots:  {eng.get('snapshots')}")
    click.echo(f"  branches:   {', '.join(eng.get('branches') or [])}")
    changed = eng.get("changed_files") or []
    if changed:
        click.echo("  uncommitted:")
        for f in changed[:10]:
            click.echo(f"    {truncate(f)}")
        if len(changed) > 10:
            click.echo(f"    ... +{len(changed) - 10} more")


@click.command("snapshot")
@click.argument("game")
@click.option("-m", "--message", default=None, help="Snapshot message")
@click.option(
    "--allow-empty",
    is_flag=True,
    help="Create a snapshot even if nothing changed",
)
def snapshot(game, message, allow_empty):
    """Take a manual snapshot of a game's save folder."""
    client = get_client()
    result = client.snapshot(game, message=message, allow_empty=allow_empty)
    info = result.get("snapshot")
    if not info:
        click.echo("No changes to snapshot")
        return
    click.echo(f"Snapshotted {info['id'][:8]}: {info['message']}")


@click.command("log")
@click.argument("game")
@click.option("-n", "--limit", type=int, default=20)
@click.option("-b", "--branch", default=None)
@click.pass_context
def log(ctx, game, limit, branch):
    """List snapshots of a game, newest first."""
    client = get_client()
    snaps = client.snapshots(game, branch=branch, limit=limit)
    if _maybe_json(ctx, {"snapshots": snaps}):
        return
    if not snaps:
        click.echo("No snapshots yet")
        return
    print_table(
        ["ID", "TIMESTAMP", "MESSAGE"],
        [
            [s["id"][:8], s["timestamp"], truncate(s["message"], 50)]
            for s in snaps
        ],
    )


@click.command("restore")
@click.argument("game")
@click.argument("snapshot_id")
@click.option(
    "--hard",
    is_flag=True,
    help="Move branch back instead of creating a restore snapshot",
)
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
def restore(game, snapshot_id, hard, yes):
    """Restore the live save folder to a snapshot's state."""
    client = get_client()
    mode = (
        "HARD reset (newer commits orphaned)"
        if hard
        else "safe restore (history kept)"
    )
    if not yes:
        click.confirm(
            f"Restore '{game}' to {snapshot_id}? This modifies the "
            f"live save folder. Mode: {mode}. Continue?",
            abort=True,
        )
    result = client.restore(game, snapshot_id, hard=hard)
    info = result["snapshot"]
    click.echo(
        f"Restored -> new snapshot {info['id'][:8]}: " f"{info['message']}"
    )


# ---- branches ---------------------------------------------------------------


@click.group("branch")
def branch():
    """Manage save branches."""


@branch.command("list")
@click.argument("game")
def branch_list(game):
    client = get_client()
    data = client.branches(game)
    for name in data["branches"]:
        marker = "*" if name == data["current"] else " "
        click.echo(f"{marker} {name}")


@branch.command("create")
@click.argument("game")
@click.argument("name")
@click.option(
    "-f",
    "--from-snapshot",
    default=None,
    help="Branch off a specific snapshot",
)
@click.option(
    "-s", "--switch", "do_switch", is_flag=True, help="Switch to it right away"
)
def branch_create(game, name, from_snapshot, do_switch):
    client = get_client()
    client.create_branch(
        game, name, from_snapshot=from_snapshot, switch=do_switch
    )
    click.echo(
        f"Branch '{name}' created" + (" and activated" if do_switch else "")
    )


@click.command("switch")
@click.argument("game")
@click.argument("branch_name")
def switch(game, branch_name):
    """Activate another branch (live folder is updated to match)."""
    client = get_client()
    result = client.switch_branch(game, branch_name)
    click.echo(result["message"])


def register(group) -> None:
    group.add_command(add)
    group.add_command(games)
    group.add_command(remove)
    group.add_command(status)
    group.add_command(snapshot)
    group.add_command(log)
    group.add_command(restore)
    group.add_command(branch)
    group.add_command(switch)
