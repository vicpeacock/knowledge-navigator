from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# Session Schemas
class SessionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="active", pattern="^(active|archived|deleted)$")
    metadata: Dict[str, Any] = {}


class SessionCreate(SessionBase):
    pass


class SessionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|archived|deleted)$")
    metadata: Optional[Dict[str, Any]] = None


class Session(SessionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Message Schemas
class MessageBase(BaseModel):
    content: str
    role: str = Field(..., pattern="^(user|assistant|system)$")
    metadata: Dict[str, Any] = {}


class MessageCreate(MessageBase):
    session_id: UUID


class Message(MessageBase):
    id: UUID
    session_id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True


# File Schemas
class FileBase(BaseModel):
    filename: str
    mime_type: Optional[str] = None
    metadata: Dict[str, Any] = {}


class FileCreate(FileBase):
    session_id: UUID
    filepath: str


class File(FileBase):
    id: UUID
    session_id: UUID
    filepath: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


# Memory Schemas
class MemoryShort(BaseModel):
    session_id: UUID
    context_data: Dict[str, Any]
    expires_at: datetime


class MemoryMediumBase(BaseModel):
    content: str
    embedding_id: Optional[str] = None


class MemoryMediumCreate(MemoryMediumBase):
    session_id: UUID


class MemoryMedium(MemoryMediumBase):
    id: UUID
    session_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class MemoryLongBase(BaseModel):
    content: str
    importance_score: float = 0.0
    embedding_id: Optional[str] = None


class MemoryLongCreate(MemoryLongBase):
    learned_from_sessions: List[UUID] = []


class MemoryLong(MemoryLongBase):
    id: UUID
    learned_from_sessions: List[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


# Integration Schemas
class IntegrationBase(BaseModel):
    provider: str
    service_type: str = Field(..., pattern="^(calendar|email|whatsapp|mcp_server)$")
    enabled: bool = True
    metadata: Dict[str, Any] = {}


class IntegrationCreate(IntegrationBase):
    credentials_encrypted: Optional[str] = None


class IntegrationUpdate(BaseModel):
    credentials_encrypted: Optional[str] = None
    enabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class Integration(IntegrationBase):
    id: UUID

    class Config:
        from_attributes = True


# Chat Request/Response
class ChatRequest(BaseModel):
    message: str
    session_id: UUID
    use_memory: bool = True
    force_web_search: bool = False  # Force web search for this request (like Ollama's web toggle)


class ToolExecutionDetail(BaseModel):
    """Details about a tool execution"""
    tool_name: str
    parameters: Dict[str, Any] = {}
    result: Dict[str, Any] = {}
    success: bool = True
    error: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: UUID
    memory_used: Dict[str, Any] = {}
    tools_used: List[str] = []  # Kept for backward compatibility
    tool_details: List[ToolExecutionDetail] = []  # Detailed information about tool executions


# Memory Info Schema
class LongTermMemoryItem(BaseModel):
    content: str
    importance_score: float
    created_at: datetime
    learned_from_sessions: List[str] = []

class MemoryInfo(BaseModel):
    short_term: Optional[Dict[str, Any]] = None
    medium_term_samples: List[str] = []
    long_term_samples: List[str] = []  # Kept for backward compatibility
    long_term_memories: List[LongTermMemoryItem] = []  # New: full details
    files_count: int = 0
    total_messages: int = 0

