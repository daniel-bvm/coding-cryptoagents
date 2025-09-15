from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse

from agent.slide_maker import make_slides
from .oai_models import (
    ChatCompletionRequest, 
    ChatCompletionStreamResponse,
    random_uuid,
    ErrorResponse
)
from typing import AsyncGenerator
import logging
import time
from agent.handlers import handle_request
from agent.upload_api import router as upload_router

logger = logging.getLogger(__name__)
router = APIRouter()

# Include upload endpoints
router.include_router(upload_router)

@router.post("/prompt")
async def prompt(request: ChatCompletionRequest):
    enqueued = time.time()
    ttft, tps, n_tokens = float("inf"), None, 0
    req_id = request.request_id or f"req-{random_uuid()}"

    generator = handle_request(request)

    if request.stream:
        async def to_bytes(gen: AsyncGenerator) -> AsyncGenerator[bytes, None]:
            nonlocal ttft, tps, n_tokens

            try:
                async for chunk in gen:
                    current_time = time.time()

                    n_tokens += 1
                    ttft = min(ttft, current_time - enqueued)
                    tps = n_tokens / (current_time - enqueued)

                    if isinstance(chunk, ChatCompletionStreamResponse):
                        data = chunk.model_dump_json()
                        yield "data: " + data + "\n\n"

                logger.info(f"Request {req_id} - TTFT: {ttft:.2f}s, TPS: {tps:.2f} tokens/s")

            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(to_bytes(generator), media_type="text/event-stream")
    
    else:
        try:
            async for chunk in generator:
                current_time = time.time()

                n_tokens += 1
                ttft = min(ttft, current_time - enqueued)
                tps = n_tokens / (current_time - enqueued)

            logger.info(f"Request {req_id} - TTFT: {ttft:.2f}s, TPS: {tps:.2f} tokens/s")
            return JSONResponse(chunk.model_dump()) # use the last chunk

        except Exception as e:
            return JSONResponse(ErrorResponse(message="Unknown error", type="unknown_error", code=500).model_dump())

@router.get("/processing-url")
def get_processing_url() -> dict:
    return {
        "url": f"http://localhost:12345/",
        "status": "ready"
    }


@router.post("/test")
async def test():
    await make_slides(
        presentation_title="Internet History Overview",
        user_request="A 5-page presentation covering the key milestones and developments in internet history, from early concepts to modern-day internet. Each page should focus on a different era or major development in internet evolution.",
        workdir="./opencode-workspace/f0d238e9bbc5473da3d06023b74a29c6",
    )
