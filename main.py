import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
import sys
from fastapi import FastAPI
from agent.anthropic_proxy import get_models_fn, app as anthropic_proxy_app
import asyncio
from agent.apis import router as apis_app
from agent.configs import settings
import uvicorn
import json

from contextlib import asynccontextmanager
from agent.opencode_sdk import update_config_task

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Mark incomplete tasks as failed
    try:
        from agent.database import get_task_repository
        task_repo = get_task_repository()
        failed_count = task_repo.mark_incomplete_tasks_as_failed()
        task_repo.db.close()  # Close the database connection
        if failed_count > 0:
            logger.info(f"Marked {failed_count} incomplete tasks as failed during startup")
        else:
            logger.info("No incomplete tasks found during startup")
    except Exception as e:
        logger.error(f"Error cleaning up incomplete tasks during startup: {e}")

    # Start the config update task
    task = asyncio.create_task(update_config_task(repeat_interval=30))
    PROXY_PORT = 12345

    logger.info(f"Starting socat proxy on port {PROXY_PORT}")
    command = f"socat TCP-LISTEN:{PROXY_PORT},fork TCP:localhost:{settings.port}"
    process = await asyncio.create_subprocess_shell(command, stdout=sys.stdout, stderr=sys.stderr)

    try:
        yield
    finally:
        task.cancel()

        if process:
            process.terminate()
            await process.wait()

app = FastAPI(lifespan=lifespan)
app.include_router(apis_app)
app.include_router(anthropic_proxy_app)

# Include task management and pubsub routers
from agent.task_api import router as task_router
from agent.pubsub import api_router as pubsub_router
app.include_router(task_router)
app.include_router(pubsub_router)

# Static file serving
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="public"), name="static")

# Serve dashboard at root
from fastapi.responses import FileResponse
@app.get("/")
async def dashboard():
    return FileResponse("public/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port)