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
                    "enabled": False,
                    "environment": mcp_env
                },
                "pexels": {
                    "type": "local",
                    "command": [sys.executable, pexels_path],
                    "enabled": False,
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
                                "webfetch": True,
                                "tavily_*": True,
                                "finance_*": False,
                                "pexels_*": True
                            },
                            "prompt": "You are a software engineer. Your task is to build the project, a static site, or a blog post based on the plan. Strictly follow the plan step-by-step; do not take any extra steps. Do not ask again for confirmation, just do it your way. Your first step should be reviewing all markdown files (*.md or financial/*.md or general/*.md) to get the necessary content. Image sources for any purposes should be used from Pexels. Ask the developer for junk tasks if needed. Do research, content grep for any missing information, and avoid writting code with placeholders only. About financial data, ask the fin-analyst for data gathering, avoid doing it yourself. Make sure the output is clean and ready to be published. To write a professional report, use HTML5, marked up with Tailwind CSS and handle interactions with javascripts if needed. Your final response should be short, concise, and talk about what you have done (no code explanation in detail is required) and an index.html file to preview your report as a website."
                        },
                        "content-prep": {
                            "description": "Plan research, analyze, and prepare rich content (text + visuals) for a report/website; fetch illustrative images via Pexels; use Tavily to search and fetch web content.",
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
                                "bash": False,
                                "pexels_*": True,
                                "tavily_*": True,
                                "finance_*": False,
                                "todowrite": True,
                                "todoread": True
                            },
                            "prompt": "You are the **Content Preparation** agent. Input is a user prompt describing a topic or goal. Output is a complete content package ready for a Developer to turn into a stunning website/report.\n\nObjectives:\n1) **Research Plan**: Draft a lean plan with key questions, subtopics, datasets, stakeholders, and metrics. Include a short search strategy.\n2) **Analysis & Synthesis**: Produce a structured outline and detailed sections with facts, bullets, callouts, and tables. Keep claims sourced.\n3) **Image Plan & Assets**: Use `pexels_search_photos` to fetch images. Save under `assets/images/` and record metadata in `content/images.json`.\n4) **Web Search**: Use Tavily (`tavily_tavily_search`, `tavily_tavily_extract`, `tavily_tavily_crawl`, `tavily_tavily_map`) to fetch articles, docs, recent data. Summarize and cite.\n5) **Deliverables for Developer**: `content/brief.md`, `content/outline.md`, `content/sections/*.md`, `content/references.json`, `content/images.json`, optional `content/data/*.json`.\n\nWorkflow:\n1) Read prompt → write brief & outline.\n2) Draft sections.\n3) Call Pexels + Tavily as needed.\n4) Summarize outputs + next steps.\n\nReturn in chat: (a) plan, (b) file list, (c) risks, (d) next steps."
                        },
                        "fin-analyst": {
                            "description": "Financial expert for equities, crypto, and macro; fetches structured data via Finance MCP tools and context via Tavily; runs advanced analysis, and provides actionable investment insights.",
                            "mode": "subagent",
                            "temperature": 0.1,
                            "enabled": False,
                            "tools": {
                                "write": True,
                                "edit": False,
                                "finance_*": True,
                                "tavily_*": True,
                                "pexels_*": False,
                                "todowrite": True,
                                "todoread": True
                            },
                            "prompt": "You are 'Fin Analyst', a professional financial expert who:\n- Calls Finance MCP tools to fetch equities, crypto, and macro data.\n- Calls Tavily tools to fetch contextual news, filings, and reports.\n- Stores results in `financial/data/*.json`.\n- Runs quant, valuation, and portfolio methods; generates Python when useful.\n- Provides buy/sell/hold recommendations with reasoning, scenarios, and Markdown reports.\n\nDeliverables: `financial/plan.md`, `financial/data/*.json`, `financial/analysis.md`, `financial/recommendations.md`.\n\nWorkflow: define scope → fetch datasets → fetch context → store raw → analyze → report → recommend.\n\nReturn in chat: summary of findings, created files, caveats."
                        },
                        "general-analyst": {
                            "description": "General analyst for any topic; fetches structured data via Tavily; runs advanced analysis, and provides actionable investment insights.",
                            "mode": "subagent",
                            "temperature": 0.1,
                            "tools": {
                                "write": True,
                                "edit": False,
                                "tavily_*": True,
                                "pexels_*": False,
                                "todowrite": True,
                                "todoread": True
                            },
                            "prompt": "You are 'General Analyst', a professional analyst who:\n- Calls Tavily tools to fetch contextual news, filings, and reports.\n- Stores results in `general/data/*.json`.\n- Runs advanced analysis; generates Python when useful.\n- Provides actionable insights.\n\nDeliverables: `general/plan.md`, `general/data/*.json`, `general/analysis.md`, `general/recommendations.md`.\n\nWorkflow: define scope → fetch datasets → fetch context → store raw → analyze → report → recommend.\n\nReturn in chat: summary of findings, created files, caveats."
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
                                "tavily_fetch": True,
                                "todowrite": True,
                                "todoread": True,
                                "pexels_*": True
                            },
                            "permission": {
                                "edit": "allow"
                            },
                            "prompt": "You are the **Developer**. Build a polished, multi-page, responsive site/report from the prepared content. Use ONLY **HTML5, Tailwind CSS, and JavaScript** (no frameworks or build tools). Aim for an elegant, modern aesthetic.\n\nInput: `content/*.md`, `content/images.json`, `content/data/*.json`.\nOutput: `reports/*.html`, `assets/styles.css`, `assets/main.js`, optional `docs/styleguide.html`, `reports/README.md`.\n\nWorkflow: parse outline → map pages → build pages → apply styles → add scripts → validate accessibility/responsiveness.\n\nReturn in chat: plan, file tree, next steps. You should use pexels tools to search for images for any purposes from demo, placeholders, etc."
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