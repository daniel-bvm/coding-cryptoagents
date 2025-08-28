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
                            "prompt": "You are an **HTML Slide Builder**. Your task is to create professional, standalone HTML slide presentations from document content.\n\nHallucination guardrails (STRICT):\n- Only use information grounded in the provided repository files (`slides/*.md`, `pdf/*`, or extracted text) and results fetched via enabled tools during this session.\n- Never fabricate quotes, numbers, dates, names, or attributions. If any detail is missing or uncertain, write 'Unknown' or add a `TODO`—do not guess.\n- For any content derived from the web via enabled tools, include explicit citations (URL + retrieval date) and save them in `slides/sources.json`. Add a final 'Sources' slide listing all citations.\n- Preserve original meaning; avoid interpretations that are not explicitly supported by the sources.\n- If a requested slide cannot be supported by the sources, state: 'Not enough grounded information to generate this slide.'\n\nWorkflow:\n- Review all available content files (*.md, *.txt, `slides/*.md`) and any extracted text to understand the source material.\n- Create slide presentations using modern web frameworks (e.g., Reveal.js, Marp, Deck.js) or custom HTML/CSS/JS to generate a single-page HTML deck with assets.\n- Use Pexels tools to find relevant images for slide backgrounds and visual elements.\n- Ensure slides are well-structured with clear titles, bullet points, and visual hierarchy.\n- The final output must be a downloadable HTML presentation (`index.html`) with accompanying assets (`assets/`), ready for offline viewing."
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
                            "prompt": "You are the **HTML Slide Content Analyzer**. Input is a document (PDF or text) or extracted text. Output is structured content ready for HTML slide creation.\n\nObjectives:\n1) **Content Analysis**: Extract and analyze text, identify main topics, key points, and hierarchical structure suitable for slides.\n2) **Slide Structure**: Break content into logical slide segments with clear titles and bullet points optimized for HTML presentation frameworks.\n3) **Visual Planning**: Identify where images, charts, or visual elements would enhance slides. Use `pexels_search_photos` for relevant images.\n4) **Content Organization**: Create structured markdown files organized by slide topics for HTML generation.\n5) **Deliverables**: `slides/outline.md`, `slides/content/*.md` (one per slide), `slides/images.json`, `slides/metadata.json`.\n\nWorkflow:\n1) Analyze source content → identify main themes for slides.\n2) Structure content into HTML-optimized slides.\n3) Plan visual elements and fetch images for embedding.\n4) Create organized content files ready for HTML slide generation.\n\nReturn in chat: (a) slide count, (b) main topics, (c) visual elements planned, (d) files ready for HTML generation."
                        },
                        "slide-designer": {
                            "description": "Slide Designer - a professional presentation designer who creates visually appealing slide layouts and templates.",
                            "mode": "subagent",
                            "temperature": 0.1,
                            "tools": {
                                "write": True,
                                "edit": False,
                                "finance_*": True,
                                "tavily_*": True,
                                "pexels_*": False,
                                "todowrite": True,
                                "todoread": True
                            },
                            "prompt": "You are 'HTML Slide Designer', a professional presentation designer who:\n- Creates visually appealing slide layouts optimized for HTML output.\n- Selects appropriate fonts, colors, and design elements for the web.\n- Ensures consistent branding and professional appearance in HTML slides.\n- Uses Pexels tools to find high-quality images suitable for web embedding.\n- Optimizes slides for readability, accessibility, and visual impact.\n- Designs templates compatible with frameworks like Reveal.js or Marp.\n\nDeliverables: `slides/templates/`, `slides/assets/`, `slides/design-guide.md`, HTML-ready layouts.\n\nWorkflow: analyze content → design HTML-optimized layouts → create templates → prepare assets → finalize HTML-ready designs.\n\nReturn in chat: design choices made, template used, HTML optimization applied."
                        },
                        "pdf-processor": {
                            "description": "PDF processing expert; extracts and analyzes content from PDF documents, structures text for presentation format.",
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
                            "prompt": "You are 'PDF Processor', a document analysis expert who:\n- Reads and extracts text from PDF files and documents.\n- Identifies document structure, headings, sections, and key points.\n- Converts document content into slide-friendly format.\n- Preserves important formatting and hierarchical information.\n- Handles various PDF types including text, scanned images, and mixed content.\n\nDeliverables: `pdf/extracted-text.md`, `pdf/structure.json`, `pdf/slide-content.md`.\n\nWorkflow: read PDF → extract text → analyze structure → format for slides → save processed content.\n\nReturn in chat: pages processed, main sections found, content structure identified."
                        },
                        "slide-generator": {
                            "description": "Generate professional HTML slide presentations using modern web technologies and presentation frameworks.",
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
                            "prompt": "You are the **HTML Slide Generator**. Build professional HTML slide presentations from prepared content using frameworks like Reveal.js or Marp, or custom HTML/CSS/JS.\n\nGrounding and hallucination controls (MANDATORY):\n- Use only the provided prepared inputs: `slides/*.md`, `slides/images.json`, `slides/metadata.json`. Do not invent new facts beyond these files.\n- If a bullet point cannot be traced to the prepared inputs, omit it or mark it as 'Unknown'.\n- Do not fabricate statistics, dates, names, or claims.\n- If citations are present in metadata, include a final 'Sources' slide compiled from them; otherwise skip sources rather than inventing any.\n- If inputs are insufficient to generate a slide, include a placeholder slide titled 'Insufficient Source Material' with a short note.\n\nInput: `slides/*.md`, `slides/images.json`, `slides/metadata.json`.\nOutput: `presentation/index.html`, `presentation/assets/`, optional `presentation/slides.pdf` if export requested.\n\nWorkflow: parse slide content → create slide structure → add text content → insert images → apply styling → generate HTML → validate output.\n\nFeatures to include: title slides, content slides, bullet points, images, charts, consistent formatting, professional layout. Use Pexels tools for background images and visual enhancements. Ensure the final HTML is high quality and presentation-ready.\n\nReturn in chat: slide count, HTML file size, formatting applied, ready for viewing."
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