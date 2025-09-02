RECEPTIONIST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "explain",
            "description": "Start planning, researching, and create a HTML report that explains for what the user is looking for.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Name the task."
                    },
                    "topic_or_url": {
                        "type": "string",
                        "description": "Either a topic (raw text) or a URL. Examples: 'footballdotfun', 'https://arxiv.org/abs/1706.03762'."
                    },
                    "expectation": {
                        "type": "string", 
                        "description": "Describe how should the output looks like.",
                    }
                },
                "required": ["title", "topic_or_url", "expectation"]
            }
        }
    }
]

RECEPTIONIST_SYSTEM_PROMPT = """
Your task is to first communicate with the user and determine the next step, explain, research, or report, or ask the user for more details if it is too vague, etc. Especially, we are helping user to realize their thoughts, understand the problem, prototype it, build a static website, html report or a blog post (that broadcasts content to the audience). User is busy, so they do not want to communicate too much. You only have to ask them for more details in some specific cases:
- Their core idea is too unclear.
- Greeting.

In other cases, you are free to guess what they want and call the explain tool. But, for terms and keywords, keep it raw in the description and title so we can build the answer more efficiently. When the user asking to explain something, we just need to focus on carefully research about it and make the report professional, concise, and visual stunning. We can resolve any problems, explain, write, and prototype anything. Any request, send it to us via the explain function, and the user gets what they want. 
"""

from agent.oai_models import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionStreamResponse, ErrorResponse
from agent.utils import refine_chat_history, refine_assistant_message, save_chat_history
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
from agent.utils import wrap_chunk, random_uuid, compress_output
from agent.database import get_task_repository
from agent.pubsub import EventHandler, EventPayload, EventType
import glob
import base64
from mimetypes import guess_type
import uuid
from .lite_keybert import extract_keywords
from deepsearch.export import deepsearch
from deepsearch.agents.deep_reasoning import StructuredReport
import re
from pydantic import BaseModel
from .concurrency import sync2async
import asyncio

class QueryInput(BaseModel):
    topic: str
    urls: list[str]
    
URL_REGEX = re.compile(r'https?://[^\s]+')

def is_valid_topic(topic: str, urls: list[str]) -> bool:
    topic_cp = deepcopy(topic) 

    for url in urls:
        topic_cp = topic_cp.replace(url, '')
 
    for p in punctuation:
        topic_cp = topic_cp.replace(p, '')

    return len(topic_cp.strip()) > 0

def detect_urls(topic_or_url: str) -> QueryInput:
    urls = URL_REGEX.findall(topic_or_url)

    if not urls:
        return QueryInput(topic=topic_or_url if is_valid_topic(topic_or_url, []) else '', urls=[])

    return QueryInput(topic=topic_or_url if is_valid_topic(topic_or_url, urls) else '', urls=urls)

from copy import deepcopy
from string import punctuation

async def run_deepsearch(topic: str) -> StructuredReport | None:
    if not topic:
        return None

    async_deepsearch = sync2async(deepsearch)
    output: StructuredReport = await async_deepsearch(topic)
    
    if not output:
        return None

    return output

async def scrape(
    urls: list[str],
    save_dir: str, 
    preview_tokens_limit: int = 4096,
    max_preview_tokens: int = 1024
) -> list[dict[str, Any]]:
    os.makedirs(save_dir, exist_ok=True)

    if not urls:
        return []

    from mcps.tavily_search.main import fetch
    call_fn = fetch.fn
    
    urls = list(set(urls))

    preview_chars_limit = preview_tokens_limit * 4
    max_preview_chars = max_preview_tokens * 4
    char_limits = min(preview_chars_limit // len(urls), max_preview_chars)

    results: list[dict[str, Any]] = []

    for url in urls:
        try:
            response = await call_fn(url)
            for item in response:
                if 'raw_content' not in item:
                    continue

                raw_content: str = item['raw_content']
                raw_content_preview: str = raw_content[:char_limits]
                random_file_name: str = f'{os.urandom(4).hex()}.md'
                file_path: str = os.path.join(save_dir, random_file_name)
                
                with open(file_path, 'w') as f:
                    f.write(raw_content_preview)

                results.append({
                    'url': url,
                    'full_content_path': file_path,
                    'preview_content': raw_content_preview,
                    'raw_content': raw_content
                })

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            continue

    return results

def compose_steps(steps: List[StepV2], task_offset_1: int = 1) -> StepV2:
    step_type, task, expectation, reason = steps[0].step_type, '', '', ''

    for i, step in enumerate(steps):
        task += f"Step {i + task_offset_1}: {step.task}\n" \
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

        while it < len(steps) - 1 and steps[it].step_type == steps[it-1].step_type and len(seg) < 2:
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

async def publish_task_update(task, event_type: str = "task_updated"):
    """Publish real-time task updates via pubsub"""
    try:
        from agent.task_api import task_to_response
        event = EventPayload(
            type=EventType.MESSAGE,
            data={
                "event_type": event_type,
                "task": task_to_response(task).model_dump()
            },
            channel="tasks"
        )
        await EventHandler.event_handler().publish(event)
    except Exception as e:
        logger.error(f"Error publishing task update: {e}")

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

def gather_info(scrape_results: list[dict[str, Any]], deepsearch_results: StructuredReport | None, save_dir: str) -> str:
    if not scrape_results and not deepsearch_results:
        return ""

    scratchpad = ""
    scratchpad_full = ""

    for i, result in enumerate(scrape_results):
        scratchpad += f"{1 + i} Scraped from {result['url']} (Raw content stored in {result['full_content_path']}):\n"
        scratchpad += f"Preview: {result['preview_content']}\n\n"

        scratchpad_full += f"{1 + i} Scraped from {result['url']}:\n"
        scratchpad_full += f"{result['raw_content']}\n\n"

    if deepsearch_results:
        scratchpad += f"Deep search results:\n"
        scratchpad += f"Title: {deepsearch_results.title}\n"
        scratchpad += f"Keypoints: {deepsearch_results.keypoints}\n"
        scratchpad += f"Short Answer: {deepsearch_results.direct_answer}\n"
        scratchpad += f"Content: {deepsearch_results.report}\n"
        scratchpad += f"References: {deepsearch_results.references}\n"
        
        scratchpad_full += f"Deep search results:\n"
        scratchpad_full += f"Title: {deepsearch_results.title}\n"
        scratchpad_full += f"Keypoints: {deepsearch_results.keypoints}\n"
        scratchpad_full += f"Short Answer: {deepsearch_results.direct_answer}\n"
        scratchpad_full += f"Content: {deepsearch_results.report}\n"
        scratchpad_full += f"References: {deepsearch_results.references}\n"
        
    full_path = os.path.join(save_dir, 'research.md')
    scratchpad += f"Full version of the research content is stored in {full_path}"

    with open(full_path, "w", encoding='utf-8') as f:
        f.write(scratchpad_full)

    return scratchpad

async def build(
    task_id: str, 
    title: str,
    topic_or_url: str,
    expectation: str,
    pre_search_info: str | None = None
) -> AsyncGenerator[ChatCompletionStreamResponse | ChatCompletionResponse, None]: # recap
    input_query: QueryInput = detect_urls(topic_or_url)

    assert expectation is not None, "No task definition provided"
    assert input_query.topic or input_query.urls, "No topic or urls provided"
    
    workdir = os.path.abspath(os.path.join(settings.opencode_directory, task_id))
    os.makedirs(workdir, exist_ok=True)
    
    docs_workdir = os.path.join(workdir, "docs")
    os.makedirs(docs_workdir, exist_ok=True)

    scrape_results, deepsearch_results = await asyncio.gather(
        scrape(input_query.urls, docs_workdir),
        run_deepsearch(input_query.topic)
    )

    scrape_results: list[dict[str, Any]]
    deepsearch_results: StructuredReport | None

    if not scrape_results and not deepsearch_results:
        max_steps = 5
        information = "No related information has been found yet."

    else:
        max_steps = 3
        information = gather_info(scrape_results, deepsearch_results, docs_workdir)

    # Create task in database
    repo = get_task_repository()
    try:
        task = repo.create_task(
            task_id=task_id,
            title=title,
            expectation=expectation
        )
        
        # Publish task creation event
        await publish_task_update(task, "task_created")
        
        # Update task to processing
        task = repo.update_task_status(task_id, "processing")
        await publish_task_update(task, "task_status")
        
    except Exception as e:
        logger.error(f"Error creating task: {e}")

    finally:
        repo.db.close()

    yield wrap_chunk(random_uuid(), f"<action>Planning...</action>\n")

    # steps: List[StepV2] = await make_plan(title, expectation)
    steps: List[StepV2] = []

    async for step in gen_plan(title, information, expectation, max_steps):
        steps.append(step)

        # Create step in database
        repo = get_task_repository()
        try:
            db_step = repo.create_task_step(
                step_id=step.id,
                task_id=task_id,
                step_number=len(steps),
                step_type=step.step_type,
                task_description=step.task,
                expectation=step.expectation,
                reason=step.reason
            )
        except Exception as e:
            logger.error(f"Error creating step in database: {e}")
        finally:
            repo.db.close()

        # Publish plan step creation event
        try:
            event = EventPayload(
                type=EventType.INFO,
                data={
                    "event_type": "plan_step_created",
                    "task_id": task_id,
                    "step": {
                        "id": step.id,
                        "step_type": step.step_type,
                        "task": step.task,
                        "expectation": step.expectation,
                        "reason": step.reason
                    },
                    "step_number": len(steps),
                    "title": title
                },
                channel="tasks"
            )
            await EventHandler.event_handler().publish(event)
        except Exception as e:
            logger.error(f"Error publishing plan step event: {e}")

        yield wrap_chunk(random_uuid(), f"<action>{step.reason}</action>\n")
        yield wrap_chunk(random_uuid(), f"<details><summary>Todo</summary>{step.task}</details>\n")
        yield wrap_chunk(random_uuid(), f"<details><summary>Expected</summary>{step.expectation}</details>\n")

    if not steps:
        # Update task as failed
        repo = get_task_repository()
        try:
            task = repo.update_task_status(task_id, "failed", "Planner could not generate steps")
            await publish_task_update(task, "task_status")
        except Exception as e:
            logger.error(f"Error updating task status: {e}")
        finally:
            repo.db.close()
        
        yield "Planner is quite tired now, he's sleeping. The task can not be completed at this moment, please come back later."
        return


    
    # Publish plan completion event
    try:
        event = EventPayload(
            type=EventType.INFO,
            data={
                "event_type": "plan_completed",
                "task_id": task_id,
                "title": title,
                "total_steps": len(steps),
                "plan_summary": {
                    "plan_steps": len([s for s in steps if s.step_type == "research"]),
                    "build_steps": len([s for s in steps if s.step_type == "build"]),
                    "steps": [
                        {
                            "id": step.id,
                            "step_type": step.step_type,
                            "task": step.task[:100] + "..." if len(step.task) > 100 else step.task,
                            "reason": step.reason
                        } for step in steps
                    ]
                }
            },
            channel="tasks"
        )
        await EventHandler.event_handler().publish(event)
    except Exception as e:
        logger.error(f"Error publishing plan completion event: {e}")

    # Update task with total steps
    repo = get_task_repository()
    try:
        task = repo.update_task_progress(task_id, 10, "Planning completed", 0, len(steps))
        await publish_task_update(task, "task_progress")
    except Exception as e:
        logger.error(f"Error updating task progress: {e}")
    finally:
        repo.db.close()

    segmented_steps: List[List[StepV2]] = segment_steps_by_type(steps)
    steps_output: list[StepOutput] = []
    
    async with OpenCodeSDKClient(workdir) as client:
        session_id = await client.create_session(title)

    logger.info(f"Task {task_id}; Building... (Session ID: {session_id})")

    yield wrap_chunk(random_uuid(), f"<action>Building...</action>\n")

    for i in range(len(steps_output), len(segmented_steps)):
        logger.info(f"Task {task_id} ({expectation[:128]}); Progress: {len(steps_output)}/{len(segmented_steps)}")
        
        ssteps = segmented_steps[i]

        for step in ssteps:
            yield wrap_chunk(random_uuid(), f"<action>{step.task}</action>\n")

        task_offset = sum(len(e) for e in segmented_steps[:i])
        task_offset_1 = task_offset + 1
        nsteps = ', '.join([f"{task_offset_1 + j}" for j in range(len(ssteps))])

        composed_step = compose_steps(ssteps, task_offset_1)
        logger.info(f"Task {task_id}; Executing step: {composed_step.task}")

        # Update progress
        progress = 10 + int((task_offset / len(steps)) * 80)  # 10% to 90%
        repo = get_task_repository()

        try:
            task = repo.update_task_progress(task_id, progress, f"Executing steps {nsteps}", task_offset_1 - 1, len(steps))
            await publish_task_update(task, "task_progress")
        except Exception as e:
            logger.error(f"Error updating task progress: {e}")
        finally:
            repo.db.close()

        # Update step statuses to executing
        for step in ssteps:
            repo = get_task_repository()
            try:
                repo.update_step_status(step.id, "executing")
                
                # Publish step status update
                event = EventPayload(
                    type=EventType.MESSAGE,
                    data={
                        "event_type": "step_status_updated",
                        "task_id": task_id,
                        "step_id": step.id,
                        "status": "executing"
                    },
                    channel="tasks"
                )
                await EventHandler.event_handler().publish(event)
            except Exception as e:
                logger.error(f"Error updating step status to executing: {e}")
            finally:
                repo.db.close()

        if i == 0: # first step
            composed_step.task = f"We are building a {title}, expected output: {expectation}\n\nThese information are gathered:\n{information}\n\nYour task is to complete it step-by-step\n{composed_step.task}"

        is_last_build_step = ssteps[-1].step_type == "build"

        for j in range(i + 1, len(segmented_steps)):
            if segmented_steps[j][-1].step_type == "build":
                is_last_build_step = False
                break

        html_files = glob.glob(os.path.join(workdir, "**/*.html"), recursive=True)
        markdown_files = glob.glob(os.path.join(workdir, "**/*.md"), recursive=True)
        index_html_files = glob.glob(os.path.join(workdir, "**/index.html"), recursive=True)
        has_index_html = len(index_html_files) > 0
        has_any_html = len(html_files) > 0
        has_markdown_files = len(markdown_files) > 0
    
        if is_last_build_step and not has_index_html:
            composed_step.task += f"\n\nImportant: The current project does not contain an index.html file to respond to the user. Create it now."

            if has_any_html:
                composed_step.task += f"\n\nHint: If the main content is included in another index.html file, just rename it to index.html and polish it."

            elif has_markdown_files:
                composed_step.task += f"\n\nHint: Use the information from generated markdown files to create the final report."

        step_output: ClaudeCodeStepOutput = await execute_steps_v2(
            composed_step.step_type, 
            composed_step, 
            workdir,
            session_id
        )

        logger.info(f"Task {task_id} ({expectation[:128]}...); Step output: {step_output.full}")
        steps_output.append(step_output)

        # Update step statuses to completed
        for step in ssteps:
            repo = get_task_repository()
            try:
                repo.update_step_status(step.id, "completed", step_output.full)
                
                # Publish step status update
                event = EventPayload(
                    type=EventType.MESSAGE,
                    data={
                        "event_type": "step_status_updated",
                        "task_id": task_id,
                        "step_id": step.id,
                        "status": "completed",
                        "output": step_output.full
                    },
                    channel="tasks"
                )
                await EventHandler.event_handler().publish(event)
            except Exception as e:
                logger.error(f"Error updating step status to completed: {e}")
            finally:
                repo.db.close()
                
    repo = get_task_repository()

    try:
        task = repo.update_task_progress(task_id, 100, f"Finished", len(steps), len(steps))
        await publish_task_update(task, "task_progress")
    except Exception as e:
        logger.error(f"Error updating task progress: {e}")
    finally:
        repo.db.close()

    recap = 'These step(s) have been executed:\n'

    for i, (step_output, ssteps) in enumerate(zip(steps_output, segmented_steps)):
        task_offset_1 = sum(len(e) for e in segmented_steps[:i]) + 1
        composed_step = compose_steps(ssteps, task_offset_1)

        recap += f"Task: {composed_step.task}\n"
        recap += f"Output: {step_output.full}\n\n"

    found_all = glob.glob(os.path.join(workdir, "**"), recursive=True)

    if found_all:
        output_file = f"output_{task_id}.zip"

        try:
            zip_output = await compress_output(workdir, output_file)

            if zip_output and os.path.exists(zip_output) and os.path.getsize(zip_output) > 0:
                logger.info(f"Output file: {zip_output}; Size: {os.path.getsize(zip_output)}")
                # yield wrap_chunk(random_uuid(), construct_file_response([zip_output]))

            recap += f"Output has been sent to the user.\n"

        except Exception as e:
            logger.error(f"Error compressing output: {e}")

        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

            # if os.path.exists(workdir): # disable for easier debugging
            #     shutil.rmtree(workdir, ignore_errors=True)

    has_index_html = len(glob.glob(os.path.join(workdir, "**/*.html"), recursive=True)) > 0

    if not has_index_html:
        raise Exception("Task failed as the output does not meet the expectation.")

    # Update task as completed
    repo = get_task_repository()
    try:
        # Check if index.html exists
        has_index_html = False
        if os.path.exists(workdir):
            index_files = glob.glob(os.path.join(workdir, "**/index.html"), recursive=True)
            has_index_html = len(index_files) > 0
        
        task = repo.update_task_output(task_id, workdir, has_index_html)
        task = repo.update_task_status(task_id, "completed")
        await publish_task_update(task, "task_output")

    except Exception as e:
        logger.error(f"Error completing task: {e}")
        # Mark as failed if we can't update
        try:
            task = repo.update_task_status(task_id, "failed", f"Error completing task: {e}")
            await publish_task_update(task, "task_output")
        except:
            pass

    finally:
        repo.db.close()

    yield recap

async def handle_request(request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionStreamResponse | ChatCompletionResponse, None]:
    messages = request.messages
    assert len(messages) > 0, "No messages in the request"
 
    system_prompt = RECEPTIONIST_SYSTEM_PROMPT
    messages: list[dict[str, Any]] = refine_chat_history(messages, system_prompt)

    oai_tools = RECEPTIONIST_TOOLS
    finished = False

    n_calls, max_calls = 0, 1
    successfull_task_ids = []

    while not finished:
        completion_builder = ChatCompletionResponseBuilder()
    
        payload = dict(
            messages=messages,
            tools=oai_tools,
            tool_choice="auto",
            model=settings.llm_model_id
        )

        if len(successfull_task_ids) > 0:
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

            if isinstance(chunk, ChatCompletionStreamResponse) and (chunk.choices[0].delta.content or chunk.choices[0].delta.reasoning_content):
                yield chunk

            if isinstance(chunk, ErrorResponse):
                yield chunk
                return

        completion = await completion_builder.build()
        
        if (completion.choices[0].message.tool_calls or []):
            completion.choices[0].message.tool_calls = completion.choices[0].message.tool_calls[:1]

        messages.append(refine_assistant_message(completion.choices[0].message.model_dump()))

        for call in (completion.choices[0].message.tool_calls or []):
            _id, _name, _args = call.id, call.function.name, call.function.arguments
            _args = json.loads(_args)

            logger.info(f"Executing tool call: {_name} with args: {_args}")
            _result = ''
            task_id = uuid.uuid4().hex
            _args["task_id"] = task_id

            try:
                repo = get_task_repository()
                _result_gen: AsyncGenerator[ChatCompletionStreamResponse | str, None] = build(**_args)

                async for chunk in _result_gen:
                    if isinstance(chunk, ChatCompletionStreamResponse):
                        yield chunk
                    else:
                        _result = chunk

                successfull_task_ids.append(task_id)

            except Exception as e:
                logger.error(f"Error executing tool call: {_name} with args: {_args}")
                logger.error(f"Error: {e}", exc_info=True)
                _result = f"Error: {e}"

                try:
                    task = repo.update_task_status(
                        task_id, 
                        "failed", 
                        f"Error executing tool call."
                    )

                    await publish_task_update(task, "task_output")
                except Exception as e:
                    logger.error(f"Error updating task status: {e}", exc_info=True)

            finally:
                repo.db.close()

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

    compact_messages = [
        e
        for e in messages
        if isinstance(e, dict) 
        and e.get("role") in ["user", "assistant"]
    ]

    for task_id in successfull_task_ids:
        if not save_chat_history(task_id, compact_messages):
            logger.error(f"Error saving chat history for task {task_id}")
