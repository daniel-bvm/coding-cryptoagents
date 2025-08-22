from fastmcp import FastMCP
from typing import Annotated
import json
import os
import httpx
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

app = FastMCP("isearch")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
ETERNALAI_MCP_PROXY_URL = os.getenv("ETERNALAI_MCP_PROXY_URL")

def parse_tavily_search_response(response: dict) -> list[dict]:
    skip_keys = ["raw_content"]
    results: list[dict] = response.get('results', [])
    
    return [
        {
            k: v 
            for k, v in e.items()
            if k not in skip_keys
        }
        for e in results
    ]

def parse_tavily_fetch_response(response: dict) -> list[dict]:
    skip_keys = ["url"]
    results: list[dict] = response.get('results', [])

    return [
        {
            k: v 
            for k, v in e.items()
            if k not in skip_keys
        }
        for e in results
    ]

@app.tool(description="Fetch content from a URL")
async def fetch(url: Annotated[str, "The URL to fetch content from"]) -> str:
    global TAVILY_API_KEY, ETERNALAI_MCP_PROXY_URL
    
    body = {
        "urls": url,
        "include_images": True,
        "include_favicon": True,
        "extract_depth": "basic",
        "format": "markdown"
    }

    if TAVILY_API_KEY:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.tavily.com/extract",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {TAVILY_API_KEY}"
                    },
                    json=body
                )
                
                if response.status_code != 200:
                    logger.warning(f"Tavily API returned status code {response.status_code}; {response.text}")
                    return [{"error": "Failed to fetch content from URL"}]

                response_json: dict = response.json()
                return parse_tavily_fetch_response(response_json)
            
            except Exception as e:
                logger.error(f"Error searching web: {e}")
                return [{"error": str(e)}]
    
    if ETERNALAI_MCP_PROXY_URL:
        full_body = {
            "url": "https://api.tavily.com/search",
            "headers": {
                "Content-Type": "application/json",
            },
            "body": body,
            "method": "POST"
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
                    logger.warning(f"Tavily API returned status code {response.status_code}; {response.text}")
                    return [{"error": "Failed to fetch content from URL"}]

                response_json: dict = response.json()
                return parse_tavily_fetch_response(response_json)
                
            except Exception as e:
                logger.error(f"Error searching web: {e}")
                return [{"error": str(e)}]

    logger.error("No API key or keyless provider configured")
    return []

@app.tool(description="Search the web for information")
async def search(query: Annotated[str, "The query to search for"]) -> list[dict]:
    global TAVILY_API_KEY, ETERNALAI_MCP_PROXY_URL
    
    body = {
        "query": query,
        "max_results": 3,
        "include_image_descriptions": True,
        "include_images": True,
        "search_depth": "advanced",
        "topic": "general"
    }

    if TAVILY_API_KEY:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.tavily.com/search",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {TAVILY_API_KEY}"
                    },
                    json=body
                )
                
                if response.status_code != 200:
                    logger.warning(f"Tavily API returned status code {response.status_code}; {response.text}")
                    return [{"error": "Failed to search web"}]

                response_json: dict = response.json()
                return parse_tavily_search_response(response_json)
            
            except Exception as e:
                logger.error(f"Error searching web: {e}")
                return [{"error": str(e)}]
    
    if ETERNALAI_MCP_PROXY_URL:
        full_body = {
            "url": "https://api.tavily.com/search",
            "headers": {
                "Content-Type": "application/json",
            },
            "body": body,
            "method": "POST"
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
                    logger.warning(f"Tavily API returned status code {response.status_code}; {response.text}")
                    return [{"error": "Failed to search web"}]

                response_json: dict = response.json()
                return parse_tavily_search_response(response_json)
                
            except Exception as e:
                logger.error(f"Error searching web: {e}")
                return [{"error": str(e)}]

    logger.error("No API key or keyless provider configured")
    return []

if __name__ == "__main__":
    app.run(transport="stdio")