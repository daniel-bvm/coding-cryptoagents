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

ONE_SHOT_TEMPLATE = """
You are a planning assistant for generating a professional HTML report that explains in layman's terms (explain like you are talking to a child) for what the user is looking for. Generate a complete plan as a list of steps. Each step must be one of: research (deep research for required information), plan (plan report structure), build (create the main index.html). The plan should have at most {max_steps} steps. Do not suggest specific content of each step, only give high-level instructions of what to do.

Content types and handling:
- LaTeX research papers: Extract exact text, equations (use MathJax/KaTeX), figures, tables, citations from .bib files
- Company introductions: Gather company info, products, team, mission, vision, achievements from provided materials
- Problem statements: Extract problem context, challenges, requirements, constraints from source documents
- General presentations: Organize any structured content into a logical presentation flow

Strict anti-hallucination rules:
- Use ONLY content grounded in the provided source materials. Do not invent, fabricate, or add external information.
- Extract exact text, numbers, dates, names, and claims. If a detail is unavailable or uncertain, write "Unknown" or add a TODO.
- For LaTeX sources: preserve equations verbatim and plan to render them via MathJax/KaTeX in HTML.
- For any content: maintain original meaning; avoid interpretations not explicitly supported by sources.

The plan should strictly follow the 2-steps process below:
1) Content Preparation (research): deep research for required information and write a detailed report.
2) Report Planning (plan): plan the structure and content of the report.
3) HTML Generation and Review (finalize): read the report and build a professional, visual stunning, rich of meaningful content HTML report with proper formatting, styling, and image integration.

Step-specific deliverables:
- Step 1 (Deep Research): `gathered_information.md` (report), `sources.json`
- Step 2 (Report Planning): `report_plan.md`
- Step 3 (HTML Generation): `index.html` files (HTML report)

Use the user's tone of voice for connective prose only;

{note}

The user wants:
{title}: {user_request}

Generate the complete plan as a JSON array of steps. Each step should have: "reason", "task", "expectation", "step_type".

Respond in JSON format: [
  {{ "reason": "...", "task": "...", "expectation": "...", "step_type": "research/plan/build" }},
  ...
]

The current timestamp is {current_time}
"""

MAX_RETRY = 5

# async def gen_plan(title: str, information: str, user_request: str, max_steps: int = 3) -> AsyncGenerator[StepV2, None]:
#     logger.info(f"Making plan for user request: {user_request} (Title: {title})")

#     list_of_steps: list[StepV2] = []
#     client = AsyncClient(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
#     has_build_step, has_plan_step = False, False

#     while True and len(list_of_steps) < max_steps:
#         context = "\n".join([f"{i+1}. {step.task}: {step.expectation} ({step.step_type})" for i, step in enumerate(list_of_steps)])
        
#         if not has_plan_step:
#             note = f'The plan should include at least one research step to gather information.'

#         elif not has_build_step:
#             note = f'The plan should include at least one build step to create the final product or report.'

#         else:
#             note = f"The plan should be completed in maximum {max_steps} steps." if len(list_of_steps) > max_steps // 2 else ""

#         prompt = COT_TEMPLATE.format(
#             user_request=user_request,
#             context=context,
#             information=information,
#             max_steps=max_steps,
#             title=title,
#             note=note
#         )

#         response = ''

#         async with client.chat.completions.stream(
#             model=settings.llm_model_id,
#             messages=[{"role": "user", "content": prompt}]
#         ) as stream:
#             async for event in stream:
#                 if event.type == 'content.delta':
#                     response += event.delta

#         response_text = strip_thinking_content(response)

#         if "<done/>" in response_text.strip().lower():
#             break

#         try:
#             l, r = response_text.find('{'), response_text.rfind('}')+1
#             step_data: dict = json.loads(repair_json(response_text[l:r]))
#             step = StepV2(**step_data)

#             has_build_step = has_build_step or step.step_type == 'build'
#             has_plan_step = has_plan_step or step.step_type == 'research'

#             list_of_steps.append(step)
#             logger.info(f"Added {step.step_type} step: {step.task} (Reason: {step.reason}; Expectation: {step.expectation})")
#             yield step
#         except Exception as e:
#             logger.error(f"[2] Failed to parse response: {e}")


async def gen_plan_v2(title: str, information: str, user_request: str, max_steps: int = 5) -> AsyncGenerator[StepV2, None]:
    logger.info(f"Generating plan for user request: {user_request} (Title: {title})")

    client = AsyncClient(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    error_note = ""

    retry = 0
    seed = NOT_GIVEN

    while retry < MAX_RETRY:        
        prompt = ONE_SHOT_TEMPLATE.format(
            user_request=user_request,
            max_steps=max_steps,
            title=title,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            note=error_note,
        )

        search_results = await search(title)
        search_context = await format_web_search_context(search_results)
        prompt = prompt + search_context

        response = ''

        async with client.chat.completions.stream(
            model=settings.llm_model_id,
            messages=[{"role": "user", "content": prompt}],
            seed=seed,
        ) as stream:
            async for event in stream:
                if event.type == 'content.delta':
                    response += event.delta

        response_text = strip_thinking_content(response)

        try:
            logger.info(f"[gen_plan_v2] Response text: {response_text}")
            response_text = process_json_response(response_text)
            step_data: dict = json.loads(repair_json(response_text))
            step_list = StepV2List.validate_python(step_data)

            if step_list[0].step_type != 'research':
                error_note += "The first step must be a research step\n"
            if step_list[-1].step_type != 'build':
                error_note += "The last step must be a build step\n"

            if error_note:
                raise Exception(error_note)

            for step in step_list:
                logger.info(f"Added {step.step_type} step: {step.task} (Reason: {step.reason}; Expectation: {step.expectation})")
                yield step
            
            return
        except Exception as e:
            logger.error(f"[2] Failed to generate plan: {e}", exc_info=True)
            seed = random.randint(0, 1000000)
            retry += 1

    raise Exception("Failed to generate plan")
