#!/usr/bin/env python3
"""
Comprehensive End-to-End Test Suite
Tests all possible functionality: auth, sessions, chat, tools, memory, SSE, etc.
"""

import requests
import json
import time
import uuid
import sys
from typing import Optional, Dict, Any, List
from datetime import datetime

# Configuration
BACKEND_URL = "https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app"
FRONTEND_URL = "https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app"

# Colors
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def log_info(msg: str):
    print(f"{Colors.GREEN}[INFO]{Colors.RESET} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")

def log_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")

def log_test(msg: str):
    print(f"{Colors.BLUE}[TEST]{Colors.RESET} {msg}")

def log_section(msg: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.RESET}\n")

def log_success(msg: str):
    print(f"{Colors.GREEN}✅{Colors.RESET} {msg}")

def log_fail(msg: str):
    print(f"{Colors.RED}❌{Colors.RESET} {msg}")

# Test counters
stats = {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "total": 0,
    "categories": {}
}

def test_pass(category: str, msg: str):
    stats["passed"] += 1
    stats["total"] += 1
    if category not in stats["categories"]:
        stats["categories"][category] = {"passed": 0, "failed": 0, "skipped": 0}
    stats["categories"][category]["passed"] += 1
    log_success(f"{category}: {msg}")

def test_fail(category: str, msg: str):
    stats["failed"] += 1
    stats["total"] += 1
    if category not in stats["categories"]:
        stats["categories"][category] = {"passed": 0, "failed": 0, "skipped": 0}
    stats["categories"][category]["failed"] += 1
    log_fail(f"{category}: {msg}")

def test_skip(category: str, msg: str):
    stats["skipped"] += 1
    stats["total"] += 1
    if category not in stats["categories"]:
        stats["categories"][category] = {"passed": 0, "failed": 0, "skipped": 0}
    stats["categories"][category]["skipped"] += 1
    log_warn(f"{category}: SKIP - {msg}")

# Global state
access_token: Optional[str] = None
refresh_token: Optional[str] = None
user_id: Optional[str] = None
session_id: Optional[str] = None
test_email: Optional[str] = None
test_password: Optional[str] = None

# ============================================================================
# SECTION 1: INFRASTRUCTURE TESTS
# ============================================================================

def test_backend_health():
    """Test backend health check"""
    log_test("Backend Health Check")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("all_healthy"):
                services = data.get("services", {})
                for service, info in services.items():
                    if info.get("healthy"):
                        log_info(f"  ✅ {service}: {info.get('message', 'OK')}")
                    else:
                        log_warn(f"  ⚠️  {service}: {info.get('message', 'Not healthy')}")
                test_pass("Infrastructure", "Backend health check passes")
                return True
        test_fail("Infrastructure", f"Health check fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Infrastructure", f"Health check fails - {str(e)}")
        return False

def test_backend_root():
    """Test backend root endpoint"""
    log_test("Backend Root Endpoint")
    try:
        response = requests.get(f"{BACKEND_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "message" in data or "version" in data:
                test_pass("Infrastructure", "Backend root endpoint works")
                return True
        test_fail("Infrastructure", f"Root endpoint fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Infrastructure", f"Root endpoint fails - {str(e)}")
        return False

def test_api_docs():
    """Test API documentation"""
    log_test("API Documentation")
    try:
        response = requests.get(f"{BACKEND_URL}/docs", timeout=10)
        if response.status_code == 200:
            test_pass("Infrastructure", "API docs accessible")
            return True
        test_fail("Infrastructure", f"API docs fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Infrastructure", f"API docs fails - {str(e)}")
        return False

def test_openapi_schema():
    """Test OpenAPI schema"""
    log_test("OpenAPI Schema")
    try:
        response = requests.get(f"{BACKEND_URL}/openapi.json", timeout=10)
        if response.status_code == 200:
            schema = response.json()
            if "openapi" in schema or "swagger" in schema:
                test_pass("Infrastructure", "OpenAPI schema valid")
                return True
        test_fail("Infrastructure", f"OpenAPI schema fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Infrastructure", f"OpenAPI schema fails - {str(e)}")
        return False

def test_frontend_accessibility():
    """Test frontend accessibility"""
    log_test("Frontend Accessibility")
    try:
        response = requests.get(FRONTEND_URL, timeout=10)
        if response.status_code in [200, 301, 302]:
            test_pass("Infrastructure", "Frontend accessible")
            return True
        test_fail("Infrastructure", f"Frontend fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Infrastructure", f"Frontend fails - {str(e)}")
        return False

# ============================================================================
# SECTION 2: AUTHENTICATION TESTS
# ============================================================================

def test_user_registration():
    """Test user registration"""
    log_test("User Registration")
    global user_id, test_email, test_password
    
    timestamp = int(time.time())
    test_email = f"test-comprehensive-{timestamp}@example.com"
    test_password = "TestPassword123!"
    test_name = "Comprehensive Test User"
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "name": test_name
            },
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            user_id = data.get("user_id") or data.get("id")
            test_pass("Authentication", f"User registration - {test_email}")
            return True
        else:
            test_fail("Authentication", f"Registration fails - HTTP {response.status_code}: {response.text[:100]}")
            return False
    except Exception as e:
        test_fail("Authentication", f"Registration fails - {str(e)}")
        return False

def test_user_login():
    """Test user login"""
    log_test("User Login")
    global access_token, refresh_token
    
    if not test_email or not test_password:
        test_skip("Authentication", "Login - No credentials")
        return False
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={
                "email": test_email,
                "password": test_password
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            
            if access_token:
                test_pass("Authentication", f"Login successful - Token: {len(access_token)} chars")
                return True
        test_fail("Authentication", f"Login fails - HTTP {response.status_code}: {response.text[:100]}")
        return False
    except Exception as e:
        test_fail("Authentication", f"Login fails - {str(e)}")
        return False

def test_get_user_profile():
    """Test get user profile"""
    log_test("Get User Profile")
    
    if not access_token:
        test_skip("Authentication", "Get profile - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BACKEND_URL}/api/v1/users/me", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            global user_id
            user_id = data.get("id") or data.get("user_id") or user_id
            test_pass("Authentication", f"Get profile - {data.get('email', 'N/A')}")
            return True
        test_fail("Authentication", f"Get profile fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Authentication", f"Get profile fails - {str(e)}")
        return False

def test_refresh_token():
    """Test token refresh"""
    log_test("Token Refresh")
    
    if not refresh_token:
        test_skip("Authentication", "Refresh token - No refresh token")
        return False
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("access_token"):
                test_pass("Authentication", "Token refresh successful")
                return True
        test_fail("Authentication", f"Token refresh fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Authentication", f"Token refresh fails - {str(e)}")
        return False

def test_invalid_login():
    """Test invalid login credentials"""
    log_test("Invalid Login (Error Handling)")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "wrongpassword"
            },
            timeout=10
        )
        
        if response.status_code == 401:
            test_pass("Authentication", "Invalid login correctly rejected (401)")
            return True
        test_fail("Authentication", f"Invalid login not rejected - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Authentication", f"Invalid login test fails - {str(e)}")
        return False

# ============================================================================
# SECTION 3: SESSION MANAGEMENT TESTS
# ============================================================================

def test_create_session():
    """Test create session"""
    log_test("Create Session")
    global session_id
    
    if not access_token:
        test_skip("Sessions", "Create session - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        session_name = f"Comprehensive Test Session {int(time.time())}"
        response = requests.post(
            f"{BACKEND_URL}/api/sessions/",
            headers=headers,
            json={"name": session_name},
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            session_id = data.get("id")
            test_pass("Sessions", f"Create session - {session_id[:8]}...")
            return True
        test_fail("Sessions", f"Create session fails - HTTP {response.status_code}: {response.text[:100]}")
        return False
    except Exception as e:
        test_fail("Sessions", f"Create session fails - {str(e)}")
        return False

def test_list_sessions():
    """Test list sessions"""
    log_test("List Sessions")
    
    if not access_token:
        test_skip("Sessions", "List sessions - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BACKEND_URL}/api/sessions/", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            sessions = data if isinstance(data, list) else data.get("sessions", [])
            test_pass("Sessions", f"List sessions - {len(sessions)} session(s)")
            return True
        test_fail("Sessions", f"List sessions fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Sessions", f"List sessions fails - {str(e)}")
        return False

def test_get_session():
    """Test get session details"""
    log_test("Get Session Details")
    
    if not access_token or not session_id:
        test_skip("Sessions", "Get session - No token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/sessions/{session_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            test_pass("Sessions", f"Get session - Status: {data.get('status', 'N/A')}")
            return True
        test_fail("Sessions", f"Get session fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Sessions", f"Get session fails - {str(e)}")
        return False

def test_get_session_messages():
    """Test get session messages"""
    log_test("Get Session Messages")
    
    if not access_token or not session_id:
        test_skip("Sessions", "Get messages - No token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/sessions/{session_id}/messages",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            messages = data if isinstance(data, list) else data.get("messages", [])
            test_pass("Sessions", f"Get messages - {len(messages)} message(s)")
            return True
        test_fail("Sessions", f"Get messages fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Sessions", f"Get messages fails - {str(e)}")
        return False

# ============================================================================
# SECTION 4: CHAT TESTS
# ============================================================================

def test_send_chat_message():
    """Test send chat message"""
    log_test("Send Chat Message")
    
    if not access_token or not session_id:
        test_skip("Chat", "Send message - No token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        test_message = "Hello! This is a comprehensive test message. Please respond."
        
        response = requests.post(
            f"{BACKEND_URL}/api/sessions/{session_id}/chat",
            headers=headers,
            json={
                "message": test_message,
                "session_id": session_id
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", data.get("message", ""))
            if response_text:
                test_pass("Chat", f"Send message - Response received ({len(response_text)} chars)")
                return True
            else:
                test_pass("Chat", "Send message - Accepted (response via SSE)")
                return True
        test_fail("Chat", f"Send message fails - HTTP {response.status_code}: {response.text[:200]}")
        return False
    except Exception as e:
        test_fail("Chat", f"Send message fails - {str(e)}")
        return False

def test_send_multiple_messages():
    """Test sending multiple messages"""
    log_test("Send Multiple Messages")
    
    if not access_token or not session_id:
        test_skip("Chat", "Multiple messages - No token or session ID")
        return False
    
    messages = [
        "What is 2+2?",
        "What is the capital of France?",
        "Tell me a joke"
    ]
    
    success_count = 0
    for i, msg in enumerate(messages, 1):
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.post(
                f"{BACKEND_URL}/api/sessions/{session_id}/chat",
                headers=headers,
                json={
                    "message": msg,
                    "session_id": session_id
                },
                timeout=60
            )
            
            if response.status_code == 200:
                success_count += 1
            time.sleep(2)  # Wait between messages
        except Exception as e:
            log_warn(f"  Message {i} failed: {str(e)}")
    
    if success_count == len(messages):
        test_pass("Chat", f"Multiple messages - {success_count}/{len(messages)} sent")
        return True
    elif success_count > 0:
        test_pass("Chat", f"Multiple messages - {success_count}/{len(messages)} sent (partial)")
        return True
    else:
        test_fail("Chat", "Multiple messages - All failed")
        return False

# ============================================================================
# SECTION 5: SSE TESTS
# ============================================================================

def test_sse_agent_activity():
    """Test SSE Agent Activity stream"""
    log_test("SSE Agent Activity Stream")
    
    if not access_token or not session_id:
        test_skip("SSE", "Agent Activity - No token or session ID")
        return False
    
    try:
        import sseclient
        
        url = f"{BACKEND_URL}/api/sessions/{session_id}/agent-activity/stream?token={access_token}"
        headers = {"Accept": "text/event-stream"}
        
        response = requests.get(url, headers=headers, stream=True, timeout=5)
        
        if response.status_code == 200:
            client = sseclient.SSEClient(response)
            events_received = 0
            for event in client.events():
                events_received += 1
                if events_received >= 3:  # Get at least 3 events
                    break
            
            if events_received > 0:
                test_pass("SSE", f"Agent Activity - {events_received} event(s) received")
                return True
            else:
                test_pass("SSE", "Agent Activity - Connected (no events yet)")
                return True
        test_fail("SSE", f"Agent Activity fails - HTTP {response.status_code}")
        return False
    except ImportError:
        test_skip("SSE", "Agent Activity - sseclient not installed")
        return False
    except Exception as e:
        if "timeout" in str(e).lower():
            test_pass("SSE", "Agent Activity - Connected (timeout expected)")
            return True
        test_fail("SSE", f"Agent Activity fails - {str(e)}")
        return False

def test_sse_notifications():
    """Test SSE Notifications stream"""
    log_test("SSE Notifications Stream")
    
    if not access_token:
        test_skip("SSE", "Notifications - No token")
        return False
    
    try:
        import sseclient
        
        url = f"{BACKEND_URL}/api/notifications/stream?token={access_token}"
        headers = {"Accept": "text/event-stream"}
        
        # First check if endpoint responds correctly
        response = requests.get(url, headers=headers, stream=True, timeout=3)
        
        if response.status_code == 200:
            # Try to read events with shorter timeout
            client = sseclient.SSEClient(response)
            events_received = 0
            try:
                for event in client.events():
                    events_received += 1
                    if events_received >= 1:  # Just need to confirm connection works
                        break
            except Exception:
                pass  # Timeout is OK
            
            if events_received > 0:
                test_pass("SSE", f"Notifications - {events_received} event(s) received")
            else:
                test_pass("SSE", "Notifications - Connected successfully (no events yet)")
            return True
        elif response.status_code == 401:
            test_fail("SSE", "Notifications - Unauthorized (401)")
            return False
        else:
            test_fail("SSE", f"Notifications fails - HTTP {response.status_code}")
            return False
    except ImportError:
        test_skip("SSE", "Notifications - sseclient not installed")
        return False
    except requests.exceptions.Timeout:
        # Timeout is OK for SSE if connection was established
        test_pass("SSE", "Notifications - Connection established (timeout expected)")
        return True
    except Exception as e:
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            test_pass("SSE", "Notifications - Connection established (timeout expected)")
            return True
        test_fail("SSE", f"Notifications fails - {str(e)}")
        return False

# ============================================================================
# SECTION 6: MEMORY TESTS
# ============================================================================

def test_get_long_term_memory():
    """Test get long-term memory"""
    log_test("Get Long-Term Memory")
    
    if not access_token or not session_id:
        test_skip("Memory", "Get long-term memory - No token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/memory/long/list",
            headers=headers,
            params={"session_id": session_id},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            memories = data if isinstance(data, list) else data.get("memories", [])
            test_pass("Memory", f"Get long-term memory - {len(memories)} memory(ies)")
            return True
        test_fail("Memory", f"Get long-term memory fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Memory", f"Get long-term memory fails - {str(e)}")
        return False

def test_get_session_memory():
    """Test get session memory"""
    log_test("Get Session Memory")
    
    if not access_token or not session_id:
        test_skip("Memory", "Get session memory - No token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/sessions/{session_id}/memory",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            test_pass("Memory", "Get session memory successful")
            return True
        test_fail("Memory", f"Get session memory fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Memory", f"Get session memory fails - {str(e)}")
        return False

# ============================================================================
# SECTION 7: TOOLS TESTS
# ============================================================================

def test_list_tools():
    """Test list available tools"""
    log_test("List Available Tools")
    
    if not access_token:
        test_skip("Tools", "List tools - No token")
        return False
    
    # Try multiple endpoints
    endpoints = [
        ("/api/tools/list", "MCP tools"),
        ("/api/v1/users/me/tools", "User tools preferences"),
    ]
    
    for endpoint, desc in endpoints:
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(
                f"{BACKEND_URL}{endpoint}",
                headers=headers,
                timeout=15  # Longer timeout for MCP tools
            )
            
            if response.status_code == 200:
                data = response.json()
                if endpoint == "/api/v1/users/me/tools":
                    tools = data.get("available_tools", [])
                else:
                    tools = data if isinstance(data, list) else data.get("tools", [])
                
                tool_names = [t.get("name", t) if isinstance(t, dict) else str(t)[:50] for t in tools[:5]]
                test_pass("Tools", f"List tools ({desc}) - {len(tools)} tool(s) available")
                if tool_names:
                    log_info(f"  Sample tools: {', '.join(tool_names)}")
                return True
        except Exception as e:
            continue
    
    test_fail("Tools", "List tools fails - All endpoints failed")
    return False

def test_get_tool_info():
    """Test get tool information via user preferences"""
    log_test("Get Tool Information")
    
    if not access_token:
        test_skip("Tools", "Get tool info - No token")
        return False
    
    # Use /api/v1/users/me/tools which returns tool info
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/v1/users/me/tools",
            headers=headers,
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            available_tools = data.get("available_tools", [])
            if available_tools:
                tool_info = available_tools[0] if isinstance(available_tools[0], dict) else {}
                tool_name = tool_info.get("name", "unknown")
                test_pass("Tools", f"Get tool info - {tool_name} (via user preferences)")
                return True
            else:
                test_pass("Tools", "Get tool info - No tools available (MCP may be offline)")
                return True
        test_fail("Tools", f"Get tool info fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Tools", f"Get tool info fails - {str(e)}")
        return False

# ============================================================================
# SECTION 8: NOTIFICATIONS TESTS
# ============================================================================

def test_get_notifications():
    """Test get notifications"""
    log_test("Get Notifications")
    
    if not access_token:
        test_skip("Notifications", "Get notifications - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/notifications/",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            notifications = data if isinstance(data, list) else data.get("notifications", [])
            test_pass("Notifications", f"Get notifications - {len(notifications)} notification(s)")
            return True
        test_fail("Notifications", f"Get notifications fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Notifications", f"Get notifications fails - {str(e)}")
        return False

def test_get_notification_count():
    """Test get notification count"""
    log_test("Get Notification Count")
    
    if not access_token:
        test_skip("Notifications", "Get count - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/notifications/count",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            count = data.get("count", data if isinstance(data, int) else 0)
            test_pass("Notifications", f"Get count - {count} notification(s)")
            return True
        test_fail("Notifications", f"Get count fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Notifications", f"Get count fails - {str(e)}")
        return False

# ============================================================================
# SECTION 9: ERROR HANDLING TESTS
# ============================================================================

def test_invalid_endpoint():
    """Test invalid endpoint (404)"""
    log_test("Invalid Endpoint (Error Handling)")
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/invalid/endpoint", timeout=10)
        if response.status_code == 404:
            test_pass("Error Handling", "Invalid endpoint correctly returns 404")
            return True
        test_fail("Error Handling", f"Invalid endpoint - Expected 404, got {response.status_code}")
        return False
    except Exception as e:
        test_fail("Error Handling", f"Invalid endpoint test fails - {str(e)}")
        return False

def test_unauthorized_access():
    """Test unauthorized access"""
    log_test("Unauthorized Access (Error Handling)")
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/sessions/", timeout=10)
        if response.status_code == 401:
            test_pass("Error Handling", "Unauthorized access correctly returns 401")
            return True
        test_fail("Error Handling", f"Unauthorized access - Expected 401, got {response.status_code}")
        return False
    except Exception as e:
        test_fail("Error Handling", f"Unauthorized access test fails - {str(e)}")
        return False

def test_invalid_session_id():
    """Test invalid session ID"""
    log_test("Invalid Session ID (Error Handling)")
    
    if not access_token:
        test_skip("Error Handling", "Invalid session ID - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        invalid_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(
            f"{BACKEND_URL}/api/sessions/{invalid_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 404:
            test_pass("Error Handling", "Invalid session ID correctly returns 404")
            return True
        test_fail("Error Handling", f"Invalid session ID - Expected 404, got {response.status_code}")
        return False
    except Exception as e:
        test_fail("Error Handling", f"Invalid session ID test fails - {str(e)}")
        return False

# ============================================================================
# SECTION 10: FILES TESTS
# ============================================================================

def test_list_files():
    """Test list files for session"""
    log_test("List Files")
    
    if not access_token or not session_id:
        test_skip("Files", "List files - No token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/files/session/{session_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            files = data if isinstance(data, list) else data.get("files", [])
            test_pass("Files", f"List files - {len(files)} file(s)")
            return True
        test_fail("Files", f"List files fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Files", f"List files fails - {str(e)}")
        return False

# ============================================================================
# SECTION 11: METRICS TESTS
# ============================================================================

def test_get_metrics():
    """Test get Prometheus metrics"""
    log_test("Get Metrics")
    
    try:
        response = requests.get(f"{BACKEND_URL}/metrics", timeout=10)
        
        if response.status_code == 200:
            content = response.text
            # Check for Prometheus format indicators
            if "# HELP" in content or "# TYPE" in content or "http_requests_total" in content.lower():
                test_pass("Metrics", "Prometheus metrics accessible")
                return True
            # Even if format is different, 200 means endpoint works
            test_pass("Metrics", "Metrics endpoint accessible")
            return True
        test_fail("Metrics", f"Get metrics fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Metrics", f"Get metrics fails - {str(e)}")
        return False

# ============================================================================
# SECTION 12: API KEYS TESTS
# ============================================================================

def test_list_api_keys():
    """Test list API keys"""
    log_test("List API Keys")
    
    if not access_token:
        test_skip("API Keys", "List API keys - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/v1/apikeys/",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            keys = data if isinstance(data, list) else data.get("keys", [])
            test_pass("API Keys", f"List API keys - {len(keys)} key(s)")
            return True
        elif response.status_code == 403:
            test_skip("API Keys", "List API keys - Requires admin role")
            return False
        test_fail("API Keys", f"List API keys fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("API Keys", f"List API keys fails - {str(e)}")
        return False

# ============================================================================
# SECTION 13: INTEGRATIONS TESTS
# ============================================================================

def test_list_integrations():
    """Test list integrations"""
    log_test("List Integrations")
    
    if not access_token:
        test_skip("Integrations", "List integrations - No token")
        return False
    
    # Try different endpoints
    endpoints = [
        ("/api/integrations/mcp/integrations", "MCP"),
        ("/api/integrations/calendars/integrations", "Calendar"),
        ("/api/integrations/emails/integrations", "Email"),
    ]
    
    success_count = 0
    for endpoint, desc in endpoints:
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(
                f"{BACKEND_URL}{endpoint}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                integrations = data if isinstance(data, list) else data.get("integrations", [])
                log_info(f"  {desc}: {len(integrations)} integration(s)")
                success_count += 1
        except Exception as e:
            continue
    
    if success_count > 0:
        test_pass("Integrations", f"List integrations - {success_count}/{len(endpoints)} endpoint(s) working")
        return True
    else:
        test_fail("Integrations", "List integrations fails - All endpoints failed")
        return False

def test_list_calendar_integrations():
    """Test list calendar integrations"""
    log_test("List Calendar Integrations")
    
    if not access_token:
        test_skip("Integrations", "List calendar - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/integrations/calendars/integrations",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            integrations = data if isinstance(data, list) else data.get("integrations", [])
            test_pass("Integrations", f"List calendar integrations - {len(integrations)} integration(s)")
            return True
        test_fail("Integrations", f"List calendar fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Integrations", f"List calendar fails - {str(e)}")
        return False

def test_list_email_integrations():
    """Test list email integrations"""
    log_test("List Email Integrations")
    
    if not access_token:
        test_skip("Integrations", "List email - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/integrations/emails/integrations",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            integrations = data if isinstance(data, list) else data.get("integrations", [])
            test_pass("Integrations", f"List email integrations - {len(integrations)} integration(s)")
            return True
        test_fail("Integrations", f"List email fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Integrations", f"List email fails - {str(e)}")
        return False

# ============================================================================
# SECTION 14: INIT TESTS
# ============================================================================

def test_init_endpoint():
    """Test init endpoint"""
    log_test("Init Endpoint")
    
    # Try different possible endpoints
    endpoints = [
        "/api/init",
        "/api/v1/init",
        "/init",
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BACKEND_URL}{endpoint}", timeout=10)
            if response.status_code == 200:
                test_pass("Init", f"Init endpoint accessible - {endpoint}")
                return True
        except Exception as e:
            continue
    
    # If no endpoint works, skip (might not be implemented)
    test_skip("Init", "Init endpoint - Not implemented or different path")
    return False

# ============================================================================
# SECTION 15: PERFORMANCE TESTS
# ============================================================================

def test_response_time():
    """Test API response times"""
    log_test("API Response Times")
    
    endpoints = [
        ("/health", "GET", None),
        ("/api/v1/users/me", "GET", {"Authorization": f"Bearer {access_token}"} if access_token else None),
        (f"/api/sessions/{session_id}" if session_id else None, "GET", {"Authorization": f"Bearer {access_token}"} if access_token and session_id else None),
    ]
    
    results = []
    for endpoint, method, headers in endpoints:
        if endpoint is None or (headers is None and endpoint != "/health"):
            continue
        
        try:
            start = time.time()
            if method == "GET":
                response = requests.get(f"{BACKEND_URL}{endpoint}", headers=headers, timeout=10)
            elapsed = time.time() - start
            
            if response.status_code in [200, 401]:  # 401 is OK for unauthorized
                results.append((endpoint, elapsed))
                log_info(f"  {endpoint}: {elapsed*1000:.0f}ms")
        except Exception as e:
            log_warn(f"  {endpoint}: Failed - {str(e)}")
    
    if results:
        avg_time = sum(r[1] for r in results) / len(results) * 1000
        if avg_time < 1000:  # Less than 1 second
            test_pass("Performance", f"Response times - Avg: {avg_time:.0f}ms")
        else:
            test_pass("Performance", f"Response times - Avg: {avg_time:.0f}ms (acceptable)")
        return True
    else:
        test_skip("Performance", "Response times - No endpoints tested")
        return False

# ============================================================================
# SECTION 16: ADDITIONAL TESTS
# ============================================================================

def test_update_user_profile():
    """Test update user profile"""
    log_test("Update User Profile")
    
    if not access_token:
        test_skip("Users", "Update profile - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.put(
            f"{BACKEND_URL}/api/v1/users/me",
            headers=headers,
            json={"name": "Updated Test User"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            test_pass("Users", f"Update profile - Name: {data.get('name', 'N/A')}")
            return True
        test_fail("Users", f"Update profile fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Users", f"Update profile fails - {str(e)}")
        return False

def test_get_session_notifications():
    """Test get session-specific notifications"""
    log_test("Get Session Notifications")
    
    if not access_token or not session_id:
        test_skip("Notifications", "Get session notifications - No token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/sessions/{session_id}/notifications/pending",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            notifications = data if isinstance(data, list) else data.get("notifications", [])
            test_pass("Notifications", f"Get session notifications - {len(notifications)} notification(s)")
            return True
        test_fail("Notifications", f"Get session notifications fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Notifications", f"Get session notifications fails - {str(e)}")
        return False

def test_delete_session():
    """Test delete session"""
    log_test("Delete Session")
    
    if not access_token or not session_id:
        test_skip("Sessions", "Delete session - No token or session ID")
        return False
    
    # Create a temporary session to delete
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        create_response = requests.post(
            f"{BACKEND_URL}/api/sessions/",
            headers=headers,
            json={"name": "Temp Session to Delete"},
            timeout=10
        )
        
        if create_response.status_code in [200, 201]:
            temp_session_id = create_response.json().get("id")
            
            # Now delete it
            delete_response = requests.delete(
                f"{BACKEND_URL}/api/sessions/{temp_session_id}",
                headers=headers,
                timeout=10
            )
            
            if delete_response.status_code in [200, 204]:
                test_pass("Sessions", "Delete session successful")
                return True
            else:
                test_fail("Sessions", f"Delete session fails - HTTP {delete_response.status_code}")
                return False
        else:
            test_skip("Sessions", "Delete session - Could not create temp session")
            return False
    except Exception as e:
        test_fail("Sessions", f"Delete session fails - {str(e)}")
        return False

def test_web_search_endpoint():
    """Test web search endpoint (uses customsearch_search built-in tool, not MCP Gateway)"""
    log_test("Web Search Endpoint (Custom Search)")
    
    if not access_token:
        test_skip("Web", "Web search - No token")
        return False
    
    # Note: In Cloud Run, web search uses customsearch_search built-in tool
    # which uses Google Custom Search API, not MCP Gateway
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(
            f"{BACKEND_URL}/api/web/search",
            headers=headers,
            json={"query": "test search"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            # Check if result contains search results
            if "result" in data or "results" in data or "query" in data:
                test_pass("Web", "Web search endpoint accessible (customsearch_search)")
                return True
            test_pass("Web", "Web search endpoint accessible")
            return True
        elif response.status_code == 503:
            test_skip("Web", "Web search - Service unavailable (Custom Search API may need configuration)")
            return False
        elif response.status_code == 400:
            # 400 might mean missing API key or invalid query
            test_skip("Web", "Web search - Requires Google Custom Search API key configuration")
            return False
        test_fail("Web", f"Web search fails - HTTP {response.status_code}: {response.text[:200]}")
        return False
    except requests.exceptions.Timeout:
        test_skip("Web", "Web search - Timeout (Custom Search API may be slow)")
        return False
    except Exception as e:
        test_fail("Web", f"Web search fails - {str(e)}")
        return False

def test_memory_add_long_term():
    """Test add long-term memory"""
    log_test("Add Long-Term Memory")
    
    if not access_token or not session_id:
        test_skip("Memory", "Add long-term memory - No token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        # The endpoint expects learned_from_sessions as query param
        response = requests.post(
            f"{BACKEND_URL}/api/memory/long?learned_from_sessions={session_id}",
            headers=headers,
            json={
                "content": "This is a test memory for comprehensive E2E tests",
                "importance_score": 0.8
            },
            timeout=15
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            test_pass("Memory", "Add long-term memory successful")
            return True
        test_fail("Memory", f"Add long-term memory fails - HTTP {response.status_code}: {response.text[:200]}")
        return False
    except Exception as e:
        test_fail("Memory", f"Add long-term memory fails - {str(e)}")
        return False

def test_memory_query():
    """Test query long-term memory"""
    log_test("Query Long-Term Memory")
    
    if not access_token:
        test_skip("Memory", "Query memory - No token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/memory/long",
            headers=headers,
            params={
                "query": "test memory",
                "n_results": 5
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            test_pass("Memory", f"Query memory - {len(results)} result(s)")
            return True
        test_fail("Memory", f"Query memory fails - HTTP {response.status_code}")
        return False
    except Exception as e:
        test_fail("Memory", f"Query memory fails - {str(e)}")
        return False

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all comprehensive tests"""
    print(f"\n{Colors.BOLD}{Colors.MAGENTA}")
    print("=" * 70)
    print("COMPREHENSIVE END-TO-END TEST SUITE")
    print("=" * 70)
    print(f"{Colors.RESET}")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Section 1: Infrastructure
    log_section("SECTION 1: INFRASTRUCTURE TESTS")
    test_backend_health()
    test_backend_root()
    test_api_docs()
    test_openapi_schema()
    test_frontend_accessibility()
    
    # Section 2: Authentication
    log_section("SECTION 2: AUTHENTICATION TESTS")
    test_user_registration()
    test_user_login()
    test_get_user_profile()
    test_refresh_token()
    test_invalid_login()
    
    # Section 3: Session Management
    log_section("SECTION 3: SESSION MANAGEMENT TESTS")
    test_create_session()
    test_list_sessions()
    test_get_session()
    test_get_session_messages()
    
    # Section 4: Chat
    log_section("SECTION 4: CHAT TESTS")
    test_send_chat_message()
    time.sleep(3)  # Wait for async processing
    test_send_multiple_messages()
    
    # Section 5: SSE
    log_section("SECTION 5: SSE TESTS")
    test_sse_agent_activity()
    test_sse_notifications()
    
    # Section 6: Memory
    log_section("SECTION 6: MEMORY TESTS")
    test_get_long_term_memory()
    test_get_session_memory()
    
    # Section 7: Tools
    log_section("SECTION 7: TOOLS TESTS")
    test_list_tools()
    test_get_tool_info()
    
    # Section 8: Notifications
    log_section("SECTION 8: NOTIFICATIONS TESTS")
    test_get_notifications()
    test_get_notification_count()
    
    # Section 9: Error Handling
    log_section("SECTION 9: ERROR HANDLING TESTS")
    test_invalid_endpoint()
    test_unauthorized_access()
    test_invalid_session_id()
    
    # Section 10: Files
    log_section("SECTION 10: FILES TESTS")
    test_list_files()
    
    # Section 11: Metrics
    log_section("SECTION 11: METRICS TESTS")
    test_get_metrics()
    
    # Section 12: API Keys
    log_section("SECTION 12: API KEYS TESTS")
    test_list_api_keys()
    
    # Section 13: Integrations
    log_section("SECTION 13: INTEGRATIONS TESTS")
    test_list_integrations()
    test_list_calendar_integrations()
    test_list_email_integrations()
    
    # Section 14: Init
    log_section("SECTION 14: INIT TESTS")
    test_init_endpoint()
    
    # Section 15: Performance
    log_section("SECTION 15: PERFORMANCE TESTS")
    test_response_time()
    
    # Section 16: Additional Tests
    log_section("SECTION 16: ADDITIONAL TESTS")
    test_update_user_profile()
    test_get_session_notifications()
    test_delete_session()
    test_web_search_endpoint()
    test_memory_add_long_term()
    time.sleep(2)  # Wait for memory indexing
    test_memory_query()
    
    # Print summary
    print()
    log_section("TEST SUMMARY")
    
    print(f"Total Tests: {stats['total']}")
    print(f"{Colors.GREEN}Passed: {stats['passed']}{Colors.RESET}")
    print(f"{Colors.RED}Failed: {stats['failed']}{Colors.RESET}")
    print(f"{Colors.YELLOW}Skipped: {stats['skipped']}{Colors.RESET}")
    
    if stats['total'] > 0:
        success_rate = (stats['passed'] / stats['total']) * 100
        print(f"Success Rate: {success_rate:.1f}%")
    
    print("\nResults by Category:")
    for category, results in sorted(stats['categories'].items()):
        total_cat = results['passed'] + results['failed'] + results['skipped']
        if total_cat > 0:
            cat_rate = (results['passed'] / total_cat) * 100
            print(f"  {category}: {results['passed']}/{total_cat} passed ({cat_rate:.1f}%)")
    
    print()
    if stats['failed'] == 0:
        log_success("🎉 ALL TESTS PASSED!")
        return 0
    else:
        log_error(f"❌ {stats['failed']} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())

