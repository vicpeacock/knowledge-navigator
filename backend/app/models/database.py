from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float, JSON, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.database import Base


class Tenant(Base):
    """Tenant (cliente) per multi-tenancy"""
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    schema_name = Column(String(63), nullable=False, unique=True)  # PostgreSQL schema name
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    tenant_metadata = Column("metadata", JSONB, default={})  # Use tenant_metadata as attribute name, but "metadata" as column name

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    """User per tenant"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_metadata = Column("metadata", JSONB, default={})  # Use user_metadata as attribute name, but "metadata" as column name

    # Relationships
    tenant = relationship("Tenant", back_populates="users")

    # Unique constraint: email per tenant
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uq_user_tenant_email'),
    )


class ApiKey(Base):
    """API Key per autenticazione tenant"""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)  # Hashed API key
    name = Column(String(255), nullable=True)  # Optional name/description
    active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Optional expiration

    # Relationships
    tenant = relationship("Tenant", backref="api_keys")

    # Index for fast lookups
    __table_args__ = (
        {'postgresql_indexes': [
            {'name': 'ix_api_keys_key_hash', 'columns': ['key_hash']},
            {'name': 'ix_api_keys_tenant_id', 'columns': ['tenant_id']},
        ]},
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)  # Optional title for the session
    description = Column(Text, nullable=True)  # Optional description
    status = Column(String(20), nullable=False, default="active")  # active, archived, deleted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)  # When the session was archived
    session_metadata = Column("metadata", JSONB, default={})

    # Relationships
    tenant = relationship("Tenant", backref="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    files = relationship("File", back_populates="session", cascade="all, delete-orphan")
    memory_medium = relationship("MemoryMedium", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    session_metadata = Column("metadata", JSONB, default={})

    # Relationships
    tenant = relationship("Tenant", backref="messages")
    session = relationship("Session", back_populates="messages")


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    mime_type = Column(String(100))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    session_metadata = Column("metadata", JSONB, default={})

    # Relationships
    tenant = relationship("Tenant", backref="files")
    session = relationship("Session", back_populates="files")


class MemoryShort(Base):
    __tablename__ = "memory_short"

    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, primary_key=True)
    session_id = Column(UUID(as_uuid=True), primary_key=True)
    context_data = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="memory_short")


class MemoryMedium(Base):
    __tablename__ = "memory_medium"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding_id = Column(String(255))  # Reference to ChromaDB embedding
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="memory_medium")
    session = relationship("Session", back_populates="memory_medium")


class MemoryLong(Base):
    __tablename__ = "memory_long"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    content = Column(Text, nullable=False)
    embedding_id = Column(String(255))  # Reference to ChromaDB embedding
    learned_from_sessions = Column(JSONB, default=[])  # Array of session IDs
    importance_score = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    tenant = relationship("Tenant", backref="memory_long")


class Integration(Base):
    __tablename__ = "integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    provider = Column(String(50), nullable=False)  # google, apple, microsoft, mcp
    service_type = Column(String(50), nullable=False)  # calendar, email, whatsapp, mcp_server
    credentials_encrypted = Column(Text)  # Encrypted credentials (for OAuth services) or MCP server URL/config
    enabled = Column(Boolean, default=True)
    session_metadata = Column("metadata", JSONB, default={})  # For MCP: selected_tools list, server_url, etc.

    # Relationships
    tenant = relationship("Tenant", backref="integrations")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    type = Column(String(50), nullable=False)  # "contradiction", "event", "todo", ecc.
    urgency = Column(String(20), nullable=False)  # "high", "medium", "low"
    content = Column(JSONB, nullable=False)  # Contenuto della notifica (dict)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True)  # Opzionale: sessione correlata
    read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", backref="notifications")

