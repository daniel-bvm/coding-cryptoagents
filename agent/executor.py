from agent.app_models import StepV2, ClaudeCodeStepOutput
import logging
from typing import Optional, Union
from agent.configs import settings
from agent.opencode_sdk import OpenCodeSDKClient
from agent.utils import strip_thinking_content

logger = logging.getLogger(__name__)
from typing import Optional, Literal

PLANNING_SYSTEM_PROMPT = """Your task is to collect information that needed to respond to the user request including text and imge urls if needed. Do not ask again for confirmation, just do it your way. Do not take any extra steps. Your output should include what you have found related to the request. You dont need to plan or write any code, just collect information."""

BUILD_SYSTEM_PROMPT = """Your task is to build the project, a static site or a blog post based on the plan. Strictly, follow the plan step-by-step, do not take any extra steps. Do not ask again for confirmation, just do it your way. Code and assets must be written into files. Your final output should be short, talk about what you have done (no code explanation in detail is required)."""

async def execute_plan_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None) -> ClaudeCodeStepOutput:

    async with OpenCodeSDKClient(workdir) as client:
        output = await client.query(
            agent="build",
            system=PLANNING_SYSTEM_PROMPT,
            message=steps.task,
            session_id=session_id,
            model_id=settings.llm_model_id,
        )
        output = strip_thinking_content(output).strip()

    if not output:
        return ClaudeCodeStepOutput(
            step_id=steps.id,
            full=f'{steps.task} completed without generating any output',
            session_id=session_id
        )

    return ClaudeCodeStepOutput(
        step_id=steps.id,
        full=output,
        session_id=session_id
    )

async def execute_build_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None) -> ClaudeCodeStepOutput:
    async with OpenCodeSDKClient(workdir) as client:
        output = await client.query(
            agent="build",
            system=BUILD_SYSTEM_PROMPT,
            message=[
                {
                    'type': 'text',
                    'text': steps.task
                },
                # {
                #     'type': 'text',
                #     'text': '<system-reminder>\nCRITICAL: Build mode ACTIVE. All of your code, resources should be written into files. Make sure all folders created before using them.</system-reminder>'
                # }
            ],
            session_id=session_id,
            model_id=settings.llm_model_id_code,
        )
        output = strip_thinking_content(output).strip()

    if not output:
        return ClaudeCodeStepOutput(
            step_id=steps.id,
            full=f'{steps.task} completed without any output',
            session_id=session_id
        )

    return ClaudeCodeStepOutput(
        step_id=steps.id,
        full=output,
        session_id=session_id
    )

async def execute_steps_v2(
    steps_type: Literal["plan", "build"], 
    steps: StepV2, 
    workdir: str,
    session_id: Union[int, str]
) -> ClaudeCodeStepOutput:
    if steps_type == "plan":
        return await execute_plan_step(steps, workdir, session_id)

    if steps_type == "build":
        return await execute_build_step(steps, workdir, session_id)

    raise ValueError(f"Invalid steps type: {steps_type}")
