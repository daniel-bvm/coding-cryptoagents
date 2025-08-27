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

async def download_image(url: str, filename: str) -> str:
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
        except Exception as e:
            logger.error(f"Error downloading image from {url}: {e}")
            return None

        if response.status_code != 200:
            logger.error(f"Failed to download image from {url}")
            return None

        with open(filename, "wb") as f:
            f.write(response.content)

    return filename

from urllib.parse import urlparse

def get_name_from_url(url: str) -> str:
    parsed_url = urlparse(url)
    path = parsed_url.path
    file_ext = os.path.splitext(os.path.basename(path))[1]
    return f"{os.urandom(4).hex()}{file_ext}"

async def parse_pexels_search_response(response: dict, output_dir: str = 'assets/images') -> list[dict]:
    os.makedirs(output_dir, exist_ok=True)

    photos = response.get("photos", [])
    results = []

    for i, photo in enumerate(photos):
        search_result = {
            'avg_color': photo.get('avg_color', None),
            'alt': photo.get('alt', None),
        }

        src = {
            key: await download_image(
                value, 
                os.path.join(output_dir, get_name_from_url(value))
            )
            for key, value in photo.get("src", {}).items()
        }

        search_result['src'] = {
            key: value
            for key, value in src.items()
            if value is not None
        }

        results.append(search_result)

    return results

@app.tool(description="Search for images from Pexels in any topics. Return paths to local files.")
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
                return await parse_pexels_search_response(response_json)
            
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
                return await parse_pexels_search_response(response_json)
            
            except Exception as e:
                logger.error(f"Error searching for images: {e}")
                return [{"error": str(e)}]

    logger.error("No API key or keyless provider configured")
    return []

if __name__ == "__main__":
    app.run(transport="stdio")