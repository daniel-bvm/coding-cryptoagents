from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
import os
from agent.configs import settings

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{settings.opencode_directory}/tasks.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    expectation = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    current_step = Column(String, nullable=True)
    total_steps = Column(Integer, default=0)
    completed_steps = Column(Integer, default=0)
    output_directory = Column(String, nullable=True)
    has_index_html = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

class TaskStep(Base):
    __tablename__ = "task_steps"
    
    id = Column(String, primary_key=True, index=True)
    task_id = Column(String, nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    step_type = Column(String, nullable=False)  # "plan" or "build"
    task_description = Column(Text, nullable=False)
    expectation = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, executing, completed, failed
    output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Create tables
Base.metadata.create_all(bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # We'll close it manually

class TaskRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create_task(self, task_id: str, title: str, expectation: str = None) -> Task:
        task = Task(
            id=task_id,
            title=title,
            expectation=expectation,
            status="pending"
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        return self.db.query(Task).filter(Task.id == task_id).first()
    
    def get_all_tasks(self, limit: int = 100, offset: int = 0) -> List[Task]:
        res = self.db.query(Task).order_by(Task.created_at.desc()).offset(offset).limit(limit).all()
        return res
    
    def update_task_status(self, task_id: str, status: str, error_message: str = None) -> Optional[Task]:
        task = self.get_task(task_id)
        if task:
            task.status = status
            task.updated_at = datetime.utcnow()
            if error_message:
                task.error_message = error_message
            if status == "completed":
                task.completed_at = datetime.utcnow()
                task.progress = 100
            self.db.commit()
            self.db.refresh(task)
        return task
    
    def update_task_progress(self, task_id: str, progress: int, current_step: str = None, 
                           completed_steps: int = None, total_steps: int = None) -> Optional[Task]:
        task = self.get_task(task_id)
        if task:
            task.progress = max(0, min(100, progress))
            task.updated_at = datetime.utcnow()
            if current_step:
                task.current_step = current_step
            if completed_steps is not None:
                task.completed_steps = completed_steps
            if total_steps is not None:
                task.total_steps = total_steps
            self.db.commit()
            self.db.refresh(task)
        return task
    
    def update_task_output(self, task_id: str, output_directory: str, has_index_html: bool = False) -> Optional[Task]:
        task = self.get_task(task_id)
        if task:
            task.output_directory = output_directory
            task.has_index_html = has_index_html
            task.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(task)
        return task
    
    def delete_task(self, task_id: str) -> bool:
        task = self.get_task(task_id)
        if task:
            # Also delete associated steps
            self.db.query(TaskStep).filter(TaskStep.task_id == task_id).delete()
            self.db.delete(task)
            self.db.commit()
            return True
        return False
    
    # Task Step Management
    def create_task_step(self, step_id: str, task_id: str, step_number: int, 
                        step_type: str, task_description: str, expectation: str = None, 
                        reason: str = None) -> TaskStep:
        step = TaskStep(
            id=step_id,
            task_id=task_id,
            step_number=step_number,
            step_type=step_type,
            task_description=task_description,
            expectation=expectation,
            reason=reason,
            status="pending"
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step
    
    def get_task_steps(self, task_id: str) -> List[TaskStep]:
        return self.db.query(TaskStep).filter(TaskStep.task_id == task_id).order_by(TaskStep.step_number).all()
    
    def update_step_status(self, step_id: str, status: str, output: str = None, 
                          error_message: str = None) -> Optional[TaskStep]:
        step = self.db.query(TaskStep).filter(TaskStep.id == step_id).first()
        if step:
            step.status = status
            if output:
                step.output = output
            if error_message:
                step.error_message = error_message
            if status == "executing" and not step.started_at:
                step.started_at = datetime.utcnow()
            elif status in ["completed", "failed"]:
                step.completed_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(step)
        return step
    
    def get_step(self, step_id: str) -> Optional[TaskStep]:
        return self.db.query(TaskStep).filter(TaskStep.id == step_id).first()
    
    def mark_incomplete_tasks_as_failed(self) -> int:
        """Mark all incomplete tasks (pending, processing) as failed at startup"""
        incomplete_statuses = ["pending", "processing"]
        incomplete_tasks = self.db.query(Task).filter(Task.status.in_(incomplete_statuses)).all()
        
        count = 0
        for task in incomplete_tasks:
            task.status = "failed"
            task.error_message = "Task marked as failed due to application restart"
            task.updated_at = datetime.utcnow()
            count += 1
        
        # Also mark any executing or pending steps as failed
        incomplete_steps = self.db.query(TaskStep).filter(
            TaskStep.status.in_(["pending", "executing"])
        ).all()
        
        for step in incomplete_steps:
            step.status = "failed"
            step.error_message = "Step marked as failed due to application restart"
            if not step.started_at and step.status == "executing":
                step.started_at = datetime.utcnow()
            step.completed_at = datetime.utcnow()
        
        self.db.commit()
        return count

def get_task_repository() -> TaskRepository:
    db = get_db()
    return TaskRepository(db)
