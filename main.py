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

CODEX_PROFILE = f'''
approval_policy = "untrusted"
skip_git_repo_check = true

[model_providers.custom]
name = "Custom"
base_url = "{settings.llm_base_url}"
env_key = "LLM_API_KEY"
wire_api = "chat"

[profiles.{settings.llm_model_id}]
model_provider = "custom"
model = "{settings.llm_model_id}"
'''

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    with open(os.path.expanduser('~/.screenrc'), 'a') as f:
        f.write('termcapinfo xterm* ti@:te@\n')

    with open(os.path.expanduser('~/.bashrc'), 'a') as f:
        f.write('export TERM=xterm-256color\n')
        
    os.makedirs(os.path.expanduser('~/.codex'), exist_ok=True)
    with open(os.path.expanduser('~/.codex/config.toml'), 'w') as f:
        f.write(CODEX_PROFILE)

    calls = [
        # ["screen", "-dmS", SCREEN_SESSION, "-s", "bash"],
        # ["screen", "-S", SCREEN_SESSION, "-X", "stuff", "history -c && clear\n"],
        # ["screen", "-S", SCREEN_SESSION, "-X", "logfile", LOG_FILE],
        # ["screen", "-S", SCREEN_SESSION, "-X", "log", "on"],
        # ["screen", "-S", SCREEN_SESSION, "-X", "deflog", "on"],
        # ["screen", "-S", SCREEN_SESSION, "-X", "logfile", "flush", "1"],
        # ["ttyd", "-p", "7681", "screen", "-x", SCREEN_SESSION],
        ["ttyd", "-p", "7681", "--writable", "codex", "--model", settings.llm_model_id, "--skip-git-repo-check", "--ask-for-approval", "untrusted", "--profile", settings.llm_model_id] # just a fake model :D
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