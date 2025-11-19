# Testing Guide - Knowledge Navigator

## Overview

This guide explains how to run tests for the Knowledge Navigator backend and frontend.

## Backend Tests

### Running All Tests

```bash
cd backend
./scripts/run_all_tests.sh
```

Or manually:

```bash
cd backend
pytest tests/ -v --tb=short
```

### Test Structure

Tests are organized in `backend/tests/`:

- **`test_proactivity.py`** - Unit tests for proactivity system (Email Poller, Calendar Watcher, Event Monitor)
- **`test_proactivity_e2e.py`** - End-to-end tests for proactivity system
- **`test_notification_service.py`** - Unit tests for NotificationService
- **`test_notification_api.py`** - Integration tests for notification API endpoints
- **`test_daily_session_integration.py`** - Integration tests for daily session management
- **`test_day_transition_api.py`** - API tests for day transition functionality
- **`test_email_auto_session.py`** - Tests for automatic session creation from emails
- **`test_langgraph_complete.py`** - Comprehensive tests for LangGraph nodes
- **`test_langgraph_node_execution.py`** - Tests for node execution order and telemetry
- **`test_langgraph_integration.py`** - Integration tests for complete LangGraph flow
- **`test_chat_endpoint.py`** - Tests for chat endpoint to ensure responses are never empty
- **`test_observability.py`** - Tests for observability features
- **`test_evaluation_*.py`** - Tests for evaluation framework

### Running Specific Test Files

```bash
# Test LangGraph
pytest backend/tests/test_langgraph_*.py -v

# Test proactivity
pytest backend/tests/test_proactivity*.py -v

# Test notifications
pytest backend/tests/test_notification*.py -v

# Test daily sessions
pytest backend/tests/test_daily_session*.py -v
pytest backend/tests/test_day_transition*.py -v
```

### Running Specific Tests

```bash
# Run a specific test function
pytest backend/tests/test_langgraph_complete.py::TestLangGraphNodes::test_event_handler_node -v

# Run tests matching a pattern
pytest backend/tests/ -k "langgraph" -v
```

## Frontend Tests

### Running Frontend Tests

```bash
cd frontend
npm test
```

### Running in Watch Mode

```bash
cd frontend
npm run test:watch
```

### Running with Coverage

```bash
cd frontend
npm run test:coverage
```

## Test Coverage Goals

- **Backend**: All critical paths covered
- **Frontend**: All components tested
- **Integration**: End-to-end flows tested

## Debugging Tests

### Backend

```bash
# Run with detailed output
pytest backend/tests/ -v -s

# Run with pdb debugger on failure
pytest backend/tests/ --pdb

# Run with logging
pytest backend/tests/ --log-cli-level=INFO
```

### Frontend

```bash
# Run with verbose output
cd frontend
npm test -- --verbose

# Run specific test file
npm test -- NotificationBell.test.tsx
```

## Continuous Integration

Tests should pass before merging:
- All backend unit tests
- All backend integration tests
- All frontend component tests
- All end-to-end tests

## Writing New Tests

### Backend Test Template

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_feature_name():
    """Test description"""
    # Arrange
    # Act
    # Assert
    assert True
```

### Frontend Test Template

```typescript
import { render, screen } from '@testing-library/react'
import Component from './Component'

describe('Component', () => {
  it('should render correctly', () => {
    render(<Component />)
    expect(screen.getByText('Expected Text')).toBeInTheDocument()
  })
})
```

