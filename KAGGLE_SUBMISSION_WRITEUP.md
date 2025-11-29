# Knowledge Navigator: Multi-Agent AI Assistant for Enterprise Knowledge Management

## Problem Statement

In today's enterprise environment, knowledge workers face an overwhelming challenge: managing vast amounts of information across multiple platforms (email, calendars, documents, web resources) while maintaining context and making informed decisions. Traditional tools are siloed, requiring constant context switching and manual information synthesis. This fragmentation leads to:

- **Information Overload**: Critical information scattered across emails, calendars, and documents
- **Context Loss**: Difficulty maintaining continuity across multiple sessions and conversations
- **Manual Work**: Repetitive tasks like scheduling, email triage, and information retrieval
- **Knowledge Fragmentation**: Important insights get lost in conversation history

**Knowledge Navigator** addresses these challenges by providing an intelligent, multi-agent AI assistant that understands context, remembers important information, and proactively helps users manage their knowledge and workflows.

## Solution Overview

Knowledge Navigator is a **production-ready, enterprise-grade multi-agent AI assistant** built with LangGraph, FastAPI, and Next.js. It combines:

- **Multi-Agent Architecture**: Specialized agents for different tasks (knowledge retrieval, integrity checking, planning, notifications)
- **Advanced Memory System**: Three-tier memory (short/medium/long-term) with semantic search
- **Comprehensive Tool Integration**: MCP (Model Context Protocol), Google Workspace (Calendar, Gmail, Tasks), web search, and custom tools
- **Full Observability**: OpenTelemetry tracing and Prometheus metrics for production monitoring
- **Enterprise Features**: Multi-tenancy, user isolation, role-based access control

The system is **deployed on Google Cloud Run** with **Vertex AI (Gemini)** integration, demonstrating production readiness and scalability.

## Architecture

### Multi-Agent System (LangGraph)

Knowledge Navigator uses **LangGraph** for orchestration, implementing a sophisticated state machine with specialized agents:

1. **Main Agent**: Handles user interactions, tool calling, and response generation
2. **Knowledge Agent**: Retrieves relevant information from multi-level memory
3. **Integrity Agent**: Detects contradictions in long-term memory (background)
4. **Planner Agent**: Creates multi-step plans for complex tasks
5. **Notification Collector**: Aggregates notifications from various sources

**Flow**: User input → Context assembly (memory + history) → LangGraph execution → Tool calls (iterative) → Response streaming → Background processing (memory extraction, integrity checks)

### Memory Architecture

**Three-Tier Memory System**:

- **Short-Term** (TTL: 1 hour): Session-specific context, stored in PostgreSQL with in-memory cache
- **Medium-Term** (TTL: 30 days): Session-relevant information, stored in PostgreSQL + ChromaDB embeddings
- **Long-Term** (Persistent): Cross-session knowledge, stored in PostgreSQL + ChromaDB with semantic search

**Key Features**:
- Automatic knowledge extraction from conversations (`ConversationLearner`)
- Semantic search using ChromaDB (cosine similarity)
- Contradiction detection (`SemanticIntegrityChecker`) with confidence threshold 0.90
- Memory consolidation (deduplication, merging similar memories)
- Context compaction (automatic summarization of long conversations)

### Tool System

**Tool Categories**:

1. **MCP Tools**: Browser automation (Playwright), dynamic tools from MCP servers
2. **Google Workspace**: Calendar (read events, natural language queries), Gmail (read, send, archive), Tasks (create, list, update)
3. **Built-in Tools**: Web search (Google Custom Search API), file upload/analysis
4. **Custom Tools**: User-defined tools via MCP Gateway

**Tool Execution**: LLM decides which tools to use dynamically. Tools are executed iteratively until the task is complete.

### Observability

**Tracing** (OpenTelemetry):
- Distributed tracing across frontend and backend
- Trace correlation (frontend request → backend processing → tool calls → LLM requests)
- Automatic trace ID propagation

**Metrics** (Prometheus):
- Performance metrics (latency, throughput)
- Error metrics (error rate, error types)
- Agent metrics (tool usage, session duration)
- Memory metrics (operations, retrieval success)
- Integration metrics (calendar/email operations)

**Dashboard**: Real-time metrics dashboard at `/admin/metrics` showing system health and performance.

### Multi-Tenancy & Security

- **Tenant Isolation**: Complete data isolation per tenant (PostgreSQL schemas, ChromaDB collections)
- **User Isolation**: User-specific data within tenants
- **Authentication**: JWT with refresh tokens
- **Authorization**: Role-based access control (admin, user, viewer)
- **Encryption**: Encrypted credentials for OAuth integrations

## Implementation Details

### Technology Stack

**Backend**:
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 (Supabase) + ChromaDB Cloud (trychroma.com)
- **LLM**: Vertex AI (Gemini 2.5 Flash) with fallback to Ollama
- **Agent Framework**: LangGraph
- **Observability**: OpenTelemetry + Prometheus
- **Authentication**: JWT with refresh tokens

**Frontend**:
- **Framework**: Next.js 14+ (React)
- **Styling**: Tailwind CSS
- **State Management**: React Context API
- **Real-time**: Server-Sent Events (SSE) for notifications and agent activity

**Infrastructure**:
- **Deployment**: Google Cloud Run
- **Container**: Docker
- **External Services**: Supabase (PostgreSQL), ChromaDB Cloud (vector DB)

### Key Design Decisions

1. **LangGraph over LangChain**: Better state management and agent orchestration for complex workflows
2. **Multi-Level Memory**: Balances immediate context (short-term) with persistent knowledge (long-term)
3. **Semantic Search**: ChromaDB for efficient similarity search across large knowledge bases
4. **Vertex AI over Gemini API**: Better reliability and safety filter handling for production
5. **MCP Integration**: Extensible tool system via Model Context Protocol
6. **Observability First**: Built-in tracing and metrics for production monitoring

### Challenges Solved

1. **Context Window Management**: Automatic summarization when conversations exceed LLM limits
2. **Memory Contradictions**: Advanced detection system with confidence thresholding and type filtering
3. **Tool Reliability**: Comprehensive error handling and retry logic for external APIs
4. **Multi-Tenancy**: Efficient data isolation using PostgreSQL schemas and ChromaDB collections
5. **Real-time Updates**: SSE for live notifications and agent activity streaming

## Value Proposition

### For Enterprise Users

- **Productivity**: Automates repetitive tasks (email triage, calendar management, information retrieval)
- **Knowledge Management**: Centralizes information with semantic search and long-term memory
- **Context Continuity**: Maintains context across sessions and conversations
- **Proactive Assistance**: Background monitoring (email, calendar) with intelligent notifications

### For Organizations

- **Multi-Tenancy**: Isolated environments for different teams/departments
- **Scalability**: Cloud-native architecture (Cloud Run) with auto-scaling
- **Observability**: Full visibility into system performance and agent behavior
- **Security**: Enterprise-grade authentication, authorization, and data isolation

### Use Cases

1. **Executive Assistant**: Manage calendar, prioritize emails, retrieve information
2. **Knowledge Worker**: Research topics, synthesize information, maintain knowledge base
3. **Project Manager**: Track tasks, schedule meetings, coordinate team activities
4. **Customer Support**: Quick access to knowledge base, automated responses

## Deployment

**Production Deployment**: Google Cloud Run
- **Backend URL**: https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app
- **Frontend URL**: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app
- **API Documentation**: https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/docs

**External Services**:
- **PostgreSQL**: Supabase (managed PostgreSQL)
- **Vector DB**: ChromaDB Cloud (managed ChromaDB)
- **LLM**: Vertex AI (Gemini 2.5 Flash)

**Health Status**: All services healthy, comprehensive E2E tests passed (39/41 tests, 95.1% success rate)

## Evaluation

**Agent Evaluation Framework**: 14 test cases covering:
- Calendar queries (natural language)
- Email operations
- Web search
- Memory operations
- Google Maps integration
- General agent behavior

**Test Results**: Comprehensive E2E test suite with 95.1% success rate, demonstrating production readiness.

## Bonus Features

✅ **Gemini Integration**: Vertex AI (Gemini 2.5 Flash) for main LLM  
✅ **Cloud Deployment**: Google Cloud Run with auto-scaling  
⏳ **YouTube Video**: Demo video (to be created)

## Conclusion

Knowledge Navigator demonstrates a **production-ready, enterprise-grade multi-agent AI assistant** that solves real-world knowledge management challenges. With its sophisticated architecture, comprehensive tool integration, and full observability, it provides a solid foundation for enterprise AI applications.

**GitHub Repository**: https://github.com/vicpeacock/knowledge-navigator  
**Documentation**: Comprehensive documentation in `/docs` folder

---

**Track**: Enterprise Agents  
**Keywords**: Multi-Agent, LangGraph, Memory, MCP, Observability, Enterprise, Cloud Run, Vertex AI

