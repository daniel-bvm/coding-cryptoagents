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
You are an analytical assistant. Your task is to read the information and break the user request into a list of steps, each step should be clearly describe a single action with expectation output. In advance, each step should be one of research (search for information) or build (write down the HTML report, etc). It should be at least one step to define style, layout, a color palette to be used during development, focus on the contrast between background and main content. In each step, it should be solid link with the previous, the task should be solved with some research steps first, followed by build steps. Output must be professional, visual stunning, rich of meaningful content, no need to use any images. More important, your voice should be in the user's voice (like the user is self-talking). The final output must include an index.html file in the project root. To style the project, make plans to utilize Tailwind CSS as much as possible to save time and resources. Only write and review, no deployment, documents are needed. {note}. Finally, do not plan to mock the data to write the report, plan research to collect more information instead.

The user wants:
{title}: {user_request}

These information are gathered:
{information}

So far, these are the steps planned:
{context}

What is the next step should we do? 
Respond in JSON format: {{ "reason": "...", "task": "...", "expectation": "...", "step_type": "...(research or build)" }}
If no more are needed, just return: <done/> (no need to explain anything).
"""

async def gen_plan(title: str, user_request: str, information: str, max_steps: int = 3) -> AsyncGenerator[StepV2, None]:
    logger.info(f"Making plan for user request: {user_request} (Title: {title})")

    list_of_steps: list[StepV2] = []
    client = AsyncClient(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    has_build_step, has_plan_step = False, False

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
            information=information,
            max_steps=max_steps,
            title=title,
            note=note
        )

        response = await client.chat.completions.create(
            model=settings.llm_model_id,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = strip_thinking_content(response.choices[0].message.content)

        if "<done/>" in response_text.strip().lower():
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
