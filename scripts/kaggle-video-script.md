# Script Video YouTube - Knowledge Navigator

**Durata Target**: 2-3 minuti  
**Formato**: Screen recording + voiceover

---

## [0:00 - 0:30] Problem Statement

**[SCREEN: Screenshot email/calendario affollati, poi logo Knowledge Navigator]**

**VOICEOVER**:
"Knowledge workers face an overwhelming challenge: managing vast amounts of information across multiple platforms - email, calendars, documents, web resources - while maintaining context and making informed decisions.

Traditional tools are siloed, requiring constant context switching and manual information synthesis. This fragmentation leads to information overload, context loss, and repetitive manual tasks.

Knowledge Navigator addresses these challenges by providing an intelligent, multi-agent AI assistant that understands context, remembers important information, and proactively helps users manage their knowledge and workflows."

**[TRANSITION: Fade to architecture diagram]**

---

## [0:30 - 1:15] Architecture Overview

**[SCREEN: Diagramma architettura animato o statico]**

**VOICEOVER**:
"Knowledge Navigator uses LangGraph to orchestrate a sophisticated multi-agent system. We have specialized agents: the Main Agent handles user interactions and tool calling, the Knowledge Agent retrieves relevant information from our three-tier memory system, the Integrity Agent detects contradictions in long-term memory, and the Planner Agent creates multi-step plans for complex tasks.

Our three-tier memory system maintains context from immediate conversations - stored in short-term memory with a one-hour TTL - to session-relevant information in medium-term memory with a 30-day TTL, to persistent long-term knowledge with semantic search using ChromaDB.

Comprehensive tool integration includes MCP - Model Context Protocol - for browser automation and custom tools, Google Workspace integration for Calendar, Gmail, and Tasks, and web search capabilities. All of this is monitored with full observability using OpenTelemetry for tracing and Prometheus for metrics."

**[SCREEN: Screenshot metrics dashboard]**

---

## [1:15 - 2:15] Live Demo

**[SCREEN: Screen recording live demo]**

**VOICEOVER**:
"Let me show you Knowledge Navigator in action. Here's the clean, modern interface. I'll start by asking about my calendar for next week."

**[ACTION: Mostra chat, digita "What meetings do I have next week?"]**

"The agent uses Google Calendar integration to retrieve my events. Notice how it maintains context across the conversation."

**[ACTION: Mostra risposta con eventi calendario]**

"Now let me ask about a previous meeting we discussed."

**[ACTION: Digita "What did we discuss about the project X meeting?"]**

"The system retrieves information from long-term memory, showing how our semantic search works across conversation history."

**[ACTION: Mostra risposta con memoria recuperata]**

"Background monitoring detects new emails and creates proactive notifications. Here you can see real-time notifications appearing."

**[ACTION: Mostra notifiche che arrivano]**

"The system also supports web search, file uploads, and natural language queries across all integrated tools."

**[ACTION: Mostra esempio web search o file upload]**

---

## [2:15 - 2:30] Build Process

**[SCREEN: Screenshot GitHub repository, poi screenshot Cloud Run]**

**VOICEOVER**:
"Knowledge Navigator is built with FastAPI for the backend, LangGraph for agent orchestration, and Next.js for the frontend. It's deployed on Google Cloud Run with Vertex AI - Gemini 2.5 Flash - for the LLM, Supabase for PostgreSQL, and ChromaDB Cloud for vector storage.

The codebase is open source and well-documented. Check out our GitHub repository for complete setup instructions, architecture documentation, and the full source code.

You can try it live at the URLs shown on screen, or deploy your own instance using our comprehensive deployment guide."

**[SCREEN: Mostra URL GitHub, Backend, Frontend, API Docs]**

**[END SCREEN: Logo Knowledge Navigator + "GitHub: github.com/vicpeacock/knowledge-navigator"]**

---

## Note per Recording

1. **Parla lentamente e chiaramente** - meglio essere un po' più lenti che troppo veloci
2. **Pausa tra sezioni** - facilita editing
3. **Mostra UI reale** - screenshot o screen recording dell'applicazione live
4. **Evidenzia features chiave** - tool calling, memory retrieval, notifications
5. **Mantieni durata < 3 minuti** - meglio 2:30 che 3:10

## Timing Suggerito

- Problem Statement: 30 secondi (può essere ridotto a 25s se necessario)
- Architecture: 45 secondi (può essere ridotto a 40s se necessario)
- Demo: 60 secondi (può essere ridotto a 50s se necessario)
- Build: 15 secondi (può essere ridotto a 10s se necessario)

**Totale**: ~2:30 - 2:45 (ben sotto il limite di 3 minuti)

