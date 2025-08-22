from openai import AsyncClient
from typing import Any, AsyncGenerator
from agent.configs import settings
import json
import logging
from agent.app_models import StepV2
from agent.utils import strip_thinking_content
from json_repair import repair_json

logger = logging.getLogger(__name__)

COT_TEMPLATE = """
You are an analytical assistant. Your task is to break the user request into a list of steps, each step should be clearly describe a single action with expectation output. In advance, each step should be categorized into plan (search for information) or build (write down the code, etc). At each step, it should be solid link with the previous, the task should be solved with some plan steps first, followed by build steps. More important, your voice should be in the user's voice (like the user is self-talking). The final output should be a one page static site that is simple, colorful, rich of animations. It must has an index.html to include the main content, respond to the user message, also js, css files to make up the view. To style the view, utilize Vanilla CSS as much as possible to save time. For mockup images, search them from the internet and use directly (download them and store locally if needed). No deployment needed, only write and review. {note}. Do not plan to mock the data to write the report, the plan agent is accessible to any database in the world, just need to write a good plan to execute.

The user wants:
{title}: {user_request}

So far, these are the steps planned:
{context}

What is the next step should we do? 
Respond in JSON format: {{ "reason": "...", "task": "...", "expectation": "...", "step_type": "...(plan or build)" }}
If no more are needed, just return: <done/>.
"""

async def make_plan(title: str, user_request: str, max_steps: int = 5) -> list[StepV2]:
    logger.info(f"Making plan for user request: {user_request} (Title: {title})")

    list_of_steps: list[StepV2] = []
    client = AsyncClient(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    while True and len(list_of_steps) < max_steps:
        context = "\n".join([f"{i+1}. {step.task}: {step.expectation} ({step.step_type})" for i, step in enumerate(list_of_steps)])
        prompt = COT_TEMPLATE.format(
            user_request=user_request,
            context=context,
            max_steps=max_steps,
            title=title,
            note=f"The plan should be completed in maximum {max_steps} steps." if len(list_of_steps) >= max_steps // 2 else ""
        )

        response = await client.chat.completions.create(
            model=settings.llm_model_id,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = strip_thinking_content(response.choices[0].message.content)

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
            list_of_steps.append(step)
            logger.info(f"Added {step.step_type} step: {step.task} (Reason: {step.reason}; Expectation: {step.expectation})")
        except Exception as e:
            logger.error(f"[1] Failed to parse response: {e}")

    return list_of_steps



async def gen_plan(title: str, user_request: str, max_steps: int = 15) -> AsyncGenerator[StepV2, None]:
    logger.info(f"Making plan for user request: {user_request} (Title: {title})")

    list_of_steps: list[StepV2] = []
    client = AsyncClient(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    while True and len(list_of_steps) < max_steps:
        context = "\n".join([f"{i+1}. {step.task}: {step.expectation} ({step.step_type})" for i, step in enumerate(list_of_steps)])
        prompt = COT_TEMPLATE.format(
            user_request=user_request,
            context=context,
            max_steps=max_steps,
            title=title,
            note=f"The plan should be completed in maximum {max_steps} steps." if len(list_of_steps) >= max_steps // 2 else ""
        )

        response = await client.chat.completions.create(
            model=settings.llm_model_id,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = strip_thinking_content(response.choices[0].message.content)

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
            list_of_steps.append(step)
            logger.info(f"Added {step.step_type} step: {step.task} (Reason: {step.reason}; Expectation: {step.expectation})")
            yield step
        except Exception as e:
            logger.error(f"[2] Failed to parse response: {e}")
