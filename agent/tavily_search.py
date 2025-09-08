from agent.configs import settings
from typing import Annotated
import json
import os
import httpx
import logging
import sys
import re
import string
import random
from typing import Any

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

TAVILY_BASE_URL = "https://api.tavily.com"
TAVILY_API_KEY = settings.tavily_api_key
ETERNALAI_MCP_PROXY_URL = settings.eternalai_mcp_proxy_url

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


async def search(query: Annotated[str, "The query to search for"]) -> list[dict]:
    global TAVILY_BASE_URL, TAVILY_API_KEY, ETERNALAI_MCP_PROXY_URL

    body = {
        "query": query,
        "max_results": 10,
        "include_image_descriptions": True,
        "include_images": True,
        "search_depth": "advanced",
        "topic": "general"
    }

    if TAVILY_API_KEY:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{TAVILY_BASE_URL}/search",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {TAVILY_API_KEY}"
                    },
                    json=body
                )
                
                if response.status_code != 200:
                    logger.warning(f"Tavily API returned status code {response.status_code}; {response.text}")
                    return []

                response_json: dict = response.json()
                return parse_tavily_search_response(response_json)
            
            except Exception as e:
                logger.error(f"Error searching web: {e}")
                return []
    
    if ETERNALAI_MCP_PROXY_URL:
        full_body = {
            "url": f"{TAVILY_BASE_URL}/search",
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
                    return []

                response_json: dict = response.json()
                return parse_tavily_search_response(response_json)

            except Exception as e:
                logger.error(f"Error searching web: {e}")
                return []

    logger.error("No API key or keyless provider configured")
    return []


async def format_web_search_context(search_results: list[dict]) -> str:
    search_context = ""
    if len(search_results) > 0:
        search_context = "\n\n### Web Search Context\n"
        search_context += "Here's relevant information from the web that will help with your task:\n\n"
        
        for i, result in enumerate(search_results, 1):
            search_context += f"**Source {i}: {result['title']}**\n"
            search_context += f"URL: {result['url']}\n\n"
            if result.get('published_date'):
                search_context += f"Published Date: {result['published_date']}\n"
            search_context += f"Content: {result['content']}\n"

    return search_context