from agent.app_models import StepV2, ClaudeCodeStepOutput
import logging
from typing import Optional, Union
from agent.configs import settings
from agent.opencode_sdk import OpenCodeSDKClient
from agent.utils import strip_thinking_content
import asyncio

logger = logging.getLogger(__name__)
from typing import Optional, Literal

PLANNING_SYSTEM_PROMPT = """Your task is to collect information that needed to respond to the user request including text and image urls if needed. Do not ask again for confirmation, just do it your way. Do not take any extra steps. Your output should include what you have found related to the request. You dont need to plan or write any code, just collect information.

CRITICAL DATA ACCURACY REQUIREMENTS:
- When working with financial data, you MUST use ONLY real data from the financial datasets tools (get_income_statements, get_balance_sheets, get_cash_flow_statements, get_current_stock_price, get_historical_stock_prices, etc.)
- NEVER fabricate, estimate, or make up any financial numbers, percentages, or data points
- If financial data is not available through the tools, clearly state this limitation rather than creating fictional data
- All numerical data in your research must be sourced from actual API calls to financial datasets
- When collecting information, prioritize accuracy over completeness - it's better to have limited real data than comprehensive fake data"""

BUILD_SYSTEM_PROMPT = """Your task is to build the project, a static site or a blog post based on the plan. Strictly, follow the plan step-by-step, do not take any extra steps. Do not ask again for confirmation, just do it your way. Code and assets must be written into files. Your final output should be short, talk about what you have done (no code explanation in detail is required).

CRITICAL VISUALIZATION DATA REQUIREMENTS:
- When creating charts, graphs, or visualizations, you MUST use ONLY the real financial data that was collected in the research phase
- NEVER generate, fabricate, or make up any data points, numbers, or values for visualizations
- If you need additional data for charts, you MUST call the financial datasets tools to get real data
- All chart data must be sourced from actual API responses from financial datasets tools
- If insufficient data is available for a complete visualization, create a partial chart with available data and clearly label what data is missing
- Do not interpolate, estimate, or fill in missing data points - use only what is actually available
- When building visualizations, prioritize data accuracy over visual completeness"""

async def execute_research_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None) -> ClaudeCodeStepOutput:

    async with OpenCodeSDKClient(workdir) as client:
        for i, msg in enumerate([steps.task, 'Seems you faced an issue, please try again.', 'One last try']):
            logger.info(f"Try {i+1} of 3: {msg}")

            output = await client.query(
                agent="build",
                system=PLANNING_SYSTEM_PROMPT,
                message=msg,
                session_id=session_id,
                model_id=settings.llm_model_id,
            )

            output = strip_thinking_content(output).strip()

            if output:
                break

            if i < 2:
                await asyncio.sleep(2 ** (i + 2)) # wait for 4, 8, 16 seconds, wait until service available back

    if not output:
        raise Exception(f"Research step {steps.id} failed to generate any output")

    return ClaudeCodeStepOutput(
        step_id=steps.id,
        full=output,
        session_id=session_id
    )

async def execute_build_step(steps: StepV2, workdir: str, session_id: Optional[Union[int, str]] = None) -> ClaudeCodeStepOutput:
    async with OpenCodeSDKClient(workdir) as client:
        for i, msg in enumerate([steps.task, 'Seems you faced an issue, please try again.', 'One last try']):
            logger.info(f"Try {i+1} of 3: {msg}")

            output = await client.query(
                agent="build",
                system=BUILD_SYSTEM_PROMPT,
                message=[
                    {
                        'type': 'text',
                        'text': msg
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
            
            if output:
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
    steps_type: Literal["research", "build"], 
    steps: StepV2, 
    workdir: str,
    session_id: Union[int, str]
) -> ClaudeCodeStepOutput:
    if steps_type == "research":
        return await execute_research_step(steps, workdir, session_id)

    if steps_type == "build":
        return await execute_build_step(steps, workdir, session_id)

    raise ValueError(f"Invalid steps type: {steps_type}")
