from openai import NOT_GIVEN, AsyncClient
from typing import Any, AsyncGenerator
from agent.configs import settings
import json
import logging
from agent.app_models import StepV2, StepV2List
from agent.utils import process_json_response, strip_thinking_content
from json_repair import repair_json
from datetime import datetime, timezone
import random
from agent.tavily_search import format_web_search_context, search
from agent.opencode_sdk import AGENT_CONFIGS
import time
from agent.utils import strip_markers

logger = logging.getLogger(__name__)

FIRST_COT_TEMPLATE = """
You are an analytical assistant. Your task is to break the user request into a list of steps, each step should clearly describe a single action with expected output. In details, each step should be one of research (searching for or collecting information), build (producing content such as code, text, layouts, or designs). 

The user said: {user_request}

Our abilities:
{abilities}

When planning to solve a task, always follow these principles:

1. Research Phase
   - Include at least one research step to collect real information or define creative guidelines (e.g., style, layout, color palette).
   - Pay special attention to contrast between background and main sections for accessibility and visual impact.

2. Build Phase
   - Include at least one build step where the task is finalized into a deliverable (e.g., HTML report, HTML blog post, or web page).
   - The final deliverable must always be an index.html file.

3. Step Continuity
   - Each step should logically and explicitly connect to the previous ones.

4. Voice & Style
   - Write in the user's voice (like the user is talking to themselves).

5. Implementation Rules
   - Use Tailwind CSS extensively for styling the HTML content to save time and resources.
   - Only plan to research, write, and review—no deployment or external documentation is required.
   - Do not fabricate content: always plan to gather real information for writing.
   - For mockup images, plan to source them from Unsplash.

So far, these steps are planned:
{context}

What is the next step we should take? 
Respond in JSON format: {{ "reason": "...", "task": "...", "expectation": "...", "step_type": "...(research or build)" }}
If no more are needed, just return: <done/> (no need to explain anything).
"""


NEXT_COT_TEMPLATE = """
You are an analytical assistant. Your task is to break the user request into a list of steps, each step should clearly describe a single action with expected output. In details, each step should be one of research (searching for or collecting information) or build (producing content such as code, text, layouts, or designs)

The user said: {user_request}

Our abilities:
{abilities}

When planning to solve a task, always follow these principles:

1. Research Phase
   - Include at least one research step to collect real information or define creative guidelines (e.g., style, layout, color palette).
   - Pay special attention to contrast between background and main sections for accessibility and visual impact.

2. Build Phase
   - Include at least one build step where the task is finalized into a deliverable (e.g., report, blog post, or web page).
   - The final deliverable must always include an index.html file.

3. Step Continuity
   - Each step should logically and explicitly connect to the previous ones.

4. Voice & Style
   - Write in the user's voice (like the user is talking to themselves).

5. Implementation Rules
   - Use Tailwind CSS extensively for styling the HTML content to save time and resources.
   - Only plan to research, write, and review—no deployment or external documentation is required.
   - Do not fabricate content: always plan to gather real information for writing.
   - For mockup images, plan to source them from Unsplash.

So far, these steps are planned:
{context}

What is the next step we should take? 
Respond in JSON format: {{ "reason": "...", "task": "...", "expectation": "...", "step_type": "...(research or build)" }}
If no more are needed, just return: <done/> (no need to explain anything).
"""

async def gen_plan(title: str, user_request: str, max_steps: int = 4) -> AsyncGenerator[StepV2, None]:
    logger.info(f"Making plan for user request: {user_request}")

    list_of_steps: list[StepV2] = []
    client = AsyncClient(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    has_build_step, has_plan_step = False, False

    abilities = "\n".join([
        f"{k}: {v['description']}" 
        for k, v in AGENT_CONFIGS.items() 
        if v.get('mode', 'primary') == 'subagent' \
            and v.get('enabled', True) \
            and v.get('description')
    ])

    while True and len(list_of_steps) < max_steps:
        context = "\n".join([
            f"{i+1}. {step.step_type}: {step.task} - Expectation: {step.expectation}" 
            for i, step in enumerate(list_of_steps)
        ]) if list_of_steps else "None yet."
        
        if not has_plan_step:
            reminder = f'The plan should include at least one research step to gather information.'

        elif not has_build_step:
            reminder = f'The plan should include at least one build step to create the final product or report.'

        else:
            reminder = f"The plan should be completed in maximum {max_steps} steps." if len(list_of_steps) > max_steps // 2 else ""

        datetime_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        reminder += f"\nCurrent time: {datetime_str}. Platform: Linux."

        if not len(list_of_steps):
            prompt = FIRST_COT_TEMPLATE.format(
                user_request=user_request,
                context=context,
                max_steps=max_steps,
                abilities=abilities
            )
        else:
            prompt = NEXT_COT_TEMPLATE.format(
                user_request=user_request,
                context=context,
                max_steps=max_steps,
                abilities=abilities
            )

        messages = [{"role": "user", "content": prompt}]

        if reminder:
            messages.append({"role": "system", "content": f"<system-reminder>{reminder.strip()}</system-reminder>"})

        response = ''

        async with client.chat.completions.stream(
            model=settings.llm_model_id,
            messages=messages,
            seed=int(time.time())
        ) as stream:
            async for event in stream:
                if event.type == 'content.delta':
                    response += event.delta

        response_text = strip_markers(response, (("think", False), ))

        if "<done/>" in response_text.strip().lower() and len(list_of_steps) > 0:
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
