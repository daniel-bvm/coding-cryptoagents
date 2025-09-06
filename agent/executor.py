import json
import os
import requests
from agent.app_models import StepV2, ClaudeCodeStepOutput
import logging
from typing import Optional, Union
from agent.configs import settings
from agent.opencode_sdk import OpenCodeSDKClient
from agent.utils import strip_thinking_content
import asyncio
import glob

logger = logging.getLogger(__name__)
from typing import Optional, Literal

PLANNING_SYSTEM_PROMPT = """Your task is to collect information that needed to respond to the user request including text and imge urls if needed. Do not ask again for confirmation, just do it your way. Do not take any extra steps. Your output should include what you have found related to the request. You dont need to plan or write any code, just collect information."""

BUILD_SYSTEM_PROMPT = """Your task is to build the project, a static site or a blog post based on the plan. Strictly, follow the plan step-by-step, do not take any extra steps. Do not ask again for confirmation, just do it your way. Code and assets must be written into files. Your final output should be short, talk about what you have done (no code explanation in detail is required)."""

async def execute_research_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None, task_id: str = None) -> ClaudeCodeStepOutput:

    async with OpenCodeSDKClient(workdir) as client:
        for i, msg in enumerate([steps.task, 'Seems you faced an issue, please try again.', 'One last try']):
            logger.info(f"Try {i+1} of 3: {msg}")

            output = await client.query(
                agent="content-prep",
                system=PLANNING_SYSTEM_PROMPT,
                message=msg,
                session_id=session_id,
                model_id=settings.llm_model_id,
                task_id=task_id,
            )

            output = strip_thinking_content(output).strip()

            has_slides_markdown_files = len(glob.glob(os.path.join(workdir, "**/Slides_*.md"), recursive=True)) > 0

            if output and has_slides_markdown_files:
                break

            if i < 2:
                await asyncio.sleep(2 ** (i + 2)) # wait for 4, 8, 16 seconds, wait until service available back

    if not output:
        raise Exception(f"Research step {steps.id} failed to generate any output")

    return ClaudeCodeStepOutput(
        step_id=steps.id,
        full=output,
        session_id=session_id,
    )

async def execute_build_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None, task_id: str = None) -> ClaudeCodeStepOutput:
    note = ""
    async with OpenCodeSDKClient(workdir) as client:
        for i, msg in enumerate([steps.task, 'Seems you faced an issue, please try again.', 'One last try']):
            fixed_msg = msg + note
            logger.info(f"Try {i+1} of 3: {fixed_msg}")

            output = await client.query(
                agent="slide-builder",
                system=BUILD_SYSTEM_PROMPT,
                message=[
                    {
                        'type': 'text',
                        'text': fixed_msg
                    },
                    # {
                    #     'type': 'text',
                    #     'text': '<system-reminder>\nCRITICAL: Build mode ACTIVE. All of your code, resources should be written into files. Make sure all folders created before using them.</system-reminder>'
                    # }
                ],
                session_id=session_id,
                model_id=settings.llm_model_id_code,
                task_id=task_id,
            )

            output = strip_thinking_content(output).strip()
            
            has_slides_html_files = len(glob.glob(os.path.join(workdir, "**/Slides_*.html"), recursive=True)) > 0
            
            if output and has_slides_html_files:
                break

            if i < 2:
                await asyncio.sleep(2 ** (i + 2)) # wait for 4, 8, 16 seconds, wait until service available back

    if not output:
        raise Exception(f"Build step {steps.id} failed to generate any output")

    return ClaudeCodeStepOutput(
        step_id=steps.id,
        full=output,
        session_id=session_id,
    )


async def execute_finalize_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None, task_id: str = None) -> ClaudeCodeStepOutput:
    async with OpenCodeSDKClient(workdir) as client:
        for i, msg in enumerate([steps.task, 'Seems you faced an issue, please try again.', 'One last try']):
            logger.info(f"Try {i+1} of 3: {msg}")

            output = await client.query(
                agent="developer",
                system=BUILD_SYSTEM_PROMPT,
                message=msg,
                session_id=session_id,
                model_id=settings.llm_model_id_code,
                task_id=task_id,
            )

            output = strip_thinking_content(output).strip()

            has_index_html_files = len(glob.glob(os.path.join(workdir, "**/index.html"), recursive=True)) > 0
            
            if output and has_index_html_files:
                break

            if i < 2:
                await asyncio.sleep(2 ** (i + 2)) # wait for 4, 8, 16 seconds, wait until service available back

    if not output:
        raise Exception(f"Build step {steps.id} failed to generate any output")

    return ClaudeCodeStepOutput(
        step_id=steps.id,
        full=output,
        session_id=session_id
    )


async def execute_steps_v2(
    steps_type: Literal["research", "build", "finalize"], 
    steps: StepV2, 
    workdir: str,
    session_id: Union[int, str],
    task_id: str,
) -> ClaudeCodeStepOutput:
    if steps_type == "research":
        return await execute_research_step(steps, workdir, session_id, task_id)

    if steps_type == "build":
        return await execute_build_step(steps, workdir, session_id, task_id)
    
    if steps_type == "finalize":
        return await execute_finalize_step(steps, workdir, session_id, task_id)

    raise ValueError(f"Invalid steps type: {steps_type}")
