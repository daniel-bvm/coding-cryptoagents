from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from .xterm_toolcalls import mcp as xterm_mcp
from .utils import (
    refine_chat_history,
    refine_assistant_message,
    refine_mcp_response,
    execute_openai_compatible_toolcall,
    convert_mcp_tools_to_openai_format,
)
from .oai_streaming import (
    create_streaming_response,
    ChatCompletionResponseBuilder
)
from .oai_models import (
    ChatCompletionRequest, 
    ChatCompletionResponse,
    ChatCompletionStreamResponse,
    random_uuid
)
from typing import AsyncGenerator, Any
import logging
import time
import json
import os
from .configs import settings

logger = logging.getLogger(__name__)

router = APIRouter()

async def get_system_prompt() -> str:
    if not os.path.exists("system_prompt.txt"):
        with open("system_prompt.txt", "w") as f:
            f.write("You are a helpful assistant.")

    with open("system_prompt.txt", "r") as f:
        system_prompt = f.read()

    return system_prompt

async def handle_request(request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionStreamResponse | ChatCompletionResponse, None]:
    messages = request.messages
    assert len(messages) > 0, "No messages in the request"
 
    system_prompt = await get_system_prompt()
    messages: list[dict[str, Any]] = refine_chat_history(messages, system_prompt)

    tools = await xterm_mcp.list_tools()
    oai_tools = convert_mcp_tools_to_openai_format(tools)
    finished = False
    n_calls, max_calls = 0, 25

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
            settings.llm_api_key,
            **payload
        )

        async for chunk in streaming_iter:
            completion_builder.add_chunk(chunk)

            if chunk.choices[0].delta.content:
                yield chunk

        completion = await completion_builder.build()
        messages.append(refine_assistant_message(completion.choices[0].message))

        for call in (completion.choices[0].message.tool_calls or []):
            _id, _name, _args = call.id, call.function.name, call.function.arguments
            _args = json.loads(_args)

            logger.info(f"Executing tool call: {_name} with args: {_args}")
            _result = await execute_openai_compatible_toolcall(_name, _args, xterm_mcp)
            logger.info(f"Tool call {_name} result: {_result}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": _id,
                    "content": refine_mcp_response(_result)
                }
            )

            n_calls += 1

        finished = len((completion.choices[0].message.tool_calls or [])) == 0

    yield completion

@router.post("/prompt")
async def prompt(request: ChatCompletionRequest):
    enqueued = time.time()
    ttft, tps, n_tokens = float("inf"), None, 0
    req_id = request.request_id or f"req-{random_uuid()}"

    if request.stream:
        generator = handle_request(request)

        async def to_bytes(gen: AsyncGenerator) -> AsyncGenerator[bytes, None]:
            nonlocal ttft, tps, n_tokens

            async for chunk in gen:
                current_time = time.time()

                n_tokens += 1
                ttft = min(ttft, current_time - enqueued)
                tps = n_tokens / (current_time - enqueued)

                if isinstance(chunk, ChatCompletionStreamResponse):
                    data = chunk.model_dump_json()
                    yield "data: " + data + "\n\n"

            logger.info(f"Request {req_id} - TTFT: {ttft:.2f}s, TPS: {tps:.2f} tokens/s")
            yield "data: [DONE]\n\n"

        return StreamingResponse(to_bytes(generator), media_type="text/event-stream")
    
    else:
        async for chunk in handle_request(request):
            current_time = time.time()

            n_tokens += 1
            ttft = min(ttft, current_time - enqueued)
            tps = n_tokens / (current_time - enqueued)

        logger.info(f"Request {req_id} - TTFT: {ttft:.2f}s, TPS: {tps:.2f} tokens/s")
        return JSONResponse(chunk.model_dump())

@router.get("/processing-url")
async def get_processing_url():
    return {"message": "Hello, World!"}
