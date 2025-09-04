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

wrapped_base_url = f"http://localhost:{settings.port}/v1"
config_path = os.path.expanduser("~/.config/opencode/opencode.json")
opencode_dir = os.path.expanduser("~/.config/opencode")
CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

os.makedirs(opencode_dir, exist_ok=True)

async def update_config_task(repeat_interval=0): # non-positive --> no repeat
    isearch_path = os.path.join(CURRENT_DIRECTORY, "mcps", "tavily_search", "main.py")
    financial_datasets_path = os.path.join(CURRENT_DIRECTORY, "mcps", "financial_datasets", "main.py")
    pexels_path = os.path.join(CURRENT_DIRECTORY, "mcps", "pexels", "main.py")

    while True:
        try:
            models = await get_models_fn()
            mcp_env = {}

            if "ETERNALAI_MCP_PROXY_URL" in os.environ:
                mcp_env["ETERNALAI_MCP_PROXY_URL"] = os.environ["ETERNALAI_MCP_PROXY_URL"]

            if settings.tavily_api_key:
                mcp_env["TAVILY_API_KEY"] = settings.tavily_api_key

            if settings.financial_datasets_api_key:
                mcp_env["FINANCIAL_DATASETS_API_KEY"] = settings.financial_datasets_api_key

            if settings.pexels_api_key:
                mcp_env["PEXELS_API_KEY"] = settings.pexels_api_key

            if settings.twitter_api_key:
                mcp_env["TWITTER_API_KEY"] = settings.twitter_api_key

            mcp_config = {
                "tavily": {
                    "type": "local",
                    "command": [sys.executable, isearch_path],
                    "enabled": True,
                    "environment": mcp_env
                },
                "finance": {
                    "type": "local",
                    "command": [sys.executable, financial_datasets_path],
                    "enabled": True,
                    "environment": mcp_env
                },
                "pexels": {
                    "type": "local",
                    "command": [sys.executable, pexels_path],
                    "enabled": True,
                    "environment": mcp_env
                }
            }

            config = {
                "$schema": "https://opencode.ai/config.json",
                    "provider": {
                        settings.llm_model_provider: {
                            "npm": "@ai-sdk/openai-compatible",
                            "name": "LocalAI",
                            "options": {
                                "baseURL": wrapped_base_url
                            },
                            "models": {
                                e['id']: {
                                    "name": e['name']
                                }
                                for e in models
                            }
                        }
                    },
                    "agent":  {
                        "build": {
                            "mode": "primary",
                            "tools": {
                                "bash": True,
                                "edit": True,
                                "write": True,
                                "read": True,
                                "grep": True,
                                "glob": True,
                                "list": True,
                                "patch": True,
                                "todowrite": True,
                                "todoread": True,
                                "webfetch": False,
                                "tavily_*": False,
                                "finance_*": False,
                                "pexels_*": False
                            },
                            "prompt": "You are a software engineer. Your task is to build the project, a static site, or a blog post based on the plan. Strictly follow the plan step-by-step; do not take any extra steps. Do not ask again for confirmation, just do it your way. Your first step should be reviewing all markdown files (*.md or financial/*.md or general/*.md) to get the necessary content. Your code must be written into files. Any assets you use must be loaded from local or occur in search results. Ask the developer for junk tasks if needed. Do not write code with placeholders only. Always ask the fin-analyst for data gathering, avoid doing it yourself. USE EXACT data and numbers from the search result from fin-analyst, never make up anything outside them. Make sure the output is clean and ready to be published. css, js files should be clearly declared and included in the project. Your final output should be short, and talk about what you have done (no code explanation in detail is required)."
                        },
                        "fin-analyst": {
                            "description": "Financial expert for stock, equities, crypto, and macro; runs advanced analysis, and provides actionable investment insights.",
                            "mode": "subagent",
                            "temperature": 0.1,
                            "tools": {
                                "write": True,
                                "edit": True,
                                "finance_*": True,
                                "tavily_*": False,
                                "pexels_*": False,
                                "todowrite": True,
                                "todoread": True
                            },
                            "prompt": "You are 'Fin Analyst', a professional financial expert who:\n- Calls Finance MCP tools to fetch equities, crypto, and macro data along with the context.\n **Make sure** to fetch structured data via Finance MCP tools (don't use any web search like Tavily), current time is priority. For data, *always use* the financial-datasets for data, don't look up to others websites. Never make up facts. \n- Stores results in `financial/data/*.json`.\n- Runs quant, valuation, and portfolio methods; generates Python when useful.\n- Provides buy/sell/hold recommendations with reasoning, scenarios, and Markdown reports.\n\nDeliverables: `financial/plan.md`, `financial/data/*.json`, `financial/analysis.md`, `financial/recommendations.md`.\n\nWorkflow: define scope → fetch datasets → fetch context → store raw → analyze → report → recommend.\n\nReturn in chat: summary of findings, created files, caveats."
                        },
                        "developer": {
                            "description": "Turn prepared content into a visually stunning, responsive, accessible report/website, page by page and section by section, using HTML/CSS/JS.",
                            "mode": "subagent",
                            "temperature": 0.2,
                            "tools": {
                                "write": True,
                                "edit": True,
                                "read": True,
                                "grep": True,
                                "glob": True,
                                "list": True,
                                "patch": True,
                                "bash": True,
                                "finance_*": False,
                                "tavily_search": False,
                                "tavily_fetch": False,
                                "todowrite": True,
                                "todoread": True,
                                "pexels_*": False
                            },
                            "permission": {
                                "edit": "allow"
                            },
                            "prompt": "You are the **Developer**. Build a polished, multi-page, responsive site/report from the prepared content. If you want some data/number, only use the research result from fin-analyst, don't make up anything outside them. Use ONLY **HTML5, Tailwind CSS, and JavaScript** (no frameworks or build tools). Aim for an elegant, modern aesthetic.\n\nInput: `content/*.md`, `content/images.json`, `content/data/*.json`.\nOutput: `reports/*.html`, `assets/styles.css`, `assets/main.js`, optional `docs/styleguide.html`, `reports/README.md`.\n\nWorkflow: parse outline → map pages → build pages → apply styles → add scripts → validate accessibility/responsiveness.\n\nReturn in chat: plan, file tree, next steps."
                        }
                    },
                    "permission": {
                        "*": "allow"
                    },
                    "mcp": mcp_config,
                    "autoupdate": False
                }

            with open(config_path, "w") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error updating config: {e}")

        if repeat_interval <= 0:
            logger.info("Config updated, stopping config update task")
            break

        await asyncio.sleep(repeat_interval)
        

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