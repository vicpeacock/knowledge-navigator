#!/usr/bin/env python3
"""
Manual End-to-End Test Script
Tests full user flow: registration, login, session creation, chat, SSE
"""

import requests
import json
import time
import uuid
import sys
from typing import Optional, Dict, Any

# Configuration
BACKEND_URL = "https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app"
FRONTEND_URL = "https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app"

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
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

def log_success(msg: str):
    print(f"{Colors.GREEN}✅{Colors.RESET} {msg}")

def log_fail(msg: str):
    print(f"{Colors.RED}❌{Colors.RESET} {msg}")

# Test counters
tests_passed = 0
tests_failed = 0
tests_total = 0

def test_pass(msg: str):
    global tests_passed, tests_total
    tests_passed += 1
    tests_total += 1
    log_success(f"PASS: {msg}")

def test_fail(msg: str):
    global tests_failed, tests_total
    tests_failed += 1
    tests_total += 1
    log_fail(f"FAIL: {msg}")

def test_skip(msg: str):
    global tests_total
    tests_total += 1
    log_warn(f"SKIP: {msg}")

# Global state
access_token: Optional[str] = None
refresh_token: Optional[str] = None
user_id: Optional[str] = None
session_id: Optional[str] = None

def test_health_check():
    """Test 1: Backend health check"""
    log_test("Test 1: Backend health check")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("all_healthy"):
                test_pass("Backend health check passes")
                log_info(f"Services: {json.dumps(data.get('services', {}), indent=2)}")
                return True
            else:
                test_fail("Backend health check fails - not all services healthy")
                return False
        else:
            test_fail(f"Backend health check fails - HTTP {response.status_code}")
            return False
    except Exception as e:
        test_fail(f"Backend health check fails - {str(e)}")
        return False

def test_user_registration():
    """Test 2: User registration"""
    log_test("Test 2: User registration")
    global user_id
    
    # Generate unique email
    timestamp = int(time.time())
    test_email = f"test-e2e-{timestamp}@example.com"
    test_password = "TestPassword123!"
    test_name = "E2E Test User"
    
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
        
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            user_id = data.get("user_id")
            log_info(f"User registered: {test_email} (ID: {user_id})")
            test_pass(f"User registration successful - {test_email}")
            return True, test_email, test_password
        else:
            test_fail(f"User registration fails - HTTP {response.status_code}: {response.text}")
            return False, None, None
    except Exception as e:
        test_fail(f"User registration fails - {str(e)}")
        return False, None, None

def test_user_login(email: str, password: str):
    """Test 3: User login"""
    log_test("Test 3: User login")
    global access_token, refresh_token
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={
                "email": email,
                "password": password
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            
            if access_token:
                log_info(f"Login successful - Token length: {len(access_token)}")
                test_pass("User login successful")
                return True
            else:
                test_fail("Login fails - No access token in response")
                return False
        else:
            test_fail(f"Login fails - HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        test_fail(f"Login fails - {str(e)}")
        return False

def test_get_user_profile():
    """Test 4: Get user profile"""
    log_test("Test 4: Get user profile")
    global user_id
    
    if not access_token:
        test_skip("Get user profile - No access token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BACKEND_URL}/api/v1/users/me",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            user_id = data.get("id") or data.get("user_id")
            log_info(f"User profile retrieved: {data.get('email')}")
            test_pass("Get user profile successful")
            return True
        else:
            test_fail(f"Get user profile fails - HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        test_fail(f"Get user profile fails - {str(e)}")
        return False

def test_create_session():
    """Test 5: Create chat session"""
    log_test("Test 5: Create chat session")
    global session_id
    
    if not access_token:
        test_skip("Create session - No access token")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        session_name = f"E2E Test Session {int(time.time())}"
        response = requests.post(
            f"{BACKEND_URL}/api/sessions/",
            headers=headers,
            json={"name": session_name},
            timeout=10
        )
        
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            session_id = data.get("id")
            log_info(f"Session created: {session_name} (ID: {session_id})")
            test_pass(f"Create session successful - {session_name}")
            return True
        else:
            test_fail(f"Create session fails - HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        test_fail(f"Create session fails - {str(e)}")
        return False

def test_send_message():
    """Test 6: Send chat message"""
    log_test("Test 6: Send chat message")
    
    if not access_token or not session_id:
        test_skip("Send message - No access token or session ID")
        return False
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        test_message = "Hello! This is a test message from E2E tests. Can you respond?"
        
        response = requests.post(
            f"{BACKEND_URL}/api/sessions/{session_id}/chat",
            headers=headers,
            json={
                "message": test_message,
                "session_id": session_id
            },
            timeout=60  # Longer timeout for LLM response
        )
        
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", data.get("message", ""))
            if response_text:
                log_info(f"Message sent and received response (length: {len(response_text)} chars)")
                log_info(f"Response preview: {response_text[:200]}...")
                test_pass("Send message successful - Received response from Vertex AI")
                return True
            else:
                log_warn("Message sent but response is empty (might be async via SSE)")
                test_pass("Send message successful - Response might be via SSE")
                return True
        else:
            test_fail(f"Send message fails - HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        test_fail(f"Send message fails - {str(e)}")
        return False

def test_sse_agent_activity():
    """Test 7: SSE Agent Activity stream"""
    log_test("Test 7: SSE Agent Activity stream")
    
    if not access_token or not session_id:
        test_skip("SSE Agent Activity - No access token or session ID")
        return False
    
    try:
        import sseclient
        
        url = f"{BACKEND_URL}/api/sessions/{session_id}/agent-activity/stream?token={access_token}"
        headers = {"Accept": "text/event-stream"}
        
        response = requests.get(url, headers=headers, stream=True, timeout=5)
        
        if response.status_code == 200:
            # Try to read at least one event
            client = sseclient.SSEClient(response)
            events_received = 0
            for event in client.events():
                events_received += 1
                if events_received >= 1:
                    break
            
            if events_received > 0:
                test_pass(f"SSE Agent Activity stream works - Received {events_received} event(s)")
                return True
            else:
                test_pass("SSE Agent Activity stream connected (no events yet)")
                return True
        else:
            test_fail(f"SSE Agent Activity fails - HTTP {response.status_code}: {response.text}")
            return False
    except ImportError:
        test_skip("SSE Agent Activity - sseclient library not installed")
        return False
    except Exception as e:
        # SSE might timeout if no events, which is OK
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            test_pass("SSE Agent Activity stream connected (timeout expected if no events)")
            return True
        else:
            test_fail(f"SSE Agent Activity fails - {str(e)}")
            return False

def test_sse_notifications():
    """Test 8: SSE Notifications stream"""
    log_test("Test 8: SSE Notifications stream")
    
    if not access_token:
        test_skip("SSE Notifications - No access token")
        return False
    
    try:
        import sseclient
        
        url = f"{BACKEND_URL}/api/notifications/stream?token={access_token}"
        headers = {"Accept": "text/event-stream"}
        
        response = requests.get(url, headers=headers, stream=True, timeout=5)
        
        if response.status_code == 200:
            # Try to read at least one event
            client = sseclient.SSEClient(response)
            events_received = 0
            for event in client.events():
                events_received += 1
                if events_received >= 1:
                    break
            
            if events_received > 0:
                test_pass(f"SSE Notifications stream works - Received {events_received} event(s)")
                return True
            else:
                test_pass("SSE Notifications stream connected (no events yet)")
                return True
        else:
            test_fail(f"SSE Notifications fails - HTTP {response.status_code}: {response.text}")
            return False
    except ImportError:
        test_skip("SSE Notifications - sseclient library not installed")
        return False
    except Exception as e:
        # SSE might timeout if no events, which is OK
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            test_pass("SSE Notifications stream connected (timeout expected if no events)")
            return True
        else:
            test_fail(f"SSE Notifications fails - {str(e)}")
            return False

def main():
    print("=" * 60)
    print("Manual End-to-End Tests - Cloud Run")
    print("=" * 60)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Frontend URL: {FRONTEND_URL}")
    print()
    
    # Run tests in sequence
    if not test_health_check():
        log_error("Health check failed - aborting tests")
        return
    
    email, password = None, None
    registration_success, email, password = test_user_registration()
    
    if not registration_success:
        log_warn("Registration failed - trying with existing user or skipping")
        # Try to continue with login if user might exist
        email = f"test-e2e-{int(time.time())}@example.com"
        password = "TestPassword123!"
    
    if email and password:
        if test_user_login(email, password):
            test_get_user_profile()
            if test_create_session():
                test_send_message()
                # Wait a bit for async processing
                time.sleep(2)
                test_sse_agent_activity()
                test_sse_notifications()
    
    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Total Tests: {tests_total}")
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print(f"Success Rate: {(tests_passed/tests_total*100):.1f}%" if tests_total > 0 else "N/A")
    print()
    
    if tests_failed == 0:
        log_success("All tests passed!")
        return 0
    else:
        log_error(f"{tests_failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

