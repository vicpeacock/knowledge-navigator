from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)  # Optional title for the session
    description = Column(Text, nullable=True)  # Optional description
    status = Column(String(20), nullable=False, default="active")  # active, archived, deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)  # When the session was archived
    session_metadata = Column("metadata", JSONB, default={})

    # Relationships
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    files = relationship("File", back_populates="session", cascade="all, delete-orphan")
    memory_medium = relationship("MemoryMedium", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    session_metadata = Column("metadata", JSONB, default={})

    # Relationships
    session = relationship("Session", back_populates="messages")


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    mime_type = Column(String(100))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    session_metadata = Column("metadata", JSONB, default={})

    # Relationships
    session = relationship("Session", back_populates="files")


class MemoryShort(Base):
    __tablename__ = "memory_short"

    session_id = Column(UUID(as_uuid=True), primary_key=True)
    context_data = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class MemoryMedium(Base):
    __tablename__ = "memory_medium"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding_id = Column(String(255))  # Reference to ChromaDB embedding
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("Session", back_populates="memory_medium")


class MemoryLong(Base):
    __tablename__ = "memory_long"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    embedding_id = Column(String(255))  # Reference to ChromaDB embedding
    learned_from_sessions = Column(JSONB, default=[])  # Array of session IDs
    importance_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False)  # google, apple, microsoft, mcp
    service_type = Column(String(50), nullable=False)  # calendar, email, whatsapp, mcp_server
    credentials_encrypted = Column(Text)  # Encrypted credentials (for OAuth services) or MCP server URL/config
    enabled = Column(Boolean, default=True)
    session_metadata = Column("metadata", JSONB, default={})  # For MCP: selected_tools list, server_url, etc.

