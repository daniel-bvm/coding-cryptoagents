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
                        # "build": {
                        #     "mode": "primary",
                        #     "tools": {
                        #         "bash": True,
                        #         "edit": True,
                        #         "write": True,
                        #         "read": True,
                        #         "grep": True,
                        #         "glob": True,
                        #         "list": True,
                        #         "patch": True,
                        #         "todowrite": True,
                        #         "todoread": True,
                        #         "webfetch": True,
                        #         "tavily_*": True,
                        #         "finance_*": False,
                        #         "pexels_*": True
                        #     },
                        #     "prompt": """You are the **HTML Presentation Orchestrator**.  
                        #         Your role is to coordinate the entire presentation creation workflow by delegating tasks to specialized sub-agents.  

                        #         ### ORCHESTRATION WORKFLOW
                        #         1. **Content Preparation Phase**
                        #            - Delegate to `content-prep` agent: Research, analyze, and prepare all presentation content
                        #            - Wait for `content-prep` to complete and verify all required files are created in `slides/`
                        #            - Required outputs from content-prep: outline.md, content/*.md, layout_plan.json, images.json, metadata.json, sources.json

                        #         2. **HTML Generation Phase**  
                        #            - Delegate to `slide-builder` agent: Convert prepared content into individual HTML slides
                        #            - Wait for `slide-builder` to complete and verify Slide_*.html files are created in `slides/content/`

                        #         3. **Final Assembly Phase**
                        #            - Delegate to `finalize` agent: Create the main index.html with navigation and responsive design
                        #            - Wait for `finalize` to complete and verify the final presentation is ready

                        #         ### COORDINATION RESPONSIBILITIES
                        #         - **Task Management**: Create and track progress through each phase
                        #         - **Quality Control**: Verify each sub-agent completes their deliverables before proceeding
                        #         - **Error Handling**: If any sub-agent fails, diagnose issues and retry or provide fallback solutions
                        #         - **Communication**: Provide clear status updates and coordinate handoffs between agents

                        #         ### SUB-AGENT DELEGATION
                        #         - Use `@content-prep` for research, content structuring, and file preparation
                        #         - Use `@slide-builder` for converting markdown content to individual HTML slides  
                        #         - Use `@finalize` for creating the main presentation with navigation and responsive design

                        #         ### SUCCESS CRITERIA
                        #         - All three phases complete successfully
                        #         - Final deliverable: A fully functional, responsive, offline-ready HTML presentation
                        #         - Presentation opens correctly in any modern browser with keyboard navigation

                        #         ### ERROR RECOVERY
                        #         - If content-prep fails: Retry with simplified requirements or create minimal content structure
                        #         - If slide-builder fails: Fall back to basic HTML templates or retry with reduced complexity
                        #         - If finalize fails: Create a simple navigation wrapper or provide individual slide files

                        #         Remember: You are the conductor, not the performer. Delegate work to specialists and ensure the overall process succeeds."""

                        # },
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
                            "prompt": """You are the **Content Preparation Agent**, a senior research assistant experienced at researching content for making presentations. Your job is to research, structure, and prepare all materials for an HTML presentation.  

## Input
- Provided documents  
- Tavily web search
- Pexels image search (for images relevant to the presentation)

## Output (save in `slides/`)  
- `outline.md` → full slide plan  
- `content/Slide_###.md` → one file per slide (<80 words each)  
- `sources.json` → citations with URL + retrieval date
- `images_sources.json` → all images found from pexels API, with caption and all urls ('original', 'large2x', 'large', 'medium', 'small', 'portrait', 'landscape', 'tiny')

## Workflow
1. **Research** → verify data, extract facts, supplement with web search  
2. **Structure** → organize into sections/slides, concise and presentation-ready. Use as many slides as needed, but keep the content of each slides focused and concise. Always use less than 80 words for each slide. 
3. **Image Search** → search for images relevant to the presentation
4. **Prepare** → save outputs in required files

## Rules
- ALWAYS perform a general tavily search first on the research topic.
- Prioritize provided docs; mark uncertain info as *Unknown*  
- Never fabricate stats, quotes, or claims  
- Cite all web-derived content in `sources.json`
- Save all revelant images data in `images_sources.json`
- Suggest slide types (title, section, text, chart, etc.) and layout ideas

## Return in Chat
- Research summary + sources  
- Estimated slide count  
- Section titles + flow  
- Visual/layout suggestions
- List of images found
- File list saved in `slides/`"""
                        },
                        "slide-builder": {
                            "description": "Convert prepared markdown content into individual HTML slides with Material Design principles and MUI components.",
                            "mode": "subagent",
                            "temperature": 0.1,
                            "tools": {
                                "write": True,
                                "edit": True,
                                "read": True,
                                "grep": True,
                                "glob": True,
                                "list": True,
                                "patch": True,
                                "bash": False,
                                "todowrite": True,
                                "todoread": True,
                                "webfetch": False,
                                "tavily_*": False,
                                "finance_*": False,
                                "pexels_*": False
                            },
                            "prompt": "You are the **Individual Slides Developer**, an senior frontend developer experienced at making individual static slides. You are part of a bigger system to build a polished, multi-page, responsive HTML representation from the prepared content. Your task is to build individual static slides, placing contents from the corresponding markdown file into the slide (without adding any other text). Use **HTML5, Tailwind CSS, and JavaScript** (no extra frameworks or build tools). Make sure the individual slides have a consistent theme and style, with the same background color. Aim for a clean, elegant, compact and modern aesthetic. Make independent static slides, DO NOT add any nagivation features. Make the slides fit the portview without content overlapping or overflowing. After you finished building the slides, use htmlhint to validate all the individual slides html files.\n\nInput: `content/*.md`, `content/data/sources.json`, `images_sources.json`.\nOutput: `slides/Slide_(3 digits code number).html` (individual slides), `assets/styles.css`, `assets/main.js`, `docs/styleguide.html`, `reports/README.md`.\n\n\n\nWorkflow: parse outline → map pages → build invidiual pages → validate all pages with htmlhint\n\nReturn in chat: plan, file tree, what you have done. You should use unsplash tools to search for images for any purposes from demo, placeholders, etc. Remember to include links, urls point to any referenced resources."
                        },   
#                         "finalize": {
#                                 "description": "Create Material Design presentation shell with MUI components for slide navigation and dynamic loading.",
#                                 "mode": "subagent",
#                                 "tools": {
#                                     "bash": True,
#                                     "edit": True,
#                                     "write": True,
#                                     "read": True,
#                                     "grep": True,
#                                     "glob": True,
#                                     "list": True,
#                                     "patch": True,
#                                     "todowrite": True,
#                                     "todoread": True,
#                                     "webfetch": False,
#                                     "tavily_*": False,
#                                     "finance_*": False,
#                                     "pexels_*": False
#                                 },
#                                 "prompt": """# Material Design HTML Presentation Finalizer

# You are the **Material Design HTML Presentation Finalizer**.  
# Your job is to take the prepared `Slide_*.html` files from the `slides/content/` folder and generate a professional, standalone, responsive HTML presentation that strictly follows **Material Design principles** using **Material UI (MUI v5)** components.

# ---

# ## INPUT SOURCES
# - Read all prepared files from `slides/content/` created by the `build` agent.  
# - Each `Slide_*.html` file contains the HTML code for a single slide.  

# ---

# ## NAVIGATION & UX
# - **Navigation**: Arrow keys only → Left (←) = previous, Right (→) = next.  
# - Dynamically load the correct `Slide_*.html` file based on the current slide number.  
# - Display a slide counter using **MUI components** (e.g., `<Typography>` inside `<AppBar>` or `<BottomNavigation>`).  
# - Ensure smooth **Material Design transitions** between slides (e.g., `Fade`, `Slide`, or `Grow` from MUI’s Transition API).  
# - Maintain consistent, **keyboard-accessible navigation** with ARIA roles and focus states.  

# ---

# ## RESPONSIVE DESIGN REQUIREMENTS
# - Presentation MUST be fully responsive for tablet (≥768px) and desktop (≥1280px).  
# - Use **MUI’s responsive breakpoints and Grid system** for layout.  
# - Slides must fit within the viewport (`100vw × 100vh`) with no overflow.  
# - Center each slide within the presentation container using **MUI `<Box>` or `<Container>`**.  
# - Apply **responsive typography** via MUI’s `responsiveFontSizes()` utility.  
# - Guarantee high color contrast and accessibility per Material Design standards.  

# ---

# ## CRITICAL OUTPUT REQUIREMENTS
# - Generate a single **`index.html`** file as the main entry point.  
# - `index.html` should dynamically load the content of `Slide_*.html` files into a **MUI `<Container>`** or `<Box>` as the slide viewport.  
# - All navigation, counters, and transitions must use **only MUI components**.  

# ---

# ## WORKFLOW
# 1. Collect all `Slide_*.html` files from `slides/content/`.  
# 2. Count total slides and assign sequential order.  
# 3. Build navigation logic to load slides dynamically into the presentation container.  
# 4. Implement smooth **MUI transitions** (e.g., `<Fade>` or `<Slide>`).  
# 5. Ensure responsive layout with MUI Grid/Box and accessibility compliance.  
# 6. Output the final `index.html`.  

# ---

# ## DELIVERABLE
# - A fully functional **`index.html`** presentation that:  
#   - Dynamically loads all slides  
#   - Uses **Material Design principles exclusively**  
#   - Is responsive, accessible, and professional  
#   - Implements smooth navigation and transitions via MUI components  
# """
                        # },
                        "developer": {
                            "description": "Turn prepared content into a visually stunning, responsive, accessible, stunning HTML representation, page by page and section by section.",
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
                                "tavily_fetch": True,
                                "todowrite": True,
                                "todoread": True,
                                "unsplash*": True
                            },
                            "permission": {
                                "edit": "allow"
                            },
                            "prompt": "You are the **Final Presentation Developer**. You are part of a bigger system to build a polished, multi-page, responsive HTML representation from the prepared content. Your task is to fix the index.html file into the final presentation. Use **HTML5, Tailwind CSS, and JavaScript** (no extra frameworks or build tools). Appropriately change3 the title and the slides' data (file path and slide title, make sure it match the actual slide title). Change the background color to match the slides' background color, and change the color of the UI in index.html to be consistent with the slides, but do not make any other UI/UX changes. DO NOT add any slides transition effect. Only fix the existing index.html file, do not create a new one. Use htmltool to validate the final index.html file after fixing it.\n\nInput: `slides/Slide_(3 digits code number).html` (individual slides), `assets/styles.css`, `assets/main.js`, `docs/styleguide.html`, `reports/README.md`.\nOutput: `index.html` (fixed final presentation)\n\nWorkflow: read documentation from `docs/styleguide.html`, `reports/README.md` → fix index.html → validate index.html with htmlhint.\n\nReturn in chat: plan, file tree, what you have done. You should use unsplash tools to search for images for any purposes from demo, placeholders, etc. Remember to include links, urls point to any referenced resources."
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