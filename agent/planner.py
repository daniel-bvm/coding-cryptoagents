from openai import AsyncClient
from typing import Any, AsyncGenerator
from agent.configs import settings
import json
import logging
from agent.app_models import StepV2
from agent.utils import strip_thinking_content
from json_repair import repair_json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def get_current_time_details():
    """Get current time details for the planning template"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S UTC")

COT_TEMPLATE = """
You are an analytical assistant with access to ONLY Financial Datasets API tools for financial data. 

**CRITICAL FINANCIAL DATA RESTRICTIONS:**
- For ALL financial data (stocks, crypto, company financials): Use ONLY Financial Datasets API tools
- NEVER suggest using Yahoo Finance, yfinance, Bloomberg, Alpha Vantage, or any other financial data sources
- NEVER suggest scraping financial websites or external APIs
- NEVER use web search tools like Tavily for financial numbers or stock prices
- Available Financial Datasets tools ONLY:
  * get_income_statements - Company income statements
  * get_balance_sheets - Company balance sheets  
  * get_cash_flow_statements - Company cash flow data
  * get_current_stock_price - Current stock prices
  * get_historical_stock_prices - Historical stock data
  * get_company_news - Company-specific news
  * get_available_crypto_tickers - List crypto symbols
  * get_crypto_prices - Crypto price data
  * get_historical_crypto_prices - Historical crypto data
  * get_current_crypto_price - Current crypto prices
  * get_sec_filings - SEC filing documents

Your task is to break the user request into a list of steps, each step should be clearly describe a single action with expectation output. In advance, each step should be one of research (search for information using Financial Datasets tools) or build (write down the code, etc). It should be at least one step to define style, layout, a color palette to be used during development, focus on the contrast between background and main content. In each step, it should be solid link with the previous, the task should be solved with some research steps first, followed by build steps. When the user asking for something easy to understand, we just need to carefully research about it (search directly the mentioned keywords, quote, etc), and create a final report in build steps that is professional, concise, and visual stunning (no need a child-friendly design). More important, your voice should be in the user's voice (like the user is self-talking). The final output should be a static site that is professional, colorful, stunning, professional visual design and include an index.html file in the project root. To style the project, make plan to utilize Tailwind CSS as much as possible to save time and resources. For mockup images, plan to search them from the pexels. Only write and review, no deployment, documents are needed. {note}. Finally, do not plan to mock the data to write the report, plan research to gather information instead.

The user wants:
{title}: {user_request} at {current_time}

So far, these are the steps planned:
{context}

What is the next step should we do? 
Respond in JSON format: {{ "reason": "...", "task": "...", "expectation": "...", "step_type": "...(research or build)" }}
If no more are needed, just return: <done/>.
"""

async def gen_plan(title: str, user_request: str, max_steps: int = 5) -> AsyncGenerator[StepV2, None]:
    logger.info(f"Making plan for user request: {user_request} (Title: {title})")

    list_of_steps: list[StepV2] = []
    client = AsyncClient(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    has_build_step, has_plan_step = False, False

    # Get current time details for the planning session
    time_details = get_current_time_details()
    logger.info(f"Planning session started at: {time_details}")

    while True and len(list_of_steps) < max_steps:
        context = "\n".join([f"{i+1}. {step.task}: {step.expectation} ({step.step_type})" for i, step in enumerate(list_of_steps)])
        
        if not has_plan_step:
            note = f'The plan should include at least one research step to gather information.'

        elif not has_build_step:
            note = f'The plan should include at least one build step to create the final product or report.'

        else:
            note = f"The plan should be completed in maximum {max_steps} steps." if len(list_of_steps) > max_steps // 2 else ""

        prompt = COT_TEMPLATE.format(
            user_request=user_request,
            context=context,
            max_steps=max_steps,
            title=title,
            note=note,
            current_time=time_details  # Include all time details in the template
        )

        response = ''

        async with client.chat.completions.stream(
            model=settings.llm_model_id,
            messages=[{"role": "user", "content": prompt}]
        ) as stream:
            async for event in stream:
                if event.type == 'content.delta':
                    response += event.delta

        response_text = strip_thinking_content(response)

        if "<done/>" in response_text.strip().lower():
            reasoning = None

            if 'reason' in response_text.lower():
                l, r = response_text.find('{'), response_text.rfind('}')+1
                no_thinking_text = response_text[l:r]
                try:
                    resp_json: dict[str, Any] = json.loads(repair_json(no_thinking_text))
                    reasoning = resp_json.get('reason')

                except Exception as err:
                    logger.error(f"Error parsing JSON: {err}; Response: {no_thinking_text}")

            if not reasoning:
                reasoning = response_text.strip()

            break

        try:
            l, r = response_text.find('{'), response_text.rfind('}')+1
            step_data: dict = json.loads(repair_json(response_text[l:r]))
            step = StepV2(**step_data)

            has_build_step = has_build_step or step.step_type == 'build'
            has_plan_step = has_plan_step or step.step_type == 'research'

            list_of_steps.append(step)
            logger.info(f"Added {step.step_type} step: {step.task} (Reason: {step.reason}; Expectation: {step.expectation})")
            yield step
        except Exception as e:
            logger.error(f"[2] Failed to parse response: {e}")