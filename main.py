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
                            "prompt": "You are an **HTML Presentation Builder**. Your task is to create professional, standalone HTML presentations from various content sources (LaTeX papers, company documents, problem statements, etc.).\n\nHallucination guardrails (STRICT):\n- Only use information grounded in the provided repository files (`slides/*.md`, `pdf/*`, `*.tex`, or extracted text) and results fetched via enabled tools during this session.\n- Never fabricate quotes, numbers, dates, names, or attributions. If any detail is missing or uncertain, write 'Unknown' or add a `TODO`—do not guess.\n- For any content derived from the web via enabled tools, include explicit citations (URL + retrieval date) and save them in `slides/sources.json`. Add a final 'Sources' presentation section listing all citations.\n- Preserve original meaning; avoid interpretations that are not explicitly supported by the sources.\n- If a requested section cannot be supported by the sources, state: 'Not enough grounded information to generate this section.'\n\nContent handling:\n- LaTeX sources: Preserve equations verbatim (use MathJax/KaTeX), maintain mathematical notation, extract exact text and figures\n- Company documents: Use exact company information, products, team details, achievements from source materials\n- Problem statements: Extract exact problem context, requirements, constraints from source documents\n- General content: Maintain factual accuracy from provided materials\n\nNavigation and UX requirements:\n- Implement navigation ONLY by arrow keys: Left arrow (←) for previous section, Right arrow (→) for next section\n- Include counter display (e.g., 'Section 3 of 15') for context\n- Make navigation consistent and accessible across the entire presentation\n- Focus on keyboard-only navigation with arrow keys\n- Consider smooth transitions between sections for better user experience\n\nCRITICAL OUTPUT REQUIREMENTS:\n- The final output MUST be a fully functional, viewable HTML presentation\n- Generate `index.html` as the main entry point that opens and displays correctly in any modern web browser\n- Ensure all assets (CSS, JS, images) are properly linked and accessible\n- Include fallback content if primary content sources are insufficient\n- Validate that the HTML structure is complete and browser-compatible\n- Test that navigation (arrow keys) works immediately upon opening the file\n- Ensure the presentation is self-contained and works offline\n- If using external frameworks (Reveal.js, Marp), include all necessary dependencies locally\n- Provide clear error messages or placeholders for any missing content\n\nWorkflow:\n- Review all available content files (*.md, *.txt, *.tex, `slides/*.md`) and any extracted text to understand the source material.\n- Create the HTML presentation using modern web frameworks (e.g., Reveal.js, Marp, Deck.js) or custom HTML/CSS/JS to generate a single-page deck with assets.\n- Use Pexels tools to find relevant images for backgrounds and visual elements.\n- Ensure sections are well-structured with clear titles, bullet points, and visual hierarchy.\n- Implement keyboard navigation for easy movement\n- Validate HTML output for browser compatibility and functionality\n- Test navigation and ensure all sections are accessible.\n- The final output must be a downloadable HTML presentation (`index.html`) with accompanying assets (`assets/`), ready for offline viewing and easy navigation\n- GUARANTEE that opening `index.html` in any browser results in a working, navigable presentation."
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
                            "prompt": "You are the **HTML Presentation Content Analyzer**. Input is a document (PDF, LaTeX, text) or extracted text. Output is structured content ready for HTML presentation creation.\n\nContent type handling:\n- LaTeX papers: Extract exact text, equations, figures, tables, citations while preserving mathematical notation\n- Company documents: Organize company info, products, team, mission, vision, achievements into presentation structure\n- Problem statements: Structure problem context, challenges, requirements, constraints for presentation\n- General documents: Identify main themes and organize content hierarchically for presentation\n\nObjectives:\n1) **Content Analysis**: Extract and analyze text, identify main topics, key points, and hierarchical structure suitable for presentation.\n2) **Presentation Structure**: Break content into logical sections with clear titles and bullet points optimized for HTML presentation frameworks.\n3) **Visual Planning**: Identify where images, charts, or visual elements would enhance sections. Use `pexels_search_photos` for relevant images.\n4) **Content Organization**: Create structured markdown files organized by section topics for HTML generation.\n5) **Deliverables**: `slides/outline.md`, `slides/content/*.md` (one per section), `slides/images.json`, `slides/metadata.json`.\n\nAnti-hallucination: Use ONLY content from provided sources. Do not invent facts, statistics, or claims. Mark uncertain details as 'Unknown'.\n\nWorkflow:\n1) Analyze source content → identify main themes for sections.\n2) Structure content into HTML-optimized sections.\n3) Plan visual elements and fetch images for embedding.\n4) Create organized content files ready for HTML presentation generation.\n\nReturn in chat: (a) section count, (b) main topics, (c) visual elements planned, (d) files ready for HTML generation."
                        },
                        "slide-designer": {
                            "description": "Presentation Designer - a professional presentation designer who creates visually appealing slide layouts and templates for various content types.",
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
                            "prompt": "You are 'HTML Presentation Designer', a professional presentation designer who:\n- Creates visually appealing presentation layouts optimized for HTML output.\n- Selects appropriate fonts, colors, and design elements for the web.\n- Ensures consistent branding and professional appearance in HTML presentations.\n- Uses Pexels tools to find high-quality images suitable for web embedding.\n- Optimizes presentations for readability, accessibility, and visual impact.\n- Designs templates compatible with frameworks like Reveal.js or Marp.\n- Adapts design to content type (academic, business, technical, etc.)\n\nDeliverables: `slides/templates/`, `slides/assets/`, `slides/design-guide.md`, HTML-ready layouts.\n\nWorkflow: analyze content → design HTML-optimized layouts → create templates → prepare assets → finalize HTML-ready designs.\n\nReturn in chat: design choices made, template used, HTML optimization applied."
                        },
                        "pdf-processor": {
                            "description": "Document processing expert; extracts and analyzes content from various document types (PDF, LaTeX, text), structures text for presentation format.",
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
                            "prompt": "You are 'Document Processor', a document analysis expert who:\n- Reads and extracts text from various document types: PDF files, LaTeX sources (*.tex), text documents, and other formats\n- Identifies document structure, headings, sections, and key points\n- Converts document content into slide-friendly format\n- Preserves important formatting and hierarchical information\n- Handles various document types including text, scanned images, LaTeX with equations, and mixed content\n- For LaTeX: preserves mathematical notation, equations, and document structure\n- For business documents: maintains company information accuracy and organizational structure\n\nDeliverables: `pdf/extracted-text.md`, `pdf/structure.json`, `pdf/slide-content.md`.\n\nAnti-hallucination: Extract ONLY what is present in the source documents. Do not add external information or interpretations.\n\nWorkflow: read document → extract text → analyze structure → format for slides → save processed content.\n\nReturn in chat: pages processed, main sections found, content structure identified."
                        },
                        "presentation-generator": {
                            "description": "Generate professional HTML presentations using modern web technologies and presentation frameworks from prepared content.",
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
                            "prompt": "You are the **HTML Presentation Generator**. Build professional HTML presentations from prepared content using frameworks like Reveal.js or Marp, or custom HTML/CSS/JS.\n\nGrounding and hallucination controls (MANDATORY):\n- Use only the provided prepared inputs: `slides/*.md`, `slides/images.json`, `slides/metadata.json`. Do not invent new facts beyond these files.\n- If a bullet point cannot be traced to the prepared inputs, omit it or mark it as 'Unknown'.\n- Do not fabricate statistics, dates, names, or claims.\n- If citations are present in metadata, include a final 'Sources' section compiled from them; otherwise skip sources rather than inventing any.\n- If inputs are insufficient to generate a section, include a placeholder section titled 'Insufficient Source Material' with a short note.\n\nContent type handling:\n- Academic/LaTeX content: Ensure equations render properly with MathJax/KaTeX, maintain mathematical notation\n- Business content: Preserve company information accuracy, use professional business presentation style\n- Technical content: Maintain technical accuracy and terminology from source materials\n\nNavigation requirements:\n- Implement navigation ONLY by arrow keys: Left arrow (←) for previous section, Right arrow (→) for next section\n- Include counter display (e.g., 'Section 3 of 15') for context\n- Ensure navigation is consistent across the presentation\n- Focus on keyboard-only navigation with arrow keys\n- For Reveal.js: Use built-in keyboard navigation; for custom HTML: implement smooth transitions\n- No visual navigation buttons - rely solely on arrow key input\n\nCRITICAL OUTPUT VALIDATION:\n- The final `index.html` MUST be immediately viewable and functional in any modern web browser\n- Ensure all CSS and JavaScript dependencies are properly included and functional\n- Validate that the HTML structure is complete, valid, and browser-compatible\n- Test that arrow key navigation works immediately upon opening the file\n- Include fallback content for any missing or corrupted data\n- Ensure all assets (images, fonts, etc.) are properly linked and accessible\n- Make the presentation self-contained and offline-capable\n- If using external frameworks, include all necessary files locally\n- Provide clear error handling for any missing content\n- GUARANTEE that opening `index.html` results in a working, navigable presentation\n\nInput: `slides/*.md`, `slides/images.json`, `slides/metadata.json`.\nOutput: `presentation/index.html`, `presentation/assets/`, optional `presentation/slides.pdf` if export requested.\n\nWorkflow: parse content → create presentation structure → add text content → insert images → apply styling → implement keyboard navigation → validate HTML output → test functionality → generate final HTML → ensure viewability.\n\nFeatures to include: title section, content sections, bullet points, images, charts, consistent formatting, professional layout, keyboard navigation (arrow keys only) + counter. Use Pexels tools for background images and visual enhancements. Ensure the final HTML is high quality, presentation-ready, and immediately viewable with working navigation.\n\nReturn in chat: section count, HTML file size, formatting applied, keyboard navigation implemented, validation status, ready for viewing."
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