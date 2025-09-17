import re
from pydantic import BaseModel
from copy import deepcopy
from string import punctuation
from deepsearch.export import deepsearch
from deepsearch.agents.deep_reasoning import StructuredReport
import os
from typing import Any
import logging

from copy import deepcopy
from string import punctuation

from agent.concurrency import sync2async

logger = logging.getLogger(__name__)


class QueryInput(BaseModel):
    topic: str
    urls: list[str]
    
URL_REGEX = re.compile(r'https?://[^\s]+')

def is_valid_topic(topic: str, urls: list[str]) -> bool:
    topic_cp = deepcopy(topic) 

    for url in urls:
        topic_cp = topic_cp.replace(url, '')
 
    for p in punctuation:
        topic_cp = topic_cp.replace(p, '')

    return len(topic_cp.strip()) > 0

def detect_urls(topic_or_url: str) -> QueryInput:
    urls = URL_REGEX.findall(topic_or_url)

    if not urls:
        return QueryInput(topic=topic_or_url if is_valid_topic(topic_or_url, []) else '', urls=[])

    return QueryInput(topic=topic_or_url if is_valid_topic(topic_or_url, urls) else '', urls=urls)

async def run_deepsearch(topic: str) -> StructuredReport | None:
    if not topic:
        return None

    async_deepsearch = sync2async(deepsearch)
    output: StructuredReport = await async_deepsearch(topic)
    
    if not output:
        return None

    return output

async def scrape(
    urls: list[str],
    save_dir: str, 
    preview_tokens_limit: int = 4096,
    max_preview_tokens: int = 1024
) -> list[dict[str, Any]]:
    os.makedirs(save_dir, exist_ok=True)

    if not urls:
        return []

    from mcps.tavily_search.main import fetch
    call_fn = fetch.fn
    
    urls = list(set(urls))

    preview_chars_limit = preview_tokens_limit * 4
    max_preview_chars = max_preview_tokens * 4
    char_limits = min(preview_chars_limit // len(urls), max_preview_chars)

    results: list[dict[str, Any]] = []

    for url in urls:
        try:
            response = await call_fn(url)
            for item in response:
                if 'raw_content' not in item:
                    continue

                raw_content: str = item['raw_content']
                raw_content_preview: str = raw_content[:char_limits]
                random_file_name: str = f'{os.urandom(4).hex()}.md'
                file_path: str = os.path.join(save_dir, random_file_name)
                
                with open(file_path, 'w') as f:
                    f.write(raw_content_preview)

                results.append({
                    'url': url,
                    'full_content_path': file_path,
                    'preview_content': raw_content_preview,
                    'raw_content': raw_content
                })

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            continue

    return results

def gather_info(scrape_results: list[dict[str, Any]], deepsearch_results: StructuredReport | None, save_path: str) -> str:
    if not scrape_results and not deepsearch_results:
        return ""

    scratchpad = ""
    scratchpad_full = ""

    for i, result in enumerate(scrape_results):
        scratchpad += f"{1 + i} Scraped from {result['url']} (Raw content stored in {result['full_content_path']}):\n"
        scratchpad += f"Preview: {result['preview_content']}\n\n"

        scratchpad_full += f"{1 + i} Scraped from {result['url']}:\n"
        scratchpad_full += f"{result['raw_content']}\n\n"

    if deepsearch_results:
        scratchpad += f"Deep search results:\n"
        scratchpad += f"Title: {deepsearch_results.title}\n"
        scratchpad += f"Keypoints: {deepsearch_results.keypoints}\n"
        scratchpad += f"Short Answer: {deepsearch_results.direct_answer}\n"
        scratchpad += f"Content: {deepsearch_results.report}\n"
        scratchpad += f"References: {deepsearch_results.references}\n"
        
        scratchpad_full += f"Deep search results:\n"
        scratchpad_full += f"Title: {deepsearch_results.title}\n"
        scratchpad_full += f"Keypoints: {deepsearch_results.keypoints}\n"
        scratchpad_full += f"Short Answer: {deepsearch_results.direct_answer}\n"
        scratchpad_full += f"Content: {deepsearch_results.report}\n"
        scratchpad_full += f"References: {deepsearch_results.references}\n"
        
    scratchpad += f"Full version of the research content is stored in {save_path}"

    with open(save_path, "w", encoding='utf-8') as f:
        f.write(scratchpad_full)

    return scratchpad
