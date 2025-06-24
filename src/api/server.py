from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import argparse
from src.api.models import CreateDirectoryRequest
from src.core.controller import DirectoryController
from src.models.metadata import Metadata
from src.settings import settings
from src.logger import LoggerFactory
from src.models.tracked_directory import TrackedDirectory


logger = LoggerFactory.getLogger(__name__)


metadata = Metadata(path=settings.metadata.storage_filepath)
controller: DirectoryController = None

app = FastAPI()


@app.get("/start", response_model=JSONResponse)
async def start():
    controller = DirectoryController(directories=metadata.directories)
    controller.start_all()
    return JSONResponse(status_code=200, content={"message": "Started server"})


@app.get("/health", response_model=JSONResponse)
async def health():
    return JSONResponse(status_code=200, content={"message": "OK"})


@app.get("/add/d", response_model=JSONResponse)
async def add_directory(body: CreateDirectoryRequest):
    dir = TrackedDirectory(**body)
    controller.add_directory(dir=dir)
    controller.start_watching_directory(dir=dir)
    return JSONResponse(
        status_code=200, content={"message": "Directory added successfully"}
    )


def run(port: int = 8080):
    logger.info(f"Starting Daemon server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daemon server application")

    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8080,
        help="Port number to listen on (default: 8080)",
    )

    args = parser.parse_args()
    run(port=args.port)
