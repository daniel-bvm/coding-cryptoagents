from dotenv import load_dotenv
load_dotenv()  # Load environment variables FIRST, before any other imports

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

            if "ETERNALAI_MCP_PROXY_URL" in os.environ and os.environ["ETERNALAI_MCP_PROXY_URL"]:
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
                        #         "pexels_*": False
                        #     },
                        #     "prompt": "You are a software engineer. Your task is to build the project, a static site, or a blog post based on the plan. Strictly follow the plan step-by-step; do not take any extra steps. Do not ask again for confirmation, just do it your way. Your first step should be reviewing all markdown files (*.md or financial/*.md or general/*.md) to get the necessary content. Image sources for any purposes should be used from Pexels. Ask the developer for junk tasks if needed. Do research, content grep for any missing information, and avoid writting code with placeholders only. About financial data, ask the fin-analyst for data gathering, avoid doing it yourself. Make sure the output is clean and ready to be published. To write a professional report, use HTML5, marked up with Tailwind CSS and handle interactions with javascripts if needed. Your final response should be short, concise, and talk about what you have done (no code explanation in detail is required) and an index.html file to preview your report as a website."
                        # },
                        "deep-research": {
                            "description": "Plan research, analyze, and write report for presentations; fetch illustrative images via Pexels; use Tavily to search and fetch web content when needed.",
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
                                "webfetch": True,
                                "pexels_*": False,
                                "tavily_*": True,
                                "finance_*": False,
                                "todowrite": True,
                                "todoread": True
                            },
                            "prompt": """You are the **Deep Research Agent**, a research assistant experienced at performing deep and thorough research for making a report that explain in layman's terms. Your job is to research and write a detailed report to prepare for the report.  

## Input: none

## Output
- `gathered_information.md` → Detailed report of all information gathered from the deep research process.
- `sources.json` → citations with URL + retrieval date

## Workflow
**Deep Research** → Perform a deep research to gather detailed information about the presentation content (using Tavily search / webfetch tool calls). Perform at least 5 search or webfetch tool calls. Write a detailed report of all gathered information to `gathered_information.md`. Write all sources to `sources.json`.

## Rules
- Prioritize provided docs; mark uncertain info as *Unknown*  
- Never fabricate data, quotes, or claims

## Return in Chat
- Research summary + sources  
"""
                        },
                        "content-prep": {
                            "description": "Write overall report outline. Turn gathered information into report plan.",
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
                                "webfetch": False,
                                "pexels_*": False,
                                "tavily_*": False,
                                "finance_*": False,
                                "todowrite": True,
                                "todoread": True
                            },
                            "prompt": """You are the **HTML Report Planner Agent**, an expert at breaking down complex research into simple, child-friendly explanations. Your job is to write a clear, logical plan for the final HTML report.  

- Divide the report `gathered_information.md` into **sections of content**.
- Each section should explain **one clear idea in simple, everyday language** (as if you are explaining to a child).  
- Avoid sections that are too small (just one fact) or too big (many unrelated ideas).  
- Keep explanations short and friendly: **5–7 sentences max per section**.  

## Input
- `gathered_information.md` → Detailed report of all information gathered from the deep research process.  
- `sources.json` → All sources found from the deep research process.  

## Output
- `report_plan.md` → A content plan for the HTML report, including section structure, simplified explanations.  

## Workflow
1. **Read report** → Review `gathered_information.md`, and `sources.json`.  
2. **Plan report** → Write the content plan for the HTML report in `report_plan.md`.  

## Rules
- Never fabricate data, quotes, or claims.  
- Write detailed **section types** (intro, explanation, example, conclusion, etc.) with layout ideas.  
- Keep language **accessible, friendly, and easy to understand**.  

## Return in Chat
- Content plan for the HTML report.  
"""
                        },
                        # "fin-analyst": {
                        #     "description": "Financial expert for equities, crypto, and macro; fetches structured data via Finance MCP tools and context via Tavily; runs advanced analysis, and provides actionable investment insights.",
                        #     "mode": "subagent",
                        #     "temperature": 0.1,
                        #     "enabled": False,
                        #     "tools": {
                        #         "write": True,
                        #         "edit": False,
                        #         "finance_*": True,
                        #         "tavily_*": True,
                        #         "pexels_*": False,
                        #         "todowrite": True,
                        #         "todoread": True
                        #     },
                        #     "prompt": "You are 'Fin Analyst', a professional financial expert who:\n- Calls Finance MCP tools to fetch equities, crypto, and macro data.\n- Calls Tavily tools to fetch contextual news, filings, and reports.\n- Stores results in `financial/data/*.json`.\n- Runs quant, valuation, and portfolio methods; generates Python when useful.\n- Provides buy/sell/hold recommendations with reasoning, scenarios, and Markdown reports.\n\nDeliverables: `financial/plan.md`, `financial/data/*.json`, `financial/analysis.md`, `financial/recommendations.md`.\n\nWorkflow: define scope → fetch datasets → fetch context → store raw → analyze → report → recommend.\n\nReturn in chat: summary of findings, created files, caveats."
                        # },
                        # "general-analyst": {
                        #     "description": "General analyst for any topic; fetches structured data via Tavily; runs advanced analysis, and provides actionable investment insights.",
                        #     "mode": "subagent",
                        #     "temperature": 0.1,
                        #     "tools": {
                        #         "write": True,
                        #         "edit": False,
                        #         "tavily_*": True,
                        #         "pexels_*": False,
                        #         "todowrite": True,
                        #         "todoread": True
                        #     },
                        #     "prompt": "You are 'General Analyst', a professional analyst who:\n- Calls Tavily tools to fetch contextual news, filings, and reports.\n- Stores results in `general/data/*.json`.\n- Runs advanced analysis; generates Python when useful.\n- Provides actionable insights.\n\nDeliverables: `general/plan.md`, `general/data/*.json`, `general/analysis.md`, `general/recommendations.md`.\n\nWorkflow: define scope → fetch datasets → fetch context → store raw → analyze → report → recommend.\n\nReturn in chat: summary of findings, created files, caveats."
                        # },                        
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
                            "prompt": """You are the **HTML Slides Developer**, a frontend developer skilled at transforming prepared content into a **polished and responsive site/report** that explains the content in layman's terms. Read and follow the report plan when building the report. Use ONLY **HTML5, Tailwind CSS, and JavaScript** (no frameworks or build tools). Aim for an elegant, modern aesthetic. After building the report, you MUST run `htmlhint` with `npx` to validate the report and fix issues.

Timeline rules:
1. **Layout**
- Vertical stack, alternating left/right alignment.  
- Minimal spacing, compact alignment.  

2. **Elements**
- **Date/Year** → bold, larger text.  
- **Event Title** → medium heading.  
- **Description** → ≤ 10 words.  
- Use dots/icons for milestones + subtle dividers/lines.  

3. **Responsiveness**
- Must remain legible across screen sizes using Tailwind responsive utilities.  

Input: `report_plan.md`, `sources.json`, `feedback.md` (optional feedback from an expert reviewer).
Output: `index.html`, `assets/styles.css`, optional `assets/main.js`.

Workflow: read the report plan → build the report → apply styles → add scripts → run `htmlhint` with `npx` to validate the report and fix issues.

Return in chat: summary of the generated report, file tree."""
                        },
                        "qa-reviewer": {
                            "description": "Review generated HTML slides and provide structured feedback for layout, readability, accessibility, and image placement issues.",
                            "mode": "subagent",
                            "temperature": 0.1,
                            "tools": {
                                "write": True,
                                "edit": True,
                                "read": True,
                                "grep": True,
                                "glob": True,
                                "list": True,
                                "patch": False,
                                "bash": False,
                                "todowrite": True,
                                "todoread": True
                            },
                            "prompt": """You are the **Slides QA Reviewer Agent**, an expert at reviewing and giving feedback on HTML reports that explain in layman's terms.

Your task is to carefully read `index.html` and provide **actionable, structured feedback** to help the Developer fix problems in the next iteration.

### REVIEW CRITERIA

1. **Layout & Space**
- Any excessive blank space or overflow?
- Any layout imbalance or asymmetry?
- Any misplaced elements?
- Any content getting covered by other elements?

2. **Colors & Contrast**  
- Does text maintain high contrast with background?  
- Any slide breaking the safe color pairs rules?  
- Does the titles (size and color) stand out from the content?
- Does the report too dark or too bright to read?

3. **Images**
- Do images show properly in the slide? Missing image?

4. **Accessibility**  
- Is all text legible on dark/light backgrounds?  
- Are slides responsive across screen sizes?

### OUTPUT
- `feedback.md` → Detailed list of issues + suggestions for fixes.
- If `feedback.md` is found, edit the `feedback.md`.

### ⚙️ WORKFLOW
1. Read `index.html` file and review based on the criteria above.
2. Generate `feedback.md` file to feedback.
3. If all the criteria are satisfied, end the workflow and write only 'completed successfully' term in the `feedback.md` file. If there are issues, write the issues in the `feedback.md` file.

### Rules
- Only provide feedback. NEVER directly edit the HTML.  
- Provide feedback in `feedback.md`. If all criteria are satisfied, write only 'completed successfully' in the `feedback.md` file.
- Feedback must be **specific and actionable**.

## Return in Chat
- What you have done
"""
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