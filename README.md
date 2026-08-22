# gamesave-cloud

Git-backed snapshots, branching and cloud sync for game save folders.

`gamesave-cloud` watches your game save directories, takes automatic
debounced snapshots into a local git vault, and lets you branch, revert
and sync save history to any storage backend - without touching the
games themselves or requiring any launcher integration.

## Features

- **Automatic snapshots** - file activity triggers a debounced snapshot
  (quiet period + cooldown, both configurable), so a single play session
  becomes one clean commit instead of hundreds.
- **Time travel** - every snapshot is a git commit. Restore old saves
  safely (history-preserving) or hard-reset to an exact point in time.
- **Save slots as branches** - experiment on a `before-boss` branch and
  switch back to `main` at any time; switching rewrites the live folder.
- **Cross-machine sync** - history travels as a single git bundle with a
  `latest.json` pointer, so two machines converge through any dumb
  file store.
- **Pluggable remotes** - filesystem (USB/network folder), S3-compatible
  object storage, WebDAV and Yandex Disk built in; Google Drive planned.
- **Simple auth** - credentials resolve from command-line options, then
  the OS keyring (Windows Credential Manager / Secret Service), then an
  interactive prompt. Secrets never touch `metadata.json`.
- **Save folder detection** - discovers Steam libraries via appmanifests,
  Epic installs via launcher manifests, plus a heuristic scan of common
  save locations.

## Architecture

```
save folder <-> watchdog events -> SnapshotService (debounce/cooldown)
                                        |
                                        v
                              GitEngine (vault: <appdata>/repos/<slug>.git)
                                        |
                          SyncService -> RemoteStorage backend
                          (bundle export/import + latest.json pointer)
```

- The daemon (`python -m src.daemon`) owns watchers and exposes a local
  HTTP API (default `127.0.0.1:7420`, port auto-negotiated).
- The CLI (`gsc`) talks to the daemon; it can start/stop it itself.
- Game metadata lives in `<appdata>/gamesave-cloud/metadata.json`
  (schema v2); vault repos live in `<appdata>/gamesave-cloud/repos`.

## Installation

```pwsh
py -3.10 -m venv .venv
.venv\Scripts\pip install -e .
pre-commit install        # optional, for development
```

## Quick start

```pwsh
# start the background daemon
gsc daemon start

# track a save folder (auto-detects name from the folder)
gsc add "C:\Users\me\Saved Games\Hollow Knight"

# everything else works out of the box; manual snapshot:
gsc snapshot hollow-knight -m "before pantheon"

# inspect history
gsc log hollow-knight

# restore a snapshot safely (keeps history)
gsc restore hollow-knight <snapshot-id>

# branches for risky experiments
gsc branch create hollow-knight before-boss --switch
gsc switch hollow-knight main

## Cloud sync

```pwsh
# register a remote destination (prompts only for missing fields)
gsc remote add filesystem usb --path D:\Backups --for-game hollow-knight --push

# push/pull full save history (git bundle under the hood)
gsc push hollow-knight
gsc pull  hollow-knight

# other backends
gsc remote add s3 mybucket     --bucket saves --prefix games
gsc remote add webdav nas      --url https://nas.local/dav
gsc remote add yandex yadisk   # token stored in OS keyring
gsc remote types               # list all supported backends
```

On a second machine: register the same remote path, then
`gsc pull` - game names map to identical vault slugs, so both machines
converge on the same bundle.

## Discovery

```pwsh
gsc detect                 # steam + epic + heuristic scan
gsc detect -s steam
gsc add --exe "D:\Games\MyGame\bin\game.exe"   # resolve saves from exe
```

## Configuration

Environment variables (all optional):

| Variable           | Default | Meaning                                  |
|--------------------|---------|------------------------------------------|
| `QUIET_PERIOD_SEC` | 30      | silence required before auto-snapshot    |
| `COOLDOWN_SEC`     | 300     | min seconds between auto-snapshots       |
| `DAEMON_PORT`      | 7420    | API port (falls back to next free port)  |
| `VAULT_DIR`        | %LOCALAPPDATA%\gamesave-cloud\repos | vault root |

## Development

```pwsh
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\pytest          # run the test suite
```

Commits are guarded by pre-commit hooks running black + flake8 at 79
columns.
