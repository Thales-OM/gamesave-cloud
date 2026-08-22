import os
import threading
from typing import Optional

from fastapi import FastAPI, HTTPException

from src import __version__
from src.api import models
from src.api.state import AppState, get_state, set_state
from src.exceptions import (
    BranchError,
    GameNotFoundError,
    MetadataError,
    SnapshotNotFoundError,
)
from src.logger import LoggerFactory

logger = LoggerFactory.getLogger(__name__)


def create_app(state: AppState) -> FastAPI:
    app = FastAPI(title="gamesave-cloud daemon", version=__version__)
    set_state(state)

    # ---- health / lifecycle -------------------------------------------------

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/status")
    def status():
        s = get_state()
        games = []
        for game in s.metadata.games:
            try:
                engine = s.service.engine_for(game)
                engine_status = engine.status()
            except Exception as ex:
                engine_status = {"error": str(ex)}
            games.append(
                {
                    "id": game.id,
                    "name": game.name,
                    "path": str(game.path),
                    "auto_snapshot": game.auto_snapshot,
                    "remote_id": game.remote_id,
                    "engine": engine_status,
                }
            )
        return {
            "controller_status": s.controller.status,
            "games": games,
            "remotes": [r.model_dump() for r in s.metadata.remotes],
        }

    @app.post("/shutdown")
    def shutdown():
        threading.Thread(target=_delayed_exit, daemon=True).start()
        return {"message": "Shutting down"}

    def _delayed_exit():
        import time

        time.sleep(0.5)
        os._exit(0)

    # ---- games --------------------------------------------------------------

    @app.post("/games")
    def add_game(req: models.CreateGameRequest):
        s = get_state()
        try:
            game = s.controller.add_game(
                path=req.path,
                name=req.name,
                auto_snapshot=req.auto_snapshot,
            )
        except MetadataError as ex:
            raise HTTPException(status_code=409, detail=str(ex))
        except Exception as ex:
            raise HTTPException(status_code=400, detail=str(ex))
        return {"message": "Game added", "game": game.model_dump(mode="json")}

    @app.get("/games")
    def list_games():
        s = get_state()
        return {
            "games": [
                {
                    "id": g.id,
                    "name": g.name,
                    "path": str(g.path),
                    "auto_snapshot": g.auto_snapshot,
                    "remote_id": g.remote_id,
                }
                for g in s.metadata.games
            ]
        }

    @app.delete("/games/{name_or_id}")
    def remove_game(name_or_id: str):
        s = get_state()
        try:
            removed = s.controller.remove_game(name_or_id)
        except GameNotFoundError as ex:
            raise HTTPException(status_code=404, detail=str(ex))
        return {"message": f"Removed '{removed.name}'"}

    # ---- snapshots ----------------------------------------------------------

    @app.post("/games/{name_or_id}/snapshot")
    def snapshot_game(name_or_id: str, req: models.SnapshotRequest):
        s = get_state()
        game = _require_game(s, name_or_id)
        info = s.service.snapshot_now(
            game, message=req.message, allow_empty=req.allow_empty
        )
        if info is None:
            return {"message": "No changes to snapshot", "snapshot": None}
        return {"message": "Snapshot created", "snapshot": info.model_dump()}

    @app.get("/games/{name_or_id}/snapshots")
    def list_snapshots(
        name_or_id: str, branch: Optional[str] = None, limit: int = 50
    ):
        s = get_state()
        game = _require_game(s, name_or_id)
        engine = s.service.engine_for(game)
        snaps = engine.list_snapshots(branch=branch, limit=limit)
        return {"snapshots": [x.model_dump(mode="json") for x in snaps]}

    @app.post("/games/{name_or_id}/restore")
    def restore(name_or_id: str, req: models.RestoreRequest):
        s = get_state()
        game = _require_game(s, name_or_id)
        engine = s.service.engine_for(game)
        try:
            info = engine.restore(req.snapshot_id, hard=req.hard)
        except SnapshotNotFoundError as ex:
            raise HTTPException(status_code=404, detail=str(ex))
        return {"message": "Restored", "snapshot": info.model_dump()}

    # ---- branches -----------------------------------------------------------

    @app.get("/games/{name_or_id}/branches")
    def branches(name_or_id: str):
        s = get_state()
        game = _require_game(s, name_or_id)
        engine = s.service.engine_for(game)
        return {
            "branches": engine.list_branches(),
            "current": engine.current_branch(),
        }

    @app.post("/games/{name_or_id}/branches")
    def create_branch(name_or_id: str, req: models.CreateBranchRequest):
        s = get_state()
        game = _require_game(s, name_or_id)
        engine = s.service.engine_for(game)
        try:
            engine.create_branch(req.name, from_snapshot=req.from_snapshot)
            if req.switch:
                engine.switch_branch(req.name)
        except BranchError as ex:
            raise HTTPException(status_code=409, detail=str(ex))
        return {
            "message": f"Branch '{req.name}' created",
            "switched": req.switch,
        }

    @app.post("/games/{name_or_id}/switch")
    def switch_branch(name_or_id: str, req: models.SwitchBranchRequest):
        s = get_state()
        game = _require_game(s, name_or_id)
        engine = s.service.engine_for(game)
        try:
            engine.switch_branch(req.branch)
        except BranchError as ex:
            raise HTTPException(status_code=404, detail=str(ex))
        return {"message": f"Switched to '{req.branch}'"}

    return app


def _require_game(state, name_or_id: str):
    try:
        return state.controller.get_game(name_or_id)
    except GameNotFoundError as ex:
        raise HTTPException(status_code=404, detail=str(ex))
