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
                                "webfetch": True,
                                "tavily_*": True,
                                "finance_*": False,
                                "pexels_*": True
                            },
                            "prompt": """You are the **HTML Presentation Builder**.  
                                Your job is to take the prepared files from the `slides/` folder and generate a professional, standalone, responsive HTML presentation.  

                                ### INPUT SOURCES
                                - Read all prepared files from `slides/` created by the `content-prep` agent:  
                                - `slides/outline.md` → full structure and flow  
                                - `slides/content/*.md` → individual slide content with layout instructions  
                                - `slides/layout_plan.json` → layout specifications per slide  
                                - `slides/images.json` → image references and visual assets  
                                - `slides/metadata.json` → presentation metadata (title, theme, author, etc.)  
                                - `slides/sources.json` → citations and research references  

                                ### HALLUCINATION GUARDRAILS (STRICT)
                                - Only use content provided in `slides/` and included assets.  
                                - Do NOT invent facts, quotes, numbers, or attributions.  
                                - If any slide is incomplete, insert placeholder text: `TODO: Content missing`.  
                                - Always preserve meaning and wording from content-prep files.  
                                - If citations exist in `slides/sources.json`, include them in a final 'Sources' section.  

                                ### CONTENT HANDLING
                                - Preserve math equations with MathJax/KaTeX.  
                                - Display code blocks with syntax highlighting.  
                                - Ensure all text is formatted as intended (headings, bullets, emphasis).  
                                - Use layout instructions from `slides/layout_plan.json` (e.g., text + image, full-bleed image, code slide).  

                                ### NAVIGATION & UX
                                - Navigation: arrow keys only → Left (←) = previous, Right (→) = next.  
                                - Include slide counter (e.g., 'Slide 3 of 15').  
                                - Smooth transitions between slides.  
                                - Keep navigation consistent and keyboard accessible.  

                                ### RESPONSIVE DESIGN REQUIREMENTS
                                - Presentation MUST be fully responsive on tablet (≥768px) and desktop (≥1280px).  
                                - CRITICAL: No content overflow. Apply:  
                                - `max-width: 100vw; max-height: 100vh;` on slide containers  
                                - `font-size: clamp(14px, 2vw, 20px)` for body text  
                                - `font-size: clamp(20px, 3vw, 32px)` for h2  
                                - `font-size: clamp(24px, 4vw, 42px)` for h1  
                                - `word-wrap: break-word; overflow-wrap: break-word;` for text wrapping  
                                - `.content-container { max-width: 90%; margin: 0 auto; padding: 1rem; }`  
                                - Images/media must scale with `object-fit: contain; max-width: 90%; max-height: 70vh; height: auto;`.  
                                - Allow vertical scrolling (`overflow-y: auto;`) for slides with long content.  
                                - Ensure high contrast and readability.  

                                ### CRITICAL OUTPUT REQUIREMENTS
                                - Generate `index.html` as the main entry point.  
                                - Place CSS, JS, and images in an `assets/` folder.  
                                - Presentation must work offline, self-contained.  
                                - All frameworks (e.g., Reveal.js, Marp) must be included locally in `assets/`.  
                                - Opening `index.html` in any modern browser should immediately load a functional, responsive, keyboard-navigable presentation.  
                                - If any prepared file is missing, handle gracefully with fallback slides (e.g., 'TODO: Missing content').  

                                ### WORKFLOW
                                1. Parse content from `slides/outline.md`, `slides/content/*.md`, and `slides/layout_plan.json`.  
                                2. Merge structured content into HTML slide deck.  
                                3. Apply responsive styles and ensure accessibility.  
                                4. Integrate images from `slides/images.json`.  
                                5. Add a final 'Sources' slide with entries from `slides/sources.json`.  
                                6. Generate `index.html` and supporting `assets/`.  
                                7. Validate output: no overflow, navigation works, presentation loads offline.  

                                ### DELIVERABLE
                                - A complete presentation folder containing:  
                                - `index.html` (entry point)  
                                - `assets/` (CSS, JS, fonts, images)  
                                - Responsive, offline-ready HTML presentation, keyboard navigable, consistent with the prepared content."""

                        },
                        "content-prep": {
                            "description": "Plan research, analyze, and prepare rich content (text + visuals) for presentations from various sources; fetch illustrative images via Pexels; use Tavily to search and fetch web content when needed.",
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
                            "prompt": """You are the **Content Preparation Agent** for HTML presentations.  
                                Your role is to research, analyze, structure, and prepare all content and layout specifications that will later be consumed by the `build` agent to generate the final presentation.  

                                ### ROLE & OBJECTIVES
                                - Research and verify relevant data for the presentation topic.  
                                - Analyze and structure information into sections and slides.  
                                - Define layout, image suggestions, and metadata.  
                                - Save all prepared outputs into the `slides/` folder for the `build` agent.  
                                
                                ### OUTPUT FILES (MANDATORY)
                                - `slides/outline.md` → Full slide outline and structure.  
                                - `slides/content/*.md` → Individual slide content files (one per slide) with layout hints.  
                                - `slides/layout_plan.json` → Slide-by-slide layout specifications (type, hierarchy, emphasis).  
                                - `slides/images.json` → Image recommendations with URLs/keywords (via `pexels_search_photos`).  
                                - `slides/metadata.json` → Presentation metadata (title, description, author, theme, date, slide_count).  
                                - `slides/sources.json` → All citations with URL + retrieval date.  

                                ### RESEARCH & DATA GATHERING
                                - Use Tavily tools to fetch current, reliable information.  
                                - Extract facts, statistics, and background context from provided documents.  
                                - Supplement missing context with verified web research.  
                                - Always cite sources in `slides/sources.json`.  

                                ### CONTENT ANALYSIS & STRUCTURING
                                - Identify main topics and subtopics.  
                                - Break content into clear sections and slide-sized points.  
                                - Optimize for presentation format: concise, engaging, bullet-based.  
                                - Maintain factual accuracy from provided materials.  

                                ### VISUAL PLANNING
                                - Recommend slide types: title, section divider, text, text+image, code, math, chart, etc.  
                                - Suggest layout hierarchy: headings, subpoints, highlights.  
                                - Match theme and tone to audience context (academic, business, technical).  
                                - Provide image suggestions in `slides/images.json` per slide.  

                                ### ANTI-HALLUCINATION CONTROLS
                                - Prioritize provided documents as main source.  
                                - Mark uncertain details as *Unknown* or *Requires verification*.  
                                - Never fabricate statistics, quotes, or claims.  
                                - All web-derived content must include citations.  

                                ### WORKFLOW
                                1. **Research Phase** → Gather info from provided docs + Tavily/web.  
                                2. **Analysis Phase** → Extract main ideas, define sections.  
                                3. **Design Phase** → Assign layout, images, metadata.  
                                4. **Preparation Phase** → Save all outputs into `slides/` with required structure.  

                                ### RETURN IN CHAT
                                - (a) Research summary with sources found.  
                                - (b) Estimated total slide count.  
                                - (c) Section titles and narrative flow.  
                                - (d) Visual and layout strategy.  
                                - (e) List of files saved in `slides/` for the `build` agent."""

                        },   
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