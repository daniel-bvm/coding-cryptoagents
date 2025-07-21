import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
import sys
from fastapi import FastAPI, Request
from agent.anthropic_proxy import app as anthropic_proxy_app
import asyncio
from agent.apis import router as apis_app
from agent.configs import settings
import shlex
import uvicorn

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup tmux session sequentially
    logger.info("Setting up tmux session...")
    
    # Create playground directory
    playground_dir = "/workspace/playground"
    logger.info(f"Creating playground directory: {playground_dir}")
    await asyncio.create_subprocess_shell(
        f"mkdir -p {playground_dir}",
        stdout=sys.stderr,
        stderr=sys.stderr,
        shell=True
    )
    
    # Kill any existing session first
    await asyncio.create_subprocess_shell(
        "tmux kill-session -t main 2>/dev/null || true",
        stdout=sys.stderr,
        stderr=sys.stderr,
        shell=True
    )
    
    # Create new session with first command in playground directory
    logger.info("Creating tmux session...")

    process1 = await asyncio.create_subprocess_shell(
        f"tmux -f .tmux.conf new-session -d -s main -c {playground_dir} 'export LLM_BASE_URL=http://localhost:{settings.port}/v1 && (/bin/opencode || /bin/bash)'",
        stdout=sys.stderr,
        stderr=sys.stderr,
        shell=True,
        env=dict(os.environ)
    )
    await process1.wait()
    
    # Split the window vertically and start bash in the new pane (also in playground directory)
    logger.info("Splitting tmux window...")
    process2 = await asyncio.create_subprocess_shell(
        f"tmux split-window -h -t main -c {playground_dir} '/bin/bash'",
        stdout=sys.stderr,
        stderr=sys.stderr,
        shell=True,
        env=dict(os.environ)
    )
    await process2.wait()
    
    # Now start long-running processes
    calls = [
        # Start ttyd to stream the tmux session
        ["ttyd", "-p", "7681", "-W", "tmux", "attach-session", "-t", "main"]
    ]

    processes: list[asyncio.subprocess.Process] = []

    for call in calls:
        logger.info(f"Starting process: {call}")
        process = await asyncio.create_subprocess_shell(
            shlex.join(call),
            stdout=sys.stderr,
            stderr=sys.stderr,
            shell=True,
            env=dict(os.environ)
        )

        processes.append(process)
        logger.info(f"Process started: {process.pid}")

    try:
        logger.info("Starting processes...")
        yield

    finally:
        waiting_task = []

        for process in processes:
            process.terminate()
            waiting_task.append(asyncio.create_task(process.wait()))

        logger.info("Gracefully shutting down for 10 seconds...")
        completed, pending = await asyncio.wait(waiting_task, timeout=10)

        for task, process in zip(completed, processes):
            if task in pending:
                process.kill()
                logger.warning(f"Process {process.pid} killed after 10 seconds")

        logger.info("Shutdown complete")

app = FastAPI(lifespan=lifespan)
app.include_router(anthropic_proxy_app)
app.include_router(apis_app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    method = request.method
    path = request.url.path
    logger.debug(f"Request: {method} {path}")
    response = await call_next(request)
    
    return response

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port)