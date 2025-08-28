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

COT_TEMPLATE = """
You are a planning assistant for generating professional HTML presentations from various content sources. Break the request into a sequence of steps. Each step must be one of: research (collect/organize exact content from source materials) or build (create files, code, assets). Ensure steps form a coherent flow: research steps first, then build steps. The FIRST step MUST be a research step. Never start with a build step, even if sources seem obvious. If no sources are provided, plan research to gather them before any build.

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

Recommended phases:
1) Research: analyze source structure, identify key topics/sections, collect exact quotes/snippets, list figures/tables with captions, organize content hierarchy for the presentation
2) Build: finalize design system (fonts, colors, spacing), create reusable templates, generate the HTML presentation with MathJax for equations where needed, insert exact content and assets, produce final `index.html` and `assets/`

Deliverables to target: `slides/outline.md`, `slides/content/*.md` (exact content snippets), `slides/metadata.json` (content mapping), `presentation/index.html`, `presentation/assets/`.

Use the user's tone of voice for connective prose only; keep all factual statements exact from source materials.

Note: {note}
Current UTC time: {current_time}

The user wants:
{title}: {user_request}

So far, these are the steps planned:
{context}

What is the next step we should do?
Respond in JSON format: {{ "reason": "...", "task": "...", "expectation": "...", "step_type": "...(research or build)" }}
If no more are needed, just return: <done/>.

The current timestamp is {current_time}
"""

async def gen_plan(title: str, user_request: str, max_steps: int = 5) -> AsyncGenerator[StepV2, None]:
    logger.info(f"Generating plan for user request: {user_request} (Title: {title})")

    list_of_steps: list[StepV2] = []
    client = AsyncClient(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    has_build_step, has_plan_step = False, False

    while True and len(list_of_steps) < max_steps:
        context = "\n".join([f"{i+1}. {step.task}: {step.expectation} ({step.step_type})" for i, step in enumerate(list_of_steps)])
        
        if not has_plan_step:
            note = f'The plan should include at least one research step to gather information. The first step MUST be research.'

        elif not has_build_step:
            note = f'The plan should include at least one build step to create the final slide presentation.'

        else:
            note = f"The plan should be completed in maximum {max_steps} steps." if len(list_of_steps) > max_steps // 2 else ""

        prompt = COT_TEMPLATE.format(
            user_request=user_request,
            context=context,
            max_steps=max_steps,
            title=title,
            note=note,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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

            has_build_step = has_build_step or step.step_type == 'build'
            has_plan_step = has_plan_step or step.step_type == 'research'

            list_of_steps.append(step)
            logger.info(f"Added {step.step_type} step: {step.task} (Reason: {step.reason}; Expectation: {step.expectation})")
            yield step
        except Exception as e:
            logger.error(f"[2] Failed to parse response: {e}")
