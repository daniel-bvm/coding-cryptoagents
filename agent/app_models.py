from pydantic import BaseModel, Field, TypeAdapter
from typing import Literal, Optional
import uuid

class Step(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task: str
    expectation: str
    reason: str = ""
    
class StepV2(Step):
    step_type: Literal["research", "build"] = "research"

StepV2List = TypeAdapter(list[StepV2])

class StepOutput(BaseModel):
    step_id: str
    full: str
    summary: str | None = None

class ClaudeCodeStepOutput(StepOutput):
    session_id: str