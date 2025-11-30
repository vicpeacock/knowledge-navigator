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

## If I had more time, this is what I'd do

Given more development time, I would focus on the following enhancements to make Knowledge Navigator even more powerful and enterprise-ready:

### 1. Agent-to-Agent (A2A) Protocol
Implement a standardized protocol for agent communication, enabling Knowledge Navigator agents to collaborate with external agents and services. This would allow for distributed agent networks, where specialized agents (e.g., a dedicated email agent, a research agent) could communicate and share context, enabling more sophisticated multi-agent workflows and delegation.

### 2. Advanced Agent Evaluation Framework
Expand the current evaluation framework with:
- **Automated benchmarking**: Continuous evaluation against standard agent benchmarks (e.g., AgentBench, AgentEval)
- **A/B testing**: Compare different agent configurations and prompts
- **Performance regression testing**: Ensure agent quality doesn't degrade over time
- **Human-in-the-loop evaluation**: Collect feedback for improvement

### 3. Knowledge Graph Integration
Enhance the memory system with knowledge graphs to capture relationships between entities (people, projects, events, documents). This would enable:
- **Relationship queries**: "What projects is John working on?"
- **Temporal reasoning**: Track how relationships evolve over time
- **Contextual understanding**: Better understanding of entity connections
- **Visualization**: Graph-based UI for exploring knowledge relationships

### 4. Advanced Integrations
Extend integrations beyond Google Workspace:
- **Microsoft 365**: Outlook, Teams, OneDrive, SharePoint
- **Slack/Teams**: Real-time messaging and team collaboration
- **CRM Systems**: Salesforce, HubSpot integration
- **Project Management**: Jira, Asana, Trello
- **Documentation**: Confluence, Notion, Obsidian

### 5. Multi-Modal Capabilities
Add support for images, audio, and video:
- **Image understanding**: Extract information from screenshots, diagrams, charts
- **Voice input/output**: Natural voice interactions
- **Video analysis**: Summarize video content (meetings, presentations)
- **Document OCR**: Extract text from scanned documents and images

### 6. Collaborative Features
Enable team collaboration:
- **Shared knowledge bases**: Teams can share and collaborate on knowledge
- **Agent collaboration**: Multiple users' agents can work together on tasks
- **Knowledge permissions**: Fine-grained access control for shared knowledge
- **Team analytics**: Insights into team knowledge and collaboration patterns

### 7. Advanced Contradiction Detection
Improve the contradiction detection system:
- **Temporal awareness**: Distinguish between temporary facts and permanent preferences
- **Context-aware analysis**: Consider context when detecting contradictions
- **Confidence calibration**: Better confidence thresholds for different knowledge types
- **Proactive resolution**: Suggest resolutions for detected contradictions

### 8. Fine-Tuning Infrastructure
Enable customization for enterprise use:
- **Domain-specific fine-tuning**: Fine-tune models on organization-specific data
- **Custom embeddings**: Train embeddings on domain-specific documents
- **Prompt templates**: Organization-specific prompt templates and workflows
- **Custom agent behaviors**: Configure agent personalities and behaviors

### 9. Advanced Analytics & Insights
Provide deeper insights into knowledge and usage:
- **Knowledge insights**: Trends, patterns, and gaps in organizational knowledge
- **Usage analytics**: How users interact with the system
- **Productivity metrics**: Measure productivity improvements
- **ROI tracking**: Quantify value delivered by the assistant

### 10. Enhanced UI/UX
Improve user experience:
- **Mobile app**: Native iOS and Android applications
- **Voice interface**: Voice-first interactions
- **Customizable dashboards**: Personalized views and widgets
- **Advanced search**: Semantic search with filters and facets
- **Knowledge visualization**: Interactive graphs and timelines

These enhancements would transform Knowledge Navigator from a powerful AI assistant into a comprehensive enterprise knowledge platform, enabling organizations to unlock the full potential of their collective knowledge.

## Conclusion

Knowledge Navigator demonstrates a **production-ready, enterprise-grade multi-agent AI assistant** that solves real-world knowledge management challenges. With its sophisticated architecture, comprehensive tool integration, and full observability, it provides a solid foundation for enterprise AI applications.

**GitHub Repository**: https://github.com/vicpeacock/knowledge-navigator  
**Documentation**: Comprehensive documentation in `/docs` folder

---

**Track**: Enterprise Agents  
**Keywords**: Multi-Agent, LangGraph, Memory, MCP, Observability, Enterprise, Cloud Run, Vertex AI

