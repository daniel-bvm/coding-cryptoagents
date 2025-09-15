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

REVIEW_SYSTEM_PROMPT = """Your task is to review the project of a static site or a blog post based on the plan. Strictly, follow the criteria one-by-one, to do the feedback. Feedback must be written in `Feedback.md` file or edit it if found. Your final output should be short, talk about what you want to fix. If all the criteria are satisfied, write 'completed successfully' to the end of the `success.md`file. You only have 3 attempts to review the project."""

REBUILD_SYSTEM_PROMPT = """Your task is to read the feedback from `Feedback.md` and edit the `index.html` file to fix all the issues mentioned in the feedback. You must:

1. Read and understand the `Feedback.md` file completely
2. Edit the `index.html` file to address ALL feedback points
3. Make precise changes to fix layout, typography, colors, images, and accessibility issues
4. Ensure the final result satisfies all criteria mentioned in the feedback
5. Do not make any changes beyond what's requested in the feedback

Your final output should be short, explaining what you have fixed."""

async def execute_research_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None, task_id: str = None) -> ClaudeCodeStepOutput:

    async with OpenCodeSDKClient(workdir) as client:
        for i, msg in enumerate([steps.task, 'Seems you faced an issue, please try again.', 'One last try']):
            logger.info(f"Try {i+1} of 3: {msg}")

            output = await client.query(
                agent="deep-research",
                system=PLANNING_SYSTEM_PROMPT,
                message=msg,
                session_id=session_id,
                model_id=settings.llm_model_id,
                task_id=task_id,
            )

            output = strip_thinking_content(output).strip()

            has_gathered_information_files = len(glob.glob(os.path.join(workdir, "**/gathered_information.md"), recursive=True)) > 0

            if output and has_gathered_information_files:
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

async def execute_plan_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None, task_id: str = None) -> ClaudeCodeStepOutput:

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

            has_slides_plan_files = len(glob.glob(os.path.join(workdir, "**/slides_plan.md"), recursive=True)) > 0

            if output and has_slides_plan_files:
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

async def execute_review_and_rebuild_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None, task_id: str = None) -> ClaudeCodeStepOutput:
    """
    Execute a complete review and rebuild cycle:
    1. Review the index.html and generate Feedback.md
    2. Read the feedback and edit index.html to fix issues
    3. Repeat until feedback is satisfied or max iterations reached
    """
    max_iterations = 3
    iteration = 0
    final_output = ""
    
    async with OpenCodeSDKClient(workdir) as client:
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Review and rebuild iteration {iteration}/{max_iterations}")
            
            # Step 1: Generate feedback (review)
            feedback_generated = False
            for i, msg in enumerate([steps.task, 'Seems you faced an issue, please try again.', 'One last try']):
                session_id_review = await client.create_session("Reviewing...")
                logger.info(f"Review attempt {i+1} of 3: {msg}")

                review_output = await client.query(
                    agent="qa-reviewer",
                    system=REVIEW_SYSTEM_PROMPT,
                    message=msg,
                    session_id=session_id_review,
                    model_id=settings.llm_model_id_code,
                    task_id=task_id,
                )

                review_output = strip_thinking_content(review_output).strip()
                has_feedback_files = len(glob.glob(os.path.join(workdir, "**/Feedback.md"), recursive=True)) > 0
                
                if review_output and has_feedback_files:
                    feedback_generated = True
                    final_output += f"Iteration {iteration} - Review: {review_output}\n"
                    break

                if i < 2:
                    await asyncio.sleep(2 ** (i + 2))

            if not feedback_generated:
                raise Exception(f"Review step failed to generate feedback after 3 attempts")

            # Check if feedback indicates satisfaction (no issues)
            check_files = glob.glob(os.path.join(workdir, "**/check_success.md"), recursive=True)
            if check_files:
                try:
                    with open(check_files[0], 'r', encoding='utf-8') as f:
                        feedback_content = f.read().lower()
                    
                    # Check for satisfaction indicators
                    satisfaction_keywords = 'completed successfully'
                    if satisfaction_keywords in feedback_content:
                        logger.info("Feedback indicates satisfaction - stopping iteration")
                        final_output += f"Feedback satisfied after {iteration} iteration(s)."
                        break
                except Exception as e:
                    logger.warning(f"Could not read feedback file: {e}")

            # Step 2: Apply feedback (rebuild)
            rebuild_msg = f"Read the Feedback.md file and edit the index.html file to fix all the issues mentioned. This is iteration {iteration} of the review and rebuild process."
            
            rebuild_success = False
            for i, rebuild_attempt_msg in enumerate([rebuild_msg, 'Please try to fix the issues again.', 'One final attempt to fix the issues.']):
                session_id_rebuild = await client.create_session("Rebuilding...")
                logger.info(f"Rebuild attempt {i+1} of 3")

                rebuild_output = await client.query(
                    agent="developer",
                    system=REBUILD_SYSTEM_PROMPT,
                    message=rebuild_attempt_msg,
                    session_id=session_id_rebuild,
                    model_id=settings.llm_model_id_code,
                    task_id=task_id,
                )

                rebuild_output = strip_thinking_content(rebuild_output).strip()
                
                # Check if index.html still exists and was modified
                index_files = glob.glob(os.path.join(workdir, "**/index.html"), recursive=True)
                if rebuild_output and index_files:
                    rebuild_success = True
                    final_output += f"Iteration {iteration} - Rebuild: {rebuild_output}\n"
                    break

                if i < 2:
                    await asyncio.sleep(2 ** (i + 2))

            if not rebuild_success:
                logger.warning(f"Rebuild failed in iteration {iteration}")
                break

        # Final check
        has_index_html = len(glob.glob(os.path.join(workdir, "**/index.html"), recursive=True)) > 0
        if not has_index_html:
            raise Exception(f"Review and rebuild step failed - no index.html found after {iteration} iterations")

        if not final_output:
            raise Exception(f"Review and rebuild step {steps.id} failed to generate any output")

        final_output += f"\nCompleted review and rebuild process after {iteration} iteration(s)."

    return ClaudeCodeStepOutput(
        step_id=steps.id,
        full=final_output,
        session_id=session_id,
    )
    


async def execute_steps_v2(
    steps_type: Literal["research", "plan", "build", "feedback"], 
    steps: StepV2, 
    workdir: str,
    session_id: Union[int, str],
    task_id: str,
) -> ClaudeCodeStepOutput:
    if steps_type == "research":
        return await execute_research_step(steps, workdir, session_id, task_id)

    if steps_type == "plan":
        return await execute_plan_step(steps, workdir, session_id, task_id)

    if steps_type == "feedback":
        return await execute_review_and_rebuild_step(steps, workdir, session_id, task_id)
    
    if steps_type == "build":
        return await execute_build_step(steps, workdir, session_id, task_id)

    raise ValueError(f"Invalid steps type: {steps_type}")
