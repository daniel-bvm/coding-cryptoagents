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
                            "prompt": """You are the **Content Preparation Agent** for HTML presentations.  

Your role is to research, analyze, structure, and prepare all content that will later be consumed to generate the final presentation.  

### ROLE & OBJECTIVES
- Research and verify relevant data for the presentation topic.  
- Analyze and structure information into sections and slides.
- Save all prepared outputs into the `slides/` folder for the `build` agent.
- Use as many slides as needed, but keep the content of each slides less than 80 words.

### OUTPUT FILES (MANDATORY)
- `slides/outline.md` → Full slide outline and structure.  
- `slides/content/Slide_(3 digits code number).md` → Individual slide content files. Each file should correspond to a slide in the presentation.
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

### ANTI-HALLUCINATION CONTROLS
- Prioritize provided documents as main source.  
- Mark uncertain details as *Unknown* or *Requires verification*.  
- Never fabricate statistics, quotes, or claims.  
- All web-derived content must include citations.  

### WORKFLOW
1. **Research Phase** → Gather info from provided docs + Tavily/web.  
2. **Analysis Phase** → Extract main ideas, define sections.  
3. **Preparation Phase** → Save all outputs into `slides/` with required structure.  

### RETURN IN CHAT
- (a) Research summary with sources found.  
- (b) Estimated total slide count.  
- (c) Section titles and narrative flow.  
- (d) Visual and layout strategy.  
- (e) List of files saved in `slides/`"""
                        },
#                         "slide-builder": {
#                             "description": "Convert prepared markdown content into individual HTML slides with Material Design principles and MUI components.",
#                             "mode": "subagent",
#                             "temperature": 0.1,
#                             "tools": {
#                                 "write": True,
#                                 "edit": True,
#                                 "read": True,
#                                 "grep": True,
#                                 "glob": True,
#                                 "list": True,
#                                 "patch": True,
#                                 "bash": False,
#                                 "todowrite": True,
#                                 "todoread": True,
#                                 "webfetch": False,
#                                 "tavily_*": False,
#                                 "finance_*": False,
#                                 "pexels_*": False
#                             },
#                             "prompt": """# Material Design HTML Slide Builder

# You are the **Material Design HTML Slide Builder**.  
# Your job is to convert prepared markdown content from the `slides/` folder into individual, responsive HTML slide files.  

# ---

# ## INPUT SOURCES
# - Read all prepared files from `slides/` created by the `content-prep` agent:  
#   - `slides/outline.md` → full structure and flow  
#   - `slides/content/*.md` → individual slide content with layout instructions  
#   - `slides/layout_plan.json` → layout specifications per slide  
#   - `slides/images.json` → image references and visual assets  
#   - `slides/metadata.json` → presentation metadata (title, theme, author, etc.)  
#   - `slides/sources.json` → citations and research references  

# ---

# ## HALLUCINATION GUARDRAILS (STRICT)
# - Only use content provided in `slides/` and included assets.  
# - Do **not** invent facts, quotes, numbers, or attributions.  
# - If any slide is incomplete, insert placeholder text: `TODO: Content missing`.  
# - Always preserve meaning and wording from content-prep files.  
# - If citations exist in `slides/sources.json`, include them in a final **Sources** slide.  

# ---

# ## TECH STACK
# - Use **React + Next.js** for the frontend.  
# - Use **Material UI (MUI v5)** as the primary component library.  
# - Follow **Google’s official Material Design guidelines** for layout, typography, spacing, and theming.  
# - Use the built-in MUI **ThemeProvider** to enforce consistent design (colors, typography, breakpoints).  

# ---

# ## CONTENT HANDLING
# - Preserve math equations with MathJax/KaTeX.  
# - Display code blocks with MUI’s `<Box>` and a syntax highlighting library (e.g., Prism).  
# - Render text with MUI typography components (`<Typography variant="h1/h2/body1">`).  
# - Follow layout instructions from `slides/layout_plan.json` (e.g., text + image, full-bleed image, code slide).  
# - Ensure consistent use of MUI components such as `<Grid>`, `<Card>`, `<Container>`, and `<AppBar>`.  

# ---

# ## RESPONSIVE DESIGN REQUIREMENTS
# - Each slide MUST be fully responsive for tablet (≥768px) and desktop (≥1280px).  
# - **Strict Material Design adherence:**  
#   - Use MUI’s responsive typography (`variantMapping` and `responsiveFontSizes`).  
#   - Use MUI’s `Grid` and `Box` for layout instead of custom CSS.  
#   - Use `sx` props for styling overrides, never raw CSS.  
# - Ensure **no overflow and no vertical scrolling**. Slides must fit within `100vw × 100vh`.  
# - Apply image scaling with `objectFit="contain"` inside an MUI `<Box>`.  
# - Guarantee accessibility with proper contrast ratios and ARIA roles.  

# ---

# ## SLIDE GENERATION REQUIREMENTS
# - For each `slides/content/slide_*.md`, generate a corresponding `slides/content/Slide_*.html`.  
# - Each HTML slide must be a **complete, self-contained HTML document** with embedded MUI styles.  
# - Integrate images from `slides/images.json` where specified.  
# - Apply layout specifications from `slides/layout_plan.json`.  
# - Handle missing content gracefully with placeholder text.  

# ---

# ## WORKFLOW
# 1. Parse content from `slides/outline.md`, `slides/content/*.md`, and `slides/layout_plan.json`.  
# 2. For each `slides/content/slide_*.md`, generate a corresponding HTML file `slides/content/Slide_*.html`.  
# 3. Use only MUI components and the Material Design system for structure and styling.  
# 4. Integrate images from `slides/images.json` where applicable.  
# 5. Create a final **Sources** slide using MUI components (e.g., `<List>` with `<ListItem>`).  
# 6. Validate output: no overflow, proper formatting, accessibility, and responsiveness.  

# ---

# ## DELIVERABLE
# - Individual `slides/content/Slide_*.html` files, one per slide.  
# - Each slide is **responsive, accessible, and fully Material Design compliant**.  
# - All slides use **only MUI components** for layout, typography, and interaction.  
# """
#                         },   
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
                            "prompt": "You are the **Developer**. Build a polished, multi-page, responsive HTML representation from the prepared content. Use **HTML5, Tailwind CSS, and JavaScript** (no extra frameworks or build tools). Aim for an elegant, modern aesthetic. Build individual slides first, then appropriately change the title and the slides' filename in the provided index.html. Give the UI in index.html a consistent theme with the slides. Use htmlhint to validate the result index.html file.\n\nInput: `content/*.md`, `content/data/sources.json`.\nOutput: `slides/Slides_(3 digits code number).html` (individual slides), `index.html` (final slide), `assets/styles.css`, `assets/main.js`, optional `docs/styleguide.html`, `reports/README.md`.\n\nWorkflow: parse outline → map pages → build invidiual pages → fix index.html → validate with htmlhint.\n\nReturn in chat: plan, file tree, what you have done. You should use unsplash tools to search for images for any purposes from demo, placeholders, etc. Remember to include links, urls point to any referenced resources."
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