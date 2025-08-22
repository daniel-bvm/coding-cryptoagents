from typing import TypeVar, Generator, Union, List, Any, Dict
import logging
from mcp.types import CallToolResult, TextContent, Tool, EmbeddedResource
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
import re
import datetime

logger = logging.getLogger(__name__)
T = TypeVar('T')

def batching(generator: Union[Generator[T, None, None], List[T]], batch_size: int) -> Generator[list[T], None, None]:

    if isinstance(generator, List):
        for i in range(0, len(generator), batch_size):
            yield generator[i:i+batch_size]

    elif isinstance(generator, Generator) or hasattr(generator, "__iter__"):
        batch = []

        for item in generator:
            batch.append(item)

            if len(batch) == batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    else:
        raise ValueError("Generator must be a generator or a list")
    

def convert_mcp_tools_to_openai_format(
    mcp_tools: List[Any]
) -> List[Dict[str, Any]]:
    """Convert MCP tool format to OpenAI tool format"""
    openai_tools = []
    
    logger.debug(f"Input mcp_tools type: {type(mcp_tools)}")
    logger.debug(f"Input mcp_tools: {mcp_tools}")
    
    # Extract tools from the response
    if hasattr(mcp_tools, 'tools'):
        tools_list = mcp_tools.tools
        logger.debug("Found ListToolsResult, extracting tools attribute")
    elif isinstance(mcp_tools, dict):
        tools_list = mcp_tools.get('tools', [])
        logger.debug("Found dict, extracting 'tools' key")
    else:
        tools_list = mcp_tools
        logger.debug("Using mcp_tools directly as list")
        
    logger.debug(f"Tools list type: {type(tools_list)}")
    logger.debug(f"Tools list: {tools_list}")
    
    # Process each tool in the list
    if isinstance(tools_list, list):
        logger.debug(f"Processing {len(tools_list)} tools")
        for tool in tools_list:
            logger.debug(f"Processing tool: {tool}, type: {type(tool)}")
            if hasattr(tool, 'name') and hasattr(tool, 'description'):
                openai_name = sanitize_tool_name(tool.name)
                logger.debug(f"Tool has required attributes. Name: {tool.name}")
                
                tool_schema = getattr(tool, 'inputSchema', {})
                (tool_schema.setdefault(k, v) for k, v in {
                    "type": "object",
                    "properties": {},
                    "required": []
                }.items()) 
                                
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": openai_name,
                        "description": tool.description,
                        "parameters": tool_schema
                    }
                }

                openai_tools.append(openai_tool)
                logger.debug(f"Converted tool {tool.name} to OpenAI format")
            else:
                logger.debug(
                    f"Tool missing required attributes: "
                    f"has name = {hasattr(tool, 'name')}, "
                    f"has description = {hasattr(tool, 'description')}"
                )
    else:
        logger.debug(f"Tools list is not a list, it's a {type(tools_list)}")
    
    return openai_tools

def sanitize_tool_name(name: str) -> str:
    """Sanitize tool name for OpenAI compatibility"""
    # Replace any characters that might cause issues
    return name.replace("-", "_").replace(" ", "_").lower()

def compare_toolname(openai_toolname: str, mcp_toolname: str) -> bool:
    return sanitize_tool_name(mcp_toolname) == openai_toolname
    
async def execute_openai_compatible_toolcall(
    toolname: str, arguments: Dict[str, Any], mcp: FastMCP
) -> list[Union[TextContent, EmbeddedResource]]:
    tools = await mcp.list_tools()
    candidate: List[Tool] = []

    for tool in tools:
        tool: Tool
        if compare_toolname(toolname, tool.name):
            candidate.append(tool)

    if len(candidate) > 1:
        logger.warning(
            "More than one tool has the same santizied"
            " name to the requested tool"
        )
        
    elif len(candidate) == 0:
        return CallToolResult(
            content=[TextContent(text=f"Tool {toolname} not found")], 
            isError=True
        )
        
    toolname = candidate[0].name

    try:
        res = await mcp.call_tool(toolname, arguments)
    except Exception as e:
        logger.error(f"Error executing tool {toolname} with arguments {arguments}: {e}")
        return CallToolResult(
            content=[TextContent(text=f"Error executing tool {toolname}: {e}")], 
            isError=True
        )

    return [
        e for e in res 
        if isinstance(e, (TextContent, EmbeddedResource))
    ]

def refine_mcp_response(something: Any) -> str:
    if isinstance(something, dict):
        return {
            k: refine_mcp_response(v)
            for k, v in something.items()
        }

    elif isinstance(something, (list, tuple)):
        return [
            refine_mcp_response(v)
            for v in something
        ]

    elif isinstance(something, BaseModel):
        return something.model_dump()

    return something


def strip_toolcall_noti(content: str) -> str:
    cleaned = re.sub(r"<details\b[^>]*>.*?</details>", "", content, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def strip_thinking_content(content: str, logging: bool=False) -> str:
    pat = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

    # if logging:
    #     if pat.search(content):
    #         logger.info(f"Thinking content found in the content: {content}")

    return pat.sub("", content).lstrip()


def refine_chat_history(messages: list[dict[str, str]], system_prompt: str = "") -> list[dict[str, str]]:
    refined_messages = []

    has_system_prompt = False
    for message in messages:
        message: dict[str, str]

        if isinstance(message, dict) and message.get('role', 'undefined') == 'system':
            if system_prompt:
                message['content'] += f'\n{system_prompt}'

            has_system_prompt = True
            refined_messages.append(message)
            continue
    
        if isinstance(message, dict) \
            and message.get('role', 'undefined') == 'user' \
            and isinstance(message.get('content'), list):

            content = message['content']
            text_input = ''

            for item in content:
                if item.get('type', 'undefined') == 'text':
                    text_input += strip_thinking_content(item.get('text') or '', logging=True)

            refined_messages.append({
                "role": "user",
                "content": text_input
            })

        else:
            _message = {
                "role": message.get('role', 'assistant'),
                "content": strip_toolcall_noti(strip_thinking_content(message.get("content", ""), logging=True))
            }

            refined_messages.append(_message)

    if not has_system_prompt and system_prompt != "":
        refined_messages.insert(0, {
            "role": "system",
            "content": system_prompt
        })

    if isinstance(refined_messages[-1], str):
        refined_messages[-1] = {
            "role": "user",
            "content": refined_messages[-1]
        }

    return refined_messages


def refine_chat_history_v1(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    refined_messages = []

    for message in messages:
        message: dict[str, str]
        content: str | list[dict[str, Any]] = message.get('content', '')
        role: str = message.get('role', 'assistant')
        tool_calls: list[dict[str, Any]] = message.get('tool_calls', [])

        if role == 'tool':
            message['content'] = strip_thinking_content(message['content']) or 'Successfully executed (no output)'
            refined_messages.append(message)
            continue

        if isinstance(content, list):
            refined_content: list[dict[str, Any]] = []

            for item in content:
                item: dict[str, Any]

                if item.get('type', 'undefined') == 'text':
                    refined_content.append({
                        'type': 'text',
                        'text': strip_toolcall_noti(strip_thinking_content(item.get('text', '')))
                    })

                else:
                    refined_content.append(item)

            content = refined_content

        elif isinstance(content, str):
            content = strip_toolcall_noti(strip_thinking_content(content))

        new_message = {
            'role': role,
            'content': content
        }

        if tool_calls is not None and len(tool_calls) > 0:
            new_message['tool_calls'] = tool_calls

        refined_messages.append(new_message)

    return refined_messages

def refine_assistant_message(
    assistant_message: Union[dict[str, str], BaseModel]
) -> dict[str, str]:
    
    if isinstance(assistant_message, BaseModel):
        assistant_message = assistant_message.model_dump()

    if 'content' in assistant_message:
        assistant_message['content'] = strip_thinking_content(assistant_message['content'] or "")

    return assistant_message



import regex
import time
from typing import Optional, AsyncGenerator
from .oai_models import random_uuid, ChatCompletionStreamResponse, ErrorResponse


def wrap_chunk(id: str, content: str, role: str = 'assistant') -> ChatCompletionStreamResponse:
    return ChatCompletionStreamResponse(
        id=id,
        object='chat.completion.chunk',
        created=int(time.time()),
        model='unspecified',
        choices=[
            dict(
                index=0,
                delta=dict(
                    content=content,
                    role=role
                ),
            )
        ]
    )

def get_file_extension(uri: str) -> str:
    logger.info(f"received uri: {uri[:100]}")
    if uri.startswith('data:'):
        return uri.split(';')[0].split('/')[-1].lower()

    if uri.startswith('http'):
        return uri.split('.')[-1].lower()

    if uri.startswith('file:'):
        return uri.split('.')[-1].lower()

    return None

class Attachment:
    def __init__(self, data_uri: str, name: Optional[str] = None, type: Optional[str] = None):
        self.data_uri = data_uri
        self.type = type or get_file_extension(data_uri) or "data"
        self.name = name or f"attachment_{random_uuid()}.{self.type}"

class AgentResourceManager:
    def __init__(self):
        self.resources: dict[str, str] = {}
        self.attachments: list[Attachment] = []
        self.data_uri_pattern = regex.compile(r'data:[^;,]+;base64,[A-Za-z0-9+/]+=*', regex.IGNORECASE | regex.DOTALL | regex.MULTILINE)
        self.resource_citing_pattern = regex.compile(r'"([^"]+)"', regex.IGNORECASE | regex.DOTALL | regex.MULTILINE)

    def embed_resource(self, content: str) -> str:
        def replace_with_id(match: regex.Match[str]) -> str:
            resource_id = random_uuid()
            self.resources[resource_id] = match.group(0)
            return resource_id

        return self.data_uri_pattern.sub(replace_with_id, content)

    def extract_resource(self, content: str) -> list[str]:
        results: list[str] = []

        for m in self.resource_citing_pattern.finditer(content):
            resource_id: str = m.group(1)

            if resource_id not in results and resource_id in self.resources:
                results.append(resource_id)

        for resource_id, _ in self.resources.items():
            if resource_id in content and resource_id not in results:
                results.append(resource_id)

        return results

    def get_resource_by_id(self, resource_id: str) -> Optional[str]:
        return self.resources.get(resource_id)

    def reveal_resource(self, content: str) -> str:
        def replace_with_data_uri(match: regex.Match[str]) -> str:
            resource_id = match.group(1)
            return f'"{self.resources.get(resource_id, resource_id)}"'

        return self.resource_citing_pattern.sub(replace_with_data_uri, content)

    def add_attachment(self, data_uri: str, name: Optional[str] = None) -> Attachment:
        attachment = Attachment(data_uri, name)
        self.attachments.append(attachment)
        return attachment

    async def handle_streaming_response(
        self, 
        stream: AsyncGenerator[ChatCompletionStreamResponse | ErrorResponse, None], 
        cut_tags: list[str] = [], 
        cut_pats: list[str] = []
    ) -> AsyncGenerator[ChatCompletionStreamResponse | ErrorResponse, None]:
        buffer: str = ''

        cut_tags_str = "|".join(cut_tags)
        tags_str = "file|img|data|files"

        pattern_template = r"<({tags_str})\b[^>]*>(.*?)</\1>|<({tags_str})\b[^>]*/>"

        citing_pat_str = pattern_template.format(tags_str=tags_str)
        cut_pat_str = pattern_template.format(tags_str=cut_tags_str) if len(cut_pats) else ""

        if cut_pat_str:
            cut_pats.append(cut_pat_str)

        if cut_pats:
            citing_pat = regex.compile("|".join([citing_pat_str, *cut_pats]), regex.DOTALL | regex.IGNORECASE | regex.MULTILINE)
        else:
            citing_pat = regex.compile(citing_pat_str, regex.DOTALL | regex.IGNORECASE | regex.MULTILINE)

        cut_pat = regex.compile("|".join(cut_pats), regex.DOTALL | regex.IGNORECASE | regex.MULTILINE) if len(cut_pats) else None

        logger.info("Watching for citing_pat: {}".format(citing_pat))
        logger.info("Watching for cut_pat: {}".format(cut_pat))

        async for chunk in stream:
            if isinstance(chunk, ErrorResponse):
                yield chunk
                continue
            
            if not chunk.choices:
                continue

            if len(chunk.choices[0].delta.tool_calls) > 0:
                yield chunk
                continue

            buffer += chunk.choices[0].delta.content or ''
            partial_match = citing_pat.search(buffer, partial=True)
            
            if not partial_match or (partial_match.span()[0] == partial_match.span()[1]):
                yield wrap_chunk(random_uuid(), buffer, 'assistant')
                buffer = ''

                continue

            if partial_match.partial:
                yield wrap_chunk(random_uuid(), buffer[:partial_match.span()[0]], 'assistant')
                buffer = buffer[partial_match.span()[0]:]

                continue

            if cut_pat is not None and cut_pat.search(buffer) is None:
                yield wrap_chunk(random_uuid(), self.reveal_resource(buffer), 'assistant')

            buffer = ''

        if buffer:
            yield wrap_chunk(random_uuid(), buffer, 'assistant')

import os
import asyncio
import shlex
import zipfile

# create one file html
async def inline_html(index_html_file: str, output_file: str = None) -> str | None:
    if not os.path.exists(index_html_file):
        return None

    if not os.path.isfile(index_html_file):
        return None

    output_file = output_file or index_html_file
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    quoted_index_html_file = shlex.quote(index_html_file)
    quoted_output_file = shlex.quote(output_file)

    process = await asyncio.create_subprocess_shell(f"npx single-file-cli {quoted_index_html_file} -o {quoted_output_file}")
    code = await process.wait()

    if code != 0:
        logger.warning(f"Error inlining HTML file {index_html_file}")

    return output_file


# create one file html
async def compress_output(folder: str, output_file: str = None) -> str | None:
    if not os.path.exists(folder):
        return None

    if not os.path.isdir(folder):
        return None

    with zipfile.ZipFile(output_file, 'w') as zipf:
        for root, dirs, files in os.walk(folder):
            for file in files:
                zipf.write(
                    os.path.join(root, file), 
                    os.path.relpath(os.path.join(root, file), folder)
                )

    return output_file