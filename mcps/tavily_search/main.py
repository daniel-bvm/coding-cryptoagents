from fastmcp import FastMCP
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

app = FastMCP("isearch")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
ETERNALAI_MCP_PROXY_URL = os.getenv("ETERNALAI_MCP_PROXY_URL")
TAVILY_BASE_URL = "https://api.tavily.com"
TWITTER_BASE_URL = "https://imagine-backend.bvm.network/api/internal/twitter".rstrip("/")

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
 
def read_tweet(data: dict[str, Any]) -> dict[str, Any]:
    tweet = data.get('Tweet', {})
    user = data.get('User', {})

    if tweet is None or user is None:
        return None

    response = {}
    keys = ["id", "text", "username"]

    for k, v in tweet.items():
        if k in keys and v is not None:
            response[k] = v

    for k, v in user.items():
        if k in keys and v is not None:
            response[k] = v

    return response

def parse_twitter_search_response(response: dict, reduce_duplication=True) -> list[dict]:
    lookups: dict[str, Any] = response.get('LookUps', {})
    results: list[dict[str, Any]] = []
    hashes = set([])

    for id, tweet in lookups.items():
        tweet = read_tweet(tweet)
        if tweet is not None:
            text = tweet.get("text")

            if reduce_duplication and text in hashes:
                continue

            hashes.add(text)
            results.append(tweet)

    return results

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


def _optimize_twitter_query(
    query: str,
    remove_punctuations=False,
    token_limit=-1,
    pat: re.Pattern = None,
    length_limit=30,
) -> str:
    and_token = re.compile(r"\bAND\b", flags=re.IGNORECASE)
    spacing = re.compile(r"\s+")

    query = and_token.sub(" ", query)
    query = spacing.sub(" ", query)

    tokenized_query = re.split(r"\bor\b", query, flags=re.IGNORECASE)
    filtered_tokenized_query = []

    if pat is not None:
        tokenized_query = [
            i.strip() for i in tokenized_query if pat.fullmatch(i.strip())
        ]

    # sort and remove duplicates
    tokenized_query = sorted(tokenized_query, key=len, reverse=True)

    for i in tokenized_query:
        i = i.strip(" '\"")

        if remove_punctuations:
            i = "".join([c for c in i if c not in string.punctuation])

        if len(filtered_tokenized_query) == 0:
            filtered_tokenized_query.append(i)
        else:
            if any([i.lower() in x.lower() for x in filtered_tokenized_query]):
                continue
            else:
                filtered_tokenized_query.append(i)

    random.shuffle(filtered_tokenized_query)

    if token_limit != -1:
        filtered_tokenized_query = filtered_tokenized_query[:token_limit]

    if len(filtered_tokenized_query) == 0:
        return ""

    res = ""
    for item in filtered_tokenized_query:
        if len(res) + len(item) > length_limit:
            break

        if len(res) > 0:
            res += " OR "

        res += item

    if len(res) == 0:
        e = tokenized_query[0].split()

        for ee in e:
            if len(res) + len(ee) > length_limit:
                break

            if len(res) > 0:
                res += " "

            res += ee

    return res


async def search_twitter_news(
    query: str,
    limit_api_results=50,
    use_raw=False,
    no_duplication=True
) -> list[dict]:
    if not use_raw:
        query = _optimize_twitter_query(
            query, remove_punctuations=True, token_limit=5, length_limit=30
        )
        logger.info(f"[search_twitter_news] Optimized query: {query}")

    if query.strip() == "":
        logger.error("[search_twitter_news] Empty query")
        return []

    url = f"{TWITTER_BASE_URL}/tweets/search/recent"
    query_params = {
        "query": f"{query} -is:retweet -is:reply -is:quote is:verified",
        "max_results": limit_api_results,
    }

    if TWITTER_API_KEY:
        async with httpx.AsyncClient(
            headers={"api-key": TWITTER_API_KEY},
            timeout=180, # 3 minutes
        ) as client:
            try:
                resp = await client.get(url, params=query_params)
            except Exception as e:
                logger.error(f"[search_twitter_news] Error occurred when calling api: {e}")
                return []

            if resp.status_code != 200:
                return []
            
            resp_json: dict = resp.json()
            
        if resp_json.get("error") is not None:
            logger.error("[search_twitter_news] Error occurred when calling api: " + resp_json["error"]["message"])
            return []

        return parse_twitter_search_response(resp_json["result"], reduce_duplication=no_duplication)

    if ETERNALAI_MCP_PROXY_URL:
        full_body = {
            "url": f"{TWITTER_BASE_URL}/tweets/search/recent",
            "headers": {
                "Content-Type": "application/json",
            },
            "query": query_params,
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
                    logger.warning(f"Twitter API returned status code {response.status_code}; {response.text}")
                    return []

                response_json: dict = response.json()
                return parse_twitter_search_response(response_json["result"], reduce_duplication=no_duplication)

            except Exception as e:
                logger.error(f"Error searching twitter: {e}")
                return []

    logger.error("No API key or keyless provider configured")
    return []

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
                    f"{TAVILY_BASE_URL}/extract",
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
            "url": f"{TAVILY_BASE_URL}/extract",
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

def replace(placeholder: Any | None, default: Any | None) -> Any:
    if not placeholder:
        return default

    return placeholder

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

    twitter_news = await search_twitter_news(query, limit_api_results=20)

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
                    return [replace(twitter_news, {"error": "Failed to search web"})]

                response_json: dict = response.json()
                return parse_tavily_search_response(response_json) + twitter_news
            
            except Exception as e:
                logger.error(f"Error searching web: {e}")
                return [replace(twitter_news, {"error": str(e)})]
    
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
                    return [replace(twitter_news, {"error": "Failed to search web"})]

                response_json: dict = response.json()
                return parse_tavily_search_response(response_json) + twitter_news

            except Exception as e:
                logger.error(f"Error searching web: {e}")
                return [replace(twitter_news, {"error": str(e)})]

    logger.error("No API key or keyless provider configured")
    return [replace(twitter_news, {"error": "No API key or keyless provider configured"})]

if __name__ == "__main__":
    app.run(transport="stdio")