from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator
from datetime import datetime
import os
import zipfile
import glob
from io import BytesIO

from agent.database import TaskRepository, get_task_repository, Task, TaskStep
from agent.pubsub import EventHandler, EventPayload, EventType
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

class TaskResponse(BaseModel):
    id: str
    title: str
    expectation: Optional[str]
    status: str
    progress: int
    current_step: Optional[str]
    total_steps: int
    completed_steps: int
    output_directory: Optional[str]
    has_index_html: bool
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

class CreateTaskRequest(BaseModel):
    title: str
    expectation: Optional[str] = None

class UpdateTaskProgressRequest(BaseModel):
    progress: int
    current_step: Optional[str] = None
    completed_steps: Optional[int] = None
    total_steps: Optional[int] = None

class UpdateTaskStatusRequest(BaseModel):
    status: str
    error_message: Optional[str] = None

class TaskStepResponse(BaseModel):
    id: str
    task_id: str
    step_number: int
    step_type: str
    task_description: str
    expectation: Optional[str]
    reason: Optional[str]
    status: str
    output: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

class UpdateStepStatusRequest(BaseModel):
    status: str
    output: Optional[str] = None
    error_message: Optional[str] = None

def step_to_response(step: TaskStep) -> TaskStepResponse:
    return TaskStepResponse(
        id=step.id,
        task_id=step.task_id,
        step_number=step.step_number,
        step_type=step.step_type,
        task_description=step.task_description,
        expectation=step.expectation,
        reason=step.reason,
        status=step.status,
        output=step.output,
        error_message=step.error_message,
        started_at=step.started_at,
        completed_at=step.completed_at,
        created_at=step.created_at
    )

def task_to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        title=task.title,
        expectation=task.expectation,
        status=task.status,
        progress=task.progress,
        current_step=task.current_step,
        total_steps=task.total_steps,
        completed_steps=task.completed_steps,
        output_directory=task.output_directory,
        has_index_html=task.has_index_html,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at
    )

async def publish_task_update(task: Task, event_type: str = "task_updated"):
    """Publish real-time task updates via pubsub"""
    try:
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

@router.get("/", response_model=List[TaskResponse])
async def get_all_tasks(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    repo: TaskRepository = Depends(get_task_repository)
):
    """Get all tasks with pagination"""
    try:
        tasks = repo.get_all_tasks(limit=limit, offset=offset)
        return [task_to_response(task) for task in tasks]
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, repo: TaskRepository = Depends(get_task_repository)):
    """Get a specific task by ID"""
    try:
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task_to_response(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.post("/", response_model=TaskResponse)
async def create_task(
    request: CreateTaskRequest,
    background_tasks: BackgroundTasks,
    repo: TaskRepository = Depends(get_task_repository)
):
    """Create a new task"""
    try:
        import uuid
        task_id = uuid.uuid4().hex[:8]
        
        task = repo.create_task(
            task_id=task_id,
            title=request.title,
            expectation=request.expectation
        )
        
        # Publish task creation event
        background_tasks.add_task(publish_task_update, task, "task_created")
        
        return task_to_response(task)
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.put("/{task_id}/progress")
async def update_task_progress(
    task_id: str,
    request: UpdateTaskProgressRequest,
    background_tasks: BackgroundTasks,
    repo: TaskRepository = Depends(get_task_repository)
):
    """Update task progress"""
    try:
        task = repo.update_task_progress(
            task_id=task_id,
            progress=request.progress,
            current_step=request.current_step,
            completed_steps=request.completed_steps,
            total_steps=request.total_steps
        )
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Publish progress update
        background_tasks.add_task(publish_task_update, task, "task_progress")
        
        return task_to_response(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task progress {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.put("/{task_id}/status")
async def update_task_status(
    task_id: str,
    request: UpdateTaskStatusRequest,
    background_tasks: BackgroundTasks,
    repo: TaskRepository = Depends(get_task_repository)
):
    """Update task status"""
    try:
        task = repo.update_task_status(
            task_id=task_id,
            status=request.status,
            error_message=request.error_message
        )
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Publish status update
        background_tasks.add_task(publish_task_update, task, "task_status")
        
        return task_to_response(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task status {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.put("/{task_id}/output")
async def update_task_output(
    task_id: str,
    output_directory: str,
    background_tasks: BackgroundTasks,
    repo: TaskRepository = Depends(get_task_repository)
):
    """Update task output directory and check for index.html"""
    try:
        # Check if index.html exists
        has_index_html = False
        if os.path.exists(output_directory):
            index_files = glob.glob(os.path.join(output_directory, "**/index.html"), recursive=True)
            has_index_html = len(index_files) > 0
        
        task = repo.update_task_output(
            task_id=task_id,
            output_directory=output_directory,
            has_index_html=has_index_html
        )
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Publish output update
        background_tasks.add_task(publish_task_update, task, "task_output")
        
        return task_to_response(task)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task output {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.get("/{task_id}/files")
async def get_task_files(task_id: str, repo: TaskRepository = Depends(get_task_repository)):
    """Get list of files in the task output directory"""
    try:
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if not task.output_directory or not os.path.exists(task.output_directory):
            return {"files": []}
        
        files = []
        for root, dirs, file_names in os.walk(task.output_directory):
            for file_name in file_names:
                file_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(file_path, task.output_directory)
                file_size = os.path.getsize(file_path)
                
                files.append({
                    "name": file_name,
                    "path": relative_path,
                    "size": file_size,
                    "is_html": file_name.endswith('.html'),
                    "is_index": file_name == 'index.html'
                })
        
        return {"files": files}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task files {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()
        
        
async def content_generator(buffer: BytesIO, chunk_size: int = 8192) -> AsyncGenerator[bytes, None]:
    while True:
        data = buffer.read(chunk_size)

        if not data:
            break

        yield data
        

@router.get("/{task_id}/download")
async def download_task(task_id: str, repo: TaskRepository = Depends(get_task_repository)):
    """Download task output as ZIP file"""
    try:
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if not task.output_directory or not os.path.exists(task.output_directory):
            raise HTTPException(status_code=404, detail="Task output not found")
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(task.output_directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, task.output_directory)
                    zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)

        response = StreamingResponse(
            content_generator(zip_buffer),
            headers={"Content-Disposition": f"attachment; filename={task.title.replace(' ', '_')}_{task_id}.zip"}
        )

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.get("/{task_id}/preview/{file_path:path}")
async def preview_file(task_id: str, file_path: str, repo: TaskRepository = Depends(get_task_repository)):
    """Preview a file from the task output"""
    try:
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if not task.output_directory:
            raise HTTPException(status_code=404, detail="Task output not found")
        
        full_path = os.path.join(task.output_directory, file_path)
        
        # Security check - ensure the file is within the task directory
        if not os.path.abspath(full_path).startswith(os.path.abspath(task.output_directory)):
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(full_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing file {task_id}/{file_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    repo: TaskRepository = Depends(get_task_repository)
):
    """Delete a task"""
    try:
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Delete from database
        success = repo.delete_task(task_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete task")
        
        # Publish deletion event
        event = EventPayload(
            type=EventType.MESSAGE,
            data={
                "event_type": "task_deleted",
                "task_id": task_id
            },
            channel="tasks"
        )
        background_tasks.add_task(EventHandler.event_handler().publish, event)
        
        return {"message": "Task deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

# Task Steps Endpoints
@router.get("/{task_id}/steps", response_model=List[TaskStepResponse])
async def get_task_steps(task_id: str, repo: TaskRepository = Depends(get_task_repository)):
    """Get all steps for a specific task"""
    try:
        # Verify task exists
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        steps = repo.get_task_steps(task_id)
        return [step_to_response(step) for step in steps]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task steps {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()

@router.put("/{task_id}/steps/{step_id}/status")
async def update_step_status(
    task_id: str,
    step_id: str,
    request: UpdateStepStatusRequest,
    background_tasks: BackgroundTasks,
    repo: TaskRepository = Depends(get_task_repository)
):
    """Update the status of a specific step"""
    try:
        # Verify task exists
        task = repo.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Update step status
        step = repo.update_step_status(
            step_id=step_id,
            status=request.status,
            output=request.output,
            error_message=request.error_message
        )
        
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")
        
        # Publish step status update
        event = EventPayload(
            type=EventType.MESSAGE,
            data={
                "event_type": "step_status_updated",
                "task_id": task_id,
                "step": step_to_response(step).model_dump()
            },
            channel="tasks"
        )
        background_tasks.add_task(EventHandler.event_handler().publish, event)
        
        return step_to_response(step)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating step status {task_id}/{step_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        repo.db.close()
