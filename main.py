from dotenv import load_dotenv

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not load_dotenv():
    logger.warning("No .env file found")

import os
import sys
from fastapi import FastAPI
from agent.anthropic_proxy import app as anthropic_proxy_app
from agent.xterm_toolcalls import LOG_FILE, SCREEN_SESSION
import asyncio
from agent.apis import router as apis_app

async def lifespan(app: FastAPI):
    with open(os.path.expanduser('~/.screenrc'), 'a') as f:
        f.write('termcapinfo xterm* ti@:te@\n')

    with open(os.path.expanduser('~/.bashrc'), 'a') as f:
        f.write('export TERM=xterm-256color\n')
        
        
    calls = [
        ["screen", "-dmS", SCREEN_SESSION, "-s", "bash"]
        ["screen", "-S", SCREEN_SESSION, "-X", "stuff", "history -c && clear\n"],
        ["screen", "-S", SCREEN_SESSION, "-X", "logfile", LOG_FILE],
        ["screen", "-S", SCREEN_SESSION, "-X", "log", "on"],
        ["screen", "-S", SCREEN_SESSION, "-X", "deflog", "on"],
        ["screen", "-S", SCREEN_SESSION, "-X", "logfile", "flush", "1"],
        ["ttyd", "-p", "7681", "screen", "-x", SCREEN_SESSION],
        ["ttyd", "-p", "7682", "--writable", "claude"]
    ]
    
    processes: list[asyncio.subprocess.Process] = []

    for call in calls:
        process = await asyncio.create_subprocess_exec(
            *call,
            stdout=sys.stderr,
            stderr=sys.stderr,
            env=os.environ
        )
        processes.append(process)

    try:
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