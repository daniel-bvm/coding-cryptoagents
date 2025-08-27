"""
Upload API endpoints that proxy requests to EternalAI API.
This keeps the admin key secure on the server side.
"""

import logging
import httpx
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
from pydantic import BaseModel
from agent.configs import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload")

ETERNALAI_BASE_URL = "https://api.eternalai.org/api/agent/file"

class MultipartInitRequest(BaseModel):
    filename: str
    folder_name: str
    total_size: int
    chunk_size: int

class MultipartCompleteRequest(BaseModel):
    upload_id: str
    parts: List[Dict[str, Any]]

@router.post("/init")
async def init_multipart_upload(request: MultipartInitRequest):
    """Initialize multipart upload with EternalAI API"""
    try:
        # Validate input
        if request.total_size <= 0:
            raise HTTPException(status_code=400, detail="Invalid file size")
        if request.chunk_size <= 0:
            raise HTTPException(status_code=400, detail="Invalid chunk size")
        if not request.filename or not request.folder_name:
            raise HTTPException(status_code=400, detail="Filename and folder name are required")
            
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ETERNALAI_BASE_URL}/multipart/init",
                params={"admin_key": settings.eternalai_admin_key},
                json=request.dict(),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"EternalAI init failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to initialize upload: {response.text}"
                )
            
            result = response.json()
            if "upload_id" not in result:
                logger.error(f"Invalid EternalAI response: missing upload_id - {result}")
                raise HTTPException(status_code=502, detail="Invalid response from upload service")
                
            return result
            
    except httpx.TimeoutException:
        logger.error("Timeout initializing multipart upload")
        raise HTTPException(status_code=504, detail="Upload initialization timeout")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error initializing multipart upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/chunk")
async def upload_chunk(
    chunk: UploadFile = File(...),
    upload_id: str = Form(...),
    chunk_number: str = Form(...)
):
    """Upload a single chunk to EternalAI API"""
    try:
        # Validate input
        if not upload_id or not chunk_number:
            raise HTTPException(status_code=400, detail="Upload ID and chunk number are required")
        
        try:
            chunk_num = int(chunk_number)
            if chunk_num <= 0:
                raise HTTPException(status_code=400, detail="Invalid chunk number")
        except ValueError:
            raise HTTPException(status_code=400, detail="Chunk number must be a valid integer")
        
        # Read the chunk data
        chunk_data = await chunk.read()
        if len(chunk_data) == 0:
            raise HTTPException(status_code=400, detail="Empty chunk data")
        
        # Prepare form data for EternalAI
        files = {"chunk": (chunk.filename or f"chunk_{chunk_number}", chunk_data, chunk.content_type or "application/octet-stream")}
        data = {
            "upload_id": upload_id,
            "chunk_number": chunk_number
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:  # Longer timeout for chunk uploads
            response = await client.post(
                f"{ETERNALAI_BASE_URL}/multipart/chunk",
                params={"admin_key": settings.eternalai_admin_key},
                files=files,
                data=data
            )
            
            if response.status_code != 200:
                logger.error(f"EternalAI chunk upload failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to upload chunk {chunk_number}: {response.text}"
                )
            
            result = response.json()
            if "etag" not in result:
                logger.warning(f"EternalAI chunk response missing etag: {result}")
                # Some APIs might not return etag, so we'll create a placeholder
                result["etag"] = f"chunk-{chunk_number}-{upload_id}"
                
            return result
            
    except httpx.TimeoutException:
        logger.error(f"Timeout uploading chunk {chunk_number}")
        raise HTTPException(status_code=504, detail=f"Chunk {chunk_number} upload timeout")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Error uploading chunk {chunk_number}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/complete")
async def complete_multipart_upload(request: MultipartCompleteRequest):
    """Complete multipart upload with EternalAI API"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ETERNALAI_BASE_URL}/multipart/complete",
                params={"admin_key": settings.eternalai_admin_key},
                json=request.dict(),
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                logger.error(f"EternalAI complete failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to complete upload: {response.text}"
                )
            
            return response.json()
            
    except httpx.TimeoutException:
        logger.error("Timeout completing multipart upload")
        raise HTTPException(status_code=504, detail="Upload completion timeout")
    except Exception as e:
        logger.error(f"Error completing multipart upload: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/single")
async def upload_single_file(
    file: UploadFile = File(...),
    folder_name: str = Form(...)
):
    """Upload a single file to EternalAI API (for smaller files)"""
    try:
        # Read the file data
        file_data = await file.read()
        
        # Prepare form data for EternalAI
        files = {"file": (file.filename, file_data, file.content_type)}
        data = {"folder_name": folder_name}
        
        async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout for large single files
            response = await client.post(
                f"{ETERNALAI_BASE_URL}/upload-zip-extract",
                params={"admin_key": settings.eternalai_admin_key},
                files=files,
                data=data
            )
            
            if response.status_code != 200:
                logger.error(f"EternalAI single upload failed: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to upload file: {response.text}"
                )
            
            return response.json()
            
    except httpx.TimeoutException:
        logger.error("Timeout uploading single file")
        raise HTTPException(status_code=504, detail="File upload timeout")
    except Exception as e:
        logger.error(f"Error uploading single file: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/health")
async def health_check():
    """Health check endpoint for upload service"""
    return {"status": "healthy", "service": "upload_proxy"}
