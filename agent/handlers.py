RECEPTIONIST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "build",
            "description": "Start planning, researching anything, and building a static website, report or blog post using HTML, CSS and Javascript.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Name the project, website or blog post."
                    },
                    "expectation": {
                        "type": "string", 
                        "description": "Describe what to build as much detail as possible.",
                    }
                },
                "required": ["title", "expectation"]
            }
        }
    }
]

RECEPTIONIST_SYSTEM_PROMPT = """
Your task is to first communicate with the user and determine the next step, build, or ask the user for more details if it is too vague, etc. Especially, we are helping user to build their website or a blog post (that broadcasts content to the audience). User is busy, so they do not want to communicate too much. You only have to ask them for more details in some specific cases:
- Their core idea is too unclear.
- Greeting.

In other cases, you are free to guess what they want and call the build tool. We can solve any problems. Any valid request, send it to us, then the user will get what they want.
"""

from agent.oai_models import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionStreamResponse
from agent.utils import refine_chat_history, refine_assistant_message
from agent.configs import settings
from agent.oai_streaming import create_streaming_response, ChatCompletionResponseBuilder
from typing import AsyncGenerator, Any, List
import logging
import json

logger = logging.getLogger(__name__)

import os
from agent.planner import StepV2, gen_plan
from agent.app_models import StepOutput, ClaudeCodeStepOutput
from agent.executor import execute_steps_v2
from agent.opencode_sdk import OpenCodeSDKClient
from agent.oai_models import ChatCompletionStreamResponse
from agent.utils import wrap_chunk, random_uuid, inline_html
import glob
import base64
from mimetypes import guess_type

def compose_steps(steps: List[StepV2], task_offset_1: int = 1) -> StepV2:
    step_type, task, expectation, reason = steps[0].step_type, '', '', ''

    for i, step in enumerate(steps):
        task += f"Step {i + task_offset_1}: {step.reason}; {step.task}\n" \
              + f"- Expectation: {step.expectation}\n\n"

        expectation += f"Step {i + task_offset_1}: {step.expectation}\n"
        reason += f"Step {i + task_offset_1}: {step.reason}\n"

    return StepV2(
        step_type=step_type, 
        task=task.strip(),
        expectation=expectation.strip(),
        reason=reason.strip()
    )
    

def segment_steps_by_type(steps: list[StepV2]) -> List[List[StepV2]]:
    if not steps:
        logger.warning("No steps provided")
        return []

    results: list[list[StepV2]] = []
    it = 0

    while it < len(steps) - 1:
        seg: list[StepV2] = []
        seg.append(steps[it])
        it += 1

        while it < len(steps) and steps[it].step_type == steps[it-1].step_type and len(seg) < 4:
            seg.append(steps[it])
            it += 1

        results.append(seg)

    results.append([steps[-1]]) # keep the final step separate
    return results



def create_data_uri(file_path: str) -> str:
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    encoded_data = base64.b64encode(file_bytes).decode("utf-8")
    mime_type = guess_type(file_path)[0] or "application/octet-stream"
    return f"data:{mime_type};base64,{encoded_data}"

def construct_file_response(file_paths: list[str]) -> str:
    files_xml = ""

    for file_path in file_paths:
        if not os.path.exists(file_path):
            continue

        try:
            filename = os.path.basename(file_path)
            data_uri = create_data_uri(file_path)
            files_xml += (
                f"  <file>\n"
                f"    <filename>{filename}</filename>\n"
                f"    <filedata>{data_uri}</filedata>\n"
                f"  </file>\n"
            )
        except Exception as e:
            continue

    return f"<files>{files_xml}</files>"

async def build(title: str, expectation: str) -> AsyncGenerator[ChatCompletionStreamResponse | ChatCompletionResponse, None]: # recap
    assert expectation is not None, "No task definition provided"
    yield wrap_chunk(random_uuid(), f"<action>Planning...</action>\n")

    # steps: List[StepV2] = await make_plan(title, expectation)
    steps: List[StepV2] = []
    
    async for step in gen_plan(title, expectation, 3):
        steps.append(step)

        yield wrap_chunk(random_uuid(), f"<action>{step.reason}</action>\n")
        yield wrap_chunk(random_uuid(), f"<details><summary>Todo</summary>{step.task}</details>\n")
        yield wrap_chunk(random_uuid(), f"<details><summary>Expected</summary>{step.expectation}</details>\n")

    if not steps:
        yield "Planner is quite tired now, he's sleeping. The task can not be completed at this moment, please come back later."
        return

    task_id = os.urandom(4).hex()
    workdir = os.path.abspath(os.path.join(settings.opencode_directory, task_id))
    os.makedirs(workdir, exist_ok=True)

    segmented_steps: List[List[StepV2]] = segment_steps_by_type(steps)
    steps_output: list[StepOutput] = []
    
    async with OpenCodeSDKClient(workdir) as client:
        session_id = await client.create_session(title)

    logger.info(f"Task {task_id}; Building... (Session ID: {session_id})")

    yield wrap_chunk(random_uuid(), f"<action>Building...</action>\n")

    for i in range(len(steps_output), len(segmented_steps)):
        logger.info(f"Task {task_id} ({expectation[:128]}); Progress: {len(steps_output)}/{len(segmented_steps)}")
        
        steps = segmented_steps[i]

        for step in steps:
            yield wrap_chunk(random_uuid(), f"<action>{step.task}</action>\n")

        task_offset_1 = sum(len(e) for e in segmented_steps[:i]) + 1
        composed_step = compose_steps(steps, task_offset_1)
        logger.info(f"Task {task_id}; Executing step: {composed_step.task}")

        step_output: ClaudeCodeStepOutput = await execute_steps_v2(
            composed_step.step_type, 
            composed_step, 
            workdir,
            session_id
        )

        logger.info(f"Task {task_id} ({expectation[:128]}...); Step output: {step_output.full}")
        steps_output.append(step_output)

    recap = 'These step(s) have been executed:\n'

    for i, (step_output, steps) in enumerate(zip(steps_output, segmented_steps)):
        task_offset_1 = sum(len(e) for e in segmented_steps[:i]) + 1
        composed_step = compose_steps(steps, task_offset_1)

        recap += f"Task: {composed_step.task}\n"
        recap += f"Output: {step_output.full}\n\n"

    found = glob.glob(os.path.join(workdir, "**", "index.html"), recursive=True)

    if len(found) > 1:
        logger.warning(f"Multiple index.html files found in {workdir}: {found}. Picking the first one.")
        found = [found[0]]

    if found:
        recap += "File index.html has been sent to the user."
        index_html = await inline_html(found[0])
        yield wrap_chunk(random_uuid(), construct_file_response([index_html]))

    with open('debug.json', 'w') as f:
        json.dump({
            "recap": recap,
            "steps": [step.model_dump() for step in steps],
            "output": [step_output.model_dump() for step_output in steps_output]
        }, f, indent=2)

    yield recap

async def handle_request(request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionStreamResponse | ChatCompletionResponse, None]:
    messages = request.messages
    assert len(messages) > 0, "No messages in the request"
 
    system_prompt = RECEPTIONIST_SYSTEM_PROMPT
    messages: list[dict[str, Any]] = refine_chat_history(messages, system_prompt)

    oai_tools = RECEPTIONIST_TOOLS
    finished = False

    n_calls, max_calls = 0, 1
    use_tool_calls = lambda: n_calls < max_calls and not finished

    while not finished:
        completion_builder = ChatCompletionResponseBuilder()
    
        payload = dict(
            messages=messages,
            tools=oai_tools,
            tool_choice="auto",
            model=settings.llm_model_id
        )

        if not use_tool_calls():
            payload.pop("tools")
            payload.pop("tool_choice")

        logger.info(f"Payload - URL: {settings.llm_base_url}, API Key: {'*' * len(settings.llm_api_key)}, Model: {settings.llm_model_id}")
        streaming_iter = create_streaming_response(
            settings.llm_base_url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            **payload
        )

        async for chunk in streaming_iter:
            completion_builder.add_chunk(chunk)

            if chunk.choices[0].delta.content or chunk.choices[0].delta.reasoning_content:
                yield chunk

        completion = await completion_builder.build()
        
        if (completion.choices[0].message.tool_calls or []):
            completion.choices[0].message.tool_calls = completion.choices[0].message.tool_calls[:1]

        messages.append(refine_assistant_message(completion.choices[0].message.model_dump()))

        for call in (completion.choices[0].message.tool_calls or []):
            _id, _name, _args = call.id, call.function.name, call.function.arguments
            _args = json.loads(_args)

            logger.info(f"Executing tool call: {_name} with args: {_args}")
            _result = ''

            try:
                _result_gen: AsyncGenerator[ChatCompletionStreamResponse | str, None] = build(**_args)

                async for chunk in _result_gen:
                    if isinstance(chunk, ChatCompletionStreamResponse):
                        yield chunk
                    else:
                        _result = chunk

            except Exception as e:
                logger.error(f"Error executing tool call: {_name} with args: {_args}")
                logger.error(f"Error: {e}")
                _result = f"Error: {e}"

            _result = _result or 'No output'
            logger.info(f"Tool call {_name} result: {_result}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": _id,
                    "content": _result
                }
            )

            n_calls += 1

        finished = len((completion.choices[0].message.tool_calls or [])) == 0

    yield completion