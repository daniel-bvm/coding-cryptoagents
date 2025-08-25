from fastmcp import FastMCP
import os
from typing import Annotated

import logging
import sys

import httpx
import json

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

app = FastMCP("pexels")

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
ETERNALAI_MCP_PROXY_URL = os.getenv("ETERNALAI_MCP_PROXY_URL")

def parse_pexels_search_response(response: dict) -> list[dict]:
    fields = ['url', 'photographer', 'avg_color', 'src', 'alt']
    photos = response.get("photos", [])

    return [
        {
            k: v
            for k, v in e.items()
            if k in fields
        }
        for e in photos
    ]

@app.tool(description="Search for images from Pexels")
async def search_pexels(topic: Annotated[str, "The topic to search for"]) -> list[dict]:
    params = {
        "query": topic,
        "per_page": 3,
        "page": 1
    }

    if PEXELS_API_KEY:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.pexels.com/v1/search",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"{PEXELS_API_KEY}"
                    },
                    params=params
                )
                
                if response.status_code != 200:
                    logger.warning(f"Pexels API returned status code {response.status_code}; {response.text}")
                    return [{"error": "Failed to search for images"}]

                response_json: dict = response.json()
                return parse_pexels_search_response(response_json)
            
            except Exception as e:
                logger.error(f"Error searching for images: {e}")
                return [{"error": str(e)}]
    
    if ETERNALAI_MCP_PROXY_URL:
        full_body = {
            "url": "https://api.pexels.com/v1/search",
            "headers": {
                "Content-Type": "application/json",
            },
            "query": params,
            "method": "GET"
        }

        body_str = json.dumps(full_body)

        data = {
            'messages': [
                {
                    'role': 'user',
                    'content': body_str
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    ETERNALAI_MCP_PROXY_URL,
                    json=data
                )

                if response.status_code != 200:
                    logger.warning(f"Pexels API returned status code {response.status_code}; {response.text}")
                    return [{"error": "Failed to search for images"}]

                response_json: dict = response.json()
                return parse_pexels_search_response(response_json)
            
            except Exception as e:
                logger.error(f"Error searching for images: {e}")
                return [{"error": str(e)}]

    logger.error("No API key or keyless provider configured")
    return []

if __name__ == "__main__":
    app.run(transport="stdio")