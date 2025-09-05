import requests
from agent.configs import settings
import httpx
from typing import Literal
import logging
import json

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
    agent: Literal["research", "build", "finalize"],
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
        agent: Literal["research", "build", "finalize"], 
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
