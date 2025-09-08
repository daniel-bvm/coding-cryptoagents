import requests
from agent.configs import settings
import httpx
from typing import Literal
import logging
import json
from agent.anthropic_proxy import get_models_fn
import sys

logger = logging.getLogger(__name__) 

async def find_opencode_binary() -> str:
    user = os.getenv("USER")

    for path in [
        "/root/.opencode/bin/opencode",
        f"/home/{user}/.opencode/bin/opencode",
        "/usr/bin/opencode",
        "/usr/local/bin/opencode",
        "/bin/opencode",
        f"/Users/{user}/.opencode/bin/opencode"
    ]:
        if os.path.exists(path):
            return path

    raise RuntimeError("OpenCode binary not found")

async def call_opencode_api_query(
    session_id: str,
    agent: Literal["research", "plan", "build", "finalize"],
    system: str,
    message: str | list[dict],
    model_provider: str,
    model_id: str, 
    opencode_host: str = settings.opencode_host,
    opencode_port: int = settings.opencode_port,
    task_id: str = None
) -> str:

    message_data = {
        "providerID": model_provider,
        "modelID": model_id,
        "agent": agent,
        # "system": system,
    }

    if isinstance(message, list):
        message_data["parts"] = message
    else:
        message_data["parts"] = [{"type": "text", "text": message}]

    response_text = ''

    async with httpx.AsyncClient() as client:
        url = f"http://{opencode_host}:{opencode_port}/session/{session_id}/message"
        logger.info(f"Calling OpenCode API: url={url}, message_data={json.dumps(message_data, indent=2)}")
        response = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            json=message_data,
            timeout=httpx.Timeout(3600.0, connect=10.0)
        )

        session_response = requests.get(url)
        session = session_response.json()

        os.makedirs(f"./opencode-session/{task_id}", exist_ok=True)
        with open(f"./opencode-session/{task_id}/{session_id}.json", "w") as f:
            json.dump(session, f, indent=2)
        
        if response.status_code == 200:
            response_json: dict = response.json()
            parts = response_json.get("parts", [])
            
            for item in parts:
                if item.get("type") == "text" and item.get("text"):
                    response_text = item.get("text") # get the last

            if not response_text:
                logger.warning(f"No text in response: {json.dumps(response_json, indent=2)} (Session: {session_id})")

        else:
            logger.error(f"Failed to call OpenCode API: {response.status_code} {response.text} (Session: {session_id})")

    return response_text.strip()

async def call_opencode_api_create_session(
    title: str,
    opencode_host: str = settings.opencode_host,
    opencode_port: int = settings.opencode_port
) -> str | None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0, connect=10.0)) as client:
        try:
            response = await client.post(
                f"http://{opencode_host}:{opencode_port}/session",
                headers={"Content-Type": "application/json"},
                json={"title": title}
            )
            response.raise_for_status()
            session_data: dict = response.json()
            return session_data.get("id")
        except Exception as e:
            return None

import os
import asyncio
import socket
import time

async def pick_random_available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]
    
async def wait_until_port_is_ready_to_connect(port: int, timeout: float = 60) -> bool:
    async with httpx.AsyncClient() as client:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                resp = await client.get(f"http://localhost:{port}/app", timeout=httpx.Timeout(1, connect=1))
                assert resp.status_code == 200, f"Failed to connect to OpenCode: {resp.status_code} {resp.text}"
                return True
            except Exception as e:
                pass

            await asyncio.sleep(1)

class OpenCodeSDKClient:
    def __init__(self, working_dir: str):
        assert os.path.exists(working_dir), f"Working directory {working_dir} does not exist"
        self.working_dir = working_dir
        self.process: asyncio.subprocess.Process | None = None
        self.port: int | None = None

    async def connect(self):
        port = await pick_random_available_port()
        
        logger.info(f"Starting OpenCode server on port {port}")
        self.process = await asyncio.create_subprocess_exec(
            await find_opencode_binary(), "serve", f"--port={port}",
            cwd=self.working_dir,
        )

        if not await wait_until_port_is_ready_to_connect(port):
            raise RuntimeError("Failed to start OpenCode server")

        self.port = port

    async def disconnect(self):
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
            finally:
                self.process = None
                self.port = None

    async def query(
        self, 
        agent: Literal["research", "plan", "build", "finalize"], 
        system: str,
        message: str | list[dict],
        model_provider: str = settings.llm_model_provider,
        model_id: str = settings.llm_model_id_code,
        session_id: str | None = None,
        task_id: str = None,
    ) -> str:
        assert self.process, "Not connected to OpenCode"
        return await call_opencode_api_query(
            session_id or (await self.create_session(f"Session {time.time()}")), 
            agent, 
            system, 
            message, 
            model_provider, 
            model_id, 
            opencode_host='127.0.0.1', 
            opencode_port=self.port,
            task_id=task_id,
        )

    async def create_session(self, title: str) -> str:
        assert self.process, "Not connected to OpenCode"

        session_id = await call_opencode_api_create_session(
            title,
            opencode_host='127.0.0.1', 
            opencode_port=self.port,
        )

        assert session_id, "Failed to create session"
        return session_id
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.disconnect()


wrapped_base_url = f"http://localhost:{settings.port}/v1"
config_path = os.path.expanduser("~/.config/opencode/opencode.json")
opencode_dir = os.path.expanduser("~/.config/opencode")
CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

os.makedirs(opencode_dir, exist_ok=True)

AGENT_CONFIGS = {
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
            "tavily*": True,
            "pexels*": True
        },
        "prompt": "Your task is to build the project or a blog post based on the plan. Generally, you have to build an index.html file that responds the user. Strictly follow the plan step-by-step; do not take any extra steps. Do not ask again for confirmation, just do it your way. Your first step should be reviewing all markdown files (*.md or financial/*.md or general/*.md) to get the necessary content. Image sources for mockup purposes should be used from Unsplash. Ask the developer for junk tasks if needed. Do research, content grep for any missing information, and avoid writing code with placeholders only. About financial data, ask the fin-analyst for data gathering, avoid doing it yourself. Make sure the output is clean and ready to be published. To build a well-structured output, use HTML5, styled with Tailwind CSS and handle interactions with js if needed. Your final response should be short, concise, and talk about what you have done (no code explanation in detail is required) and an index.html file to present your findings.   Remember to include links, urls point to any referenced resources."
    },
    "content-prep": {
        "description": "Plan research, analyze, and prepare rich content (text + visuals) for a HTML report; fetch mockup images via Unsplash; use Tavily to search and fetch web content or get original images.",
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
            "pexels*": True,
            "tavily*": True,
            "todowrite": True,
            "todoread": True
        },
        "prompt": "You are the **Content Preparation** agent. Input is a user prompt describing a topic or goal. Output is a complete content package ready for a Developer to turn into a stunning HTML representation.\n\nObjectives:\n1) **Research Plan**: Draft a lean plan with key questions, subtopics, datasets, stakeholders, and metrics. Include a short search strategy.\n2) **Analysis & Synthesis**: Produce a structured outline and detailed sections with facts, bullets, callouts, and tables. Keep claims sourced.\n3) **Image Plan & Assets**: Use `unsplash_search_photos` to fetch images. Save under `assets/images/` and record metadata in `content/images.json`.\n4) **Web Search**: Use Tavily (`tavily_tavily_search`, `tavily_tavily_extract`, `tavily_tavily_crawl`, `tavily_tavily_map`) to fetch articles, docs, recent data. Summarize and cite.\n5) **Deliverables for Developer**: `content/brief.md`, `content/outline.md`, `content/sections/*.md`, `content/references.json`, `content/images.json`, optional `content/data/*.json`.\n\nWorkflow:\n1) Read prompt → write brief & outline.\n2) Draft sections.\n3) Call Unsplash + Tavily as needed.\n4) Summarize outputs + next steps.\n\nReturn in chat: (a) plan, (b) file list, (c) risks, (d) next steps. Remember to include links, urls point to any referenced resources."
    },
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
            "pexels*": True
        },
        "permission": {
            "edit": "allow"
        },
        "prompt": "You are the **Developer**. Build a polished, multi-page, responsive HTML representation from the prepared content. Use **HTML5, Tailwind CSS, and JavaScript** (no extra frameworks or build tools). Aim for an elegant, modern aesthetic.\n\nInput: `content/*.md`, `content/images.json`, `content/data/*.json`.\nOutput: `*.html`, `assets/styles.css`, `assets/main.js`, optional `docs/styleguide.html`, `reports/README.md`.\n\nWorkflow: parse outline → map pages → build pages → apply styles → add scripts → validate accessibility/responsiveness.\n\nReturn in chat: plan, file tree, what you have done. You should use pexels tools to search for images for any purposes from demo, placeholders, etc. Remember to include links, urls point to any referenced resources."
    }
}

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
                    "agent": AGENT_CONFIGS,
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
