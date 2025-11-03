from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List
from datetime import datetime, timedelta, timezone
import json

from app.db.database import get_db
from app.models.database import Session as SessionModel, Message as MessageModel
from app.models.schemas import (
    Session,
    SessionCreate,
    SessionUpdate,
    Message,
    MessageCreate,
    ChatRequest,
    ChatResponse,
    MemoryInfo,
)
from app.core.dependencies import get_ollama_client, get_memory_manager
from app.core.ollama_client import OllamaClient
from app.core.memory_manager import MemoryManager

router = APIRouter()


@router.get("/", response_model=List[Session])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all sessions"""
    result = await db.execute(select(SessionModel).order_by(SessionModel.updated_at.desc()))
    sessions = result.scalars().all()
    # Map session_metadata to metadata for response
    return [
        Session(
            id=s.id,
            name=s.name,
            created_at=s.created_at,
            updated_at=s.updated_at,
            metadata=s.session_metadata or {},
        )
        for s in sessions
    ]


@router.post("/", response_model=Session, status_code=201)
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new session"""
    session_dict = session_data.model_dump()
    # Map metadata to session_metadata for database model
    if 'metadata' in session_dict:
        metadata_value = session_dict.pop('metadata')
        session_dict['session_metadata'] = metadata_value
    session = SessionModel(**session_dict)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    # Return response with metadata mapped back
    return Session(
        id=session.id,
        name=session.name,
        created_at=session.created_at,
        updated_at=session.updated_at,
        metadata=session.session_metadata or {},
    )


@router.get("/{session_id}", response_model=Session)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a session by ID"""
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Map session_metadata to metadata for response
    return Session(
        id=session.id,
        name=session.name,
        created_at=session.created_at,
        updated_at=session.updated_at,
        metadata=session.session_metadata or {},
    )


@router.put("/{session_id}", response_model=Session)
async def update_session(
    session_id: UUID,
    session_data: SessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a session"""
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    update_data = session_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(session, key, value)
    
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a session"""
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.delete(session)
    await db.commit()
    return None


@router.get("/{session_id}/messages", response_model=List[Message])
async def get_session_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all messages for a session"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        result = await db.execute(
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.timestamp)
        )
        messages = result.scalars().all()
        logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}", exc_info=True)
        raise
    # Map session_metadata to metadata for response
    result_messages = []
    for idx, m in enumerate(messages):
        try:
            # Convert session_metadata to dict if it's not already
            metadata = m.session_metadata
            
            # Handle different types of metadata - PostgreSQL JSONB can be tricky
            # JSONB columns can return different types depending on SQLAlchemy/PostgreSQL version
            if metadata is None:
                metadata = {}
            elif isinstance(metadata, dict):
                # Already a dict, ensure it's a plain Python dict (not a dict-like object)
                try:
                    # Create a new dict to ensure it's a plain Python dict
                    metadata = dict(metadata.items())
                except:
                    metadata = {}
            else:
                # For non-dict objects (like JSONB wrappers), use the most reliable approach
                original_type = type(metadata).__name__
                
                # Try multiple strategies to extract the actual dict value
                converted = False
                
                # Strategy 1: Check if it's a JSONB adapter and get the actual value
                # SQLAlchemy JSONB might wrap the value, try to unwrap it
                try:
                    # Some JSONB implementations expose the data via specific methods
                    if hasattr(metadata, 'asdict'):
                        metadata = metadata.asdict()
                        converted = True
                    elif hasattr(metadata, 'data'):
                        data_attr = getattr(metadata, 'data')
                        if isinstance(data_attr, dict):
                            metadata = dict(data_attr)
                            converted = True
                    elif hasattr(metadata, 'value'):
                        # Some wrappers use .value
                        value = getattr(metadata, 'value')
                        if isinstance(value, dict):
                            metadata = dict(value)
                            converted = True
                except Exception as e:
                    logger.debug(f"Strategy 1 failed: {e}")
                
                # Strategy 2: Use vars() or __dict__ if available
                if not converted:
                    try:
                        obj_dict = vars(metadata)
                        if isinstance(obj_dict, dict) and obj_dict:
                            # Check if there's a meaningful data attribute
                            if 'data' in obj_dict and isinstance(obj_dict['data'], dict):
                                metadata = dict(obj_dict['data'])
                                converted = True
                            elif len(obj_dict) > 0:
                                # If the dict itself has keys, it might be the data
                                metadata = {k: v for k, v in obj_dict.items() if not k.startswith('_')}
                                if metadata:
                                    converted = True
                    except Exception as e:
                        logger.debug(f"Strategy 2 failed: {e}")
                
                # Strategy 3: JSON serialization (may convert to string representation)
                if not converted:
                    try:
                        import json
                        # Try with default=lambda o: o.__dict__ to preserve structure
                        json_str = json.dumps(metadata, default=lambda o: vars(o) if hasattr(o, '__dict__') else str(o), ensure_ascii=False)
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict):
                            metadata = parsed
                            converted = True
                    except Exception as e:
                        logger.debug(f"Strategy 3 failed: {e}")
                
                # Strategy 4: Force dict conversion (last resort)
                if not converted:
                    try:
                        if hasattr(metadata, 'items'):
                            metadata = dict(metadata.items())
                            converted = True
                        elif hasattr(metadata, '__iter__') and not isinstance(metadata, (str, bytes)):
                            # Only try if it's not a string
                            metadata = {}
                            converted = True  # Accept empty dict as conversion
                    except Exception as e:
                        logger.debug(f"Strategy 4 failed: {e}")
                
                # Final fallback: if nothing worked, use empty dict
                if not converted or not isinstance(metadata, dict):
                    logger.warning(f"Could not convert metadata from {original_type}, using empty dict. Repr: {repr(metadata)[:100]}")
                    metadata = {}
        
            result_messages.append(
                Message(
                    id=m.id,
                    session_id=m.session_id,
                    role=m.role,
                    content=m.content,
                    timestamp=m.timestamp,
                    metadata=metadata,
                )
            )
        except Exception as e:
            logger.error(f"Error processing message {idx} (id={m.id}): {e}", exc_info=True)
            # Still add the message but with empty metadata to avoid breaking the whole response
            try:
                result_messages.append(
                    Message(
                        id=m.id,
                        session_id=m.session_id,
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                        metadata={},
                    )
                )
            except Exception as e2:
                logger.error(f"Failed to add message even with empty metadata: {e2}", exc_info=True)
                raise
    
    logger.info(f"Returning {len(result_messages)} processed messages")
    return result_messages


@router.post("/{session_id}/chat", response_model=ChatResponse)
async def chat(
    session_id: UUID,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Send a message and get AI response"""
    # Verify session exists
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get session context (previous messages)
    messages_result = await db.execute(
        select(MessageModel)
        .where(MessageModel.session_id == session_id)
        .order_by(MessageModel.timestamp)
    )
    previous_messages = messages_result.scalars().all()
    
    # Build context - ensure we're using plain dicts, not SQLAlchemy objects
    session_context = [
        {"role": str(msg.role), "content": str(msg.content)}
        for msg in previous_messages[-10:]  # Last 10 messages
    ]
    
    # Retrieve memory if enabled
    retrieved_memory = []
    memory_used = {"short_term": False, "medium_term": [], "long_term": [], "files": []}
    
    # Get the most recently uploaded file information from database
    from app.models.database import File as FileModel
    latest_file_result = await db.execute(
        select(FileModel)
        .where(FileModel.session_id == session_id)
        .order_by(FileModel.uploaded_at.desc())
        .limit(1)
    )
    latest_file = latest_file_result.scalar_one_or_none()
    
    # Always retrieve file content for the session (files are session-specific context)
    # Pass db to filter out embeddings for deleted files
    file_content = await memory.retrieve_file_content(
        session_id, request.message, n_results=5, db=db
    )
    memory_used["files"] = file_content
    
    # Add information about the most recent file to context
    file_context_info = []
    if latest_file:
        file_context_info.append(
            f"[IMPORTANT: File Information]\n"
            f"The most recently uploaded file in this session is:\n"
            f"- Filename: {latest_file.filename}\n"
            f"- Uploaded at: {latest_file.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- File ID: {latest_file.id}\n"
            f"When the user asks about 'the last file', 'the most recent file', 'the latest file', or 'ultimo file', they are referring to this file: {latest_file.filename}\n"
        )
    
    # Add file content to retrieved memory with clear labeling
    if file_content:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Retrieved {len(file_content)} file contents for session {session_id}")
        
        for i, content in enumerate(file_content):
            # Label file content clearly
            if content and content.strip():  # Only add non-empty content
                labeled_content = f"[Content from uploaded file {i+1}]:\n{content}"
                retrieved_memory.append(labeled_content)
                logger.info(f"Added file content {i+1}, length: {len(content)} chars")
            else:
                logger.warning(f"File content {i+1} is empty or None")
    else:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"No file content retrieved for session {session_id}")
    
    if request.use_memory:
        # Short-term memory
        short_term = await memory.get_short_term_memory(db, session_id)
        if short_term:
            memory_used["short_term"] = True
        
        # Medium-term memory
        medium_mem = await memory.retrieve_medium_term_memory(
            session_id, request.message, n_results=3
        )
        memory_used["medium_term"] = medium_mem
        retrieved_memory.extend(medium_mem)
        
        # Long-term memory
        long_mem = await memory.retrieve_long_term_memory(
            request.message, n_results=3
        )
        memory_used["long_term"] = long_mem
        retrieved_memory.extend(long_mem)
    
    # Save user message
    user_message = MessageModel(
        session_id=session_id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.commit()
    
    # Add file context info to retrieved memory if available
    if file_context_info:
        retrieved_memory = file_context_info + retrieved_memory
    
    # Initialize tool manager
    from app.core.tool_manager import ToolManager
    tool_manager = ToolManager(db=db)
    
    # Get tools description for LLM
    tools_description = tool_manager.get_tools_system_prompt()
    
    tools_used = []
    max_tool_iterations = 3  # Limit tool call iterations
    tool_iteration = 0
    
    # Tool calling loop: LLM can request tools, we execute them, then reinvoke LLM with results
    current_prompt = request.message
    response_text = ""
    tool_results = []
    response_data = None  # Initialize to avoid undefined variable
    
    import logging
    logger = logging.getLogger(__name__)
    
    while tool_iteration < max_tool_iterations:
        logger.info(f"Tool calling iteration {tool_iteration}, prompt length: {len(current_prompt)}")
        
        # Generate response with tools available
        try:
            response_data = await ollama.generate_with_context(
                prompt=current_prompt,
                session_context=session_context,
                retrieved_memory=retrieved_memory if retrieved_memory else None,
                tools_description=tools_description if tool_iteration == 0 else None,  # Only show tools on first iteration
                return_raw=True,
            )
            
            # Handle both string response (old) and dict response (new with tool_calls)
            if isinstance(response_data, dict):
                response_text = response_data.get("content", "")
                ollama_tool_calls = response_data.get("_parsed_tool_calls")
                if ollama_tool_calls:
                    logger.info(f"Ollama returned {len(ollama_tool_calls)} tool_calls in response structure")
                # Debug: log the structure if content is empty
                if not response_text and not ollama_tool_calls:
                    raw_result = response_data.get("raw_result", {})
                    logger.warning(f"Empty content and no tool_calls. Raw result keys: {list(raw_result.keys())}")
                    if "message" in raw_result:
                        msg = raw_result["message"]
                        logger.warning(f"Message structure: {type(msg)}, keys: {list(msg.keys()) if isinstance(msg, dict) else 'N/A'}")
            else:
                response_text = response_data if response_data else ""
                if not response_text:
                    logger.warning(f"Response_data is not a dict and empty. Type: {type(response_data)}")
            
            logger.info(f"Ollama response received, length: {len(response_text) if response_text else 0}, has content: {bool(response_text and response_text.strip())}")
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}", exc_info=True)
            response_text = f"Errore nella chiamata al modello: {str(e)}"
            response_data = None
            break
        
        # Check if we have tool_calls first (before checking if content is empty)
        # This is important because tool_calls might mean empty content is OK
        has_tool_calls_in_response = False
        if response_data and isinstance(response_data, dict):
            parsed_tc = response_data.get("_parsed_tool_calls")
            raw_result = response_data.get("raw_result", {})
            if parsed_tc or (raw_result.get("message", {}).get("tool_calls")):
                has_tool_calls_in_response = True
        
        if not response_text or not response_text.strip():
            if has_tool_calls_in_response:
                logger.info("Content is empty but tool_calls present, continuing...")
                # Set empty string - we'll generate response after tool execution
                response_text = ""
            else:
                logger.error(f"Empty response from Ollama on iteration {tool_iteration} and no tool_calls. Response_data type: {type(response_data)}")
                if response_data and isinstance(response_data, dict):
                    logger.error(f"Response_data dict keys: {list(response_data.keys())}")
                    raw_result = response_data.get('raw_result', {})
                    if raw_result:
                        msg = raw_result.get('message', {})
                        if isinstance(msg, dict):
                            logger.error(f"Message keys: {list(msg.keys())}")
                            logger.error(f"Message content: '{msg.get('content', 'NOT FOUND')}'")
                            logger.error(f"Message thinking: '{msg.get('thinking', 'NOT FOUND')[:200] if msg.get('thinking') else 'N/A'}'")
                # Return error immediately - don't continue loop if content is empty and no tool calls
                response_text = "Mi scuso, ho riscontrato un problema nella generazione della risposta. Per favore riprova."
                break
        
        # Check if LLM requested a tool call
        # First check if Ollama returned tool_calls in response structure
        tool_calls = []
        if response_data and isinstance(response_data, dict):
            # Check if we already have parsed tool calls from ollama_client
            parsed_tc = response_data.get("_parsed_tool_calls")
            if parsed_tc:
                # Already parsed in ollama_client
                tool_calls = parsed_tc
                logger.info(f"✅ LLM automatically called {len(tool_calls)} tool(s): {[tc.get('name') for tc in tool_calls]}")
            else:
                # Try to parse from raw tool_calls structure
                raw_result = response_data.get("raw_result", {})
                if "message" in raw_result and isinstance(raw_result["message"], dict):
                    message = raw_result["message"]
                    if "tool_calls" in message:
                        ollama_tc = message["tool_calls"]
                        # Convert Ollama format to our format
                        for tc in ollama_tc:
                            if "function" in tc:
                                func = tc["function"]
                                func_name = func.get("name", "")
                                func_args = func.get("arguments", {})
                                
                                # Format 1: Direct tool name (e.g., "tool.get_emails" or "get_emails")
                                if func_name and func_name not in ["tool_call", "commentary"]:
                                    # Remove "tool." prefix if present
                                    actual_name = func_name.replace("tool.", "").replace("tool_", "")
                                    if isinstance(func_args, dict):
                                        tool_calls.append({
                                            "name": actual_name,
                                            "parameters": func_args
                                        })
                                        continue
                                
                                # Format 2: Nested structure (old format)
                                if func_name == "tool_call" and isinstance(func_args, dict):
                                    if "tool_call" in func_args:
                                        tool_call_dict = func_args["tool_call"]
                                        if isinstance(tool_call_dict, dict):
                                            actual_name = tool_call_dict.get("name", "")
                                            actual_params = tool_call_dict.get("parameters", {})
                                            if actual_name:
                                                # Remove "tool." prefix if present
                                                actual_name = actual_name.replace("tool.", "").replace("tool_", "")
                                                tool_calls.append({
                                                    "name": actual_name,
                                                    "parameters": actual_params
                                                })
                        logger.info(f"Extracted {len(tool_calls)} tool calls from Ollama response structure")
        
        # Fallback: try parsing from text
        if not tool_calls:
            tool_calls = tool_manager.parse_tool_calls(response_text)
            logger.info(f"Parsed {len(tool_calls)} tool calls from response text")
        
        # If response contains only JSON tool call, remove it for next iteration
        if tool_calls and response_text.strip().startswith('{'):
            # Response is likely only the JSON tool call
            logger.info("Response contains only tool call JSON, will regenerate after tool execution")
        
        if not tool_calls:
            # No tool calls, we have a normal response - use it
            # Make sure response_text doesn't contain leftover JSON
            if response_text and response_text.strip().startswith('{') and '"tool_call"' in response_text:
                logger.warning("Response appears to be JSON but no tool calls parsed, attempting to clean")
                # Try to extract any text after JSON
                lines = response_text.split('\n')
                text_only = [l for l in lines if not l.strip().startswith('{') and '}' not in l]
                if text_only:
                    response_text = '\n'.join(text_only).strip()
                    logger.info(f"Cleaned response, new length: {len(response_text)}")
                if not response_text:
                    logger.warning("Response cleaned to empty")
            # If we have content, use it; if empty, the check after the loop will handle it
            if response_text and response_text.strip():
                logger.info(f"Using LLM response (no tools needed): {len(response_text)} chars")
            break
        
        # Execute tool calls
        iteration_tool_results = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_params = tool_call.get("parameters", {})
            
            logger.info(f"Executing tool: {tool_name} with params: {tool_params}")
            
            if tool_name:
                try:
                    result = await tool_manager.execute_tool(tool_name, tool_params, db)
                    logger.info(f"Tool {tool_name} executed successfully, result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
                    iteration_tool_results.append({
                        "tool": tool_name,
                        "result": result,
                    })
                    tools_used.append(tool_name)
                except Exception as e:
                    logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                    iteration_tool_results.append({
                        "tool": tool_name,
                        "result": {"error": str(e)},
                    })
        
        # If tools were called, reinvoke LLM with results
        if iteration_tool_results:
            # Format tool results for LLM
            tool_results_text = "\n\n=== Risultati Tool Chiamati ===\n"
            for tr in iteration_tool_results:
                tool_results_text += f"Tool: {tr['tool']}\n"
                result_str = json.dumps(tr['result'], indent=2, ensure_ascii=False, default=str)
                # If result is very long, truncate it
                if len(result_str) > 8000:
                    result_str = result_str[:8000] + "\n... [risultato troncato]"
                tool_results_text += f"Risultato: {result_str}\n\n"
            tool_results_text += "=== Fine Risultati Tool ===\n"
            tool_results_text += "IMPORTANTE: Usa SOLO i risultati dei tool sopra per rispondere. NON inventare informazioni.\n"
            tool_results_text += "Rispondi all'utente in modo naturale basandoti sui dati reali ottenuti.\n"
            
            # Update prompt with tool results and original question
            # Clear response_text since we'll regenerate with tool results
            response_text = ""
            # More explicit prompt for final response
            current_prompt = f"""L'utente ha chiesto: "{request.message}"

{tool_results_text}

IMMPORTANTE: Ora devi rispondere all'utente con un messaggio testuale chiaro e utile. 
NON usare più tool - i tool sono già stati eseguiti e hai i risultati sopra.
Rispondi in modo naturale in italiano, basandoti SOLO sui dati reali ottenuti dai tool.
Non inventare informazioni che non sono nei risultati sopra.
Inizia direttamente la tua risposta all'utente senza JSON o formattazione speciale."""
            logger.info(f"Reinvoking LLM with tool results. Prompt length: {len(current_prompt)}")
            tool_results.extend(iteration_tool_results)
        else:
            # No tool results, break
            break
        
        tool_iteration += 1
    
    # Ensure response_text is never empty
    if not response_text or not response_text.strip():
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Response text is empty after tool calling loop")
        response_text = "Mi scuso, ho riscontrato un problema nella generazione della risposta. Per favore riprova."
    
    # If we exhausted iterations and had tool calls, add note
    if tool_iteration >= max_tool_iterations and tool_calls and tool_results:
        response_text += "\n\n[Nota: Alcuni tool sono stati eseguiti per ottenere informazioni reali.]"
    
    # Save assistant message
    # Log tools usage for debugging
    if tools_used:
        logger.info(f"Tools used in this response: {tools_used}")
    else:
        logger.info("No tools were used in this response")
    
    assistant_message = MessageModel(
        session_id=session_id,
        role="assistant",
        content=response_text,
        session_metadata={"memory_used": memory_used, "tools_used": tools_used},  # Store in metadata
    )
    db.add(assistant_message)
    await db.commit()

    # Update short-term memory with new context
    if request.use_memory:
        new_context = {
            "last_user_message": request.message,
            "last_assistant_message": response_text,
            "message_count": len(previous_messages) + 2,
        }
        await memory.update_short_term_memory(db, session_id, new_context)

    # Return response
    return ChatResponse(
        response=response_text,
        session_id=session_id,
        memory_used=memory_used,
        tools_used=tools_used,
    )


@router.get("/{session_id}/memory", response_model=MemoryInfo)
async def get_session_memory(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Get memory information for a session"""
    
    # Get short-term memory
    short_term = await memory.get_short_term_memory(db, session_id)
    
    # Get sample medium-term memories (recent ones) - use a generic query
    medium_samples = await memory.retrieve_medium_term_memory(
        session_id, "sessione conversazione", n_results=5
    )
    
    # Get sample long-term memories - use a generic query
    long_samples = await memory.retrieve_long_term_memory(
        "conoscenza apprendimento", n_results=5
    )
    
    # Count files
    from app.models.database import File as FileModel
    file_count_result = await db.execute(
        select(FileModel).where(FileModel.session_id == session_id)
    )
    files_count = len(file_count_result.scalars().all())
    
    # Count total messages
    from app.models.database import Message as MessageModel
    message_count_result = await db.execute(
        select(MessageModel).where(MessageModel.session_id == session_id)
    )
    total_messages = len(message_count_result.scalars().all())
    
    return MemoryInfo(
        short_term=short_term,
        medium_term_samples=medium_samples[:5],  # Limit to 5 samples
        long_term_samples=long_samples[:5],  # Limit to 5 samples
        files_count=files_count,
        total_messages=total_messages,
    )

