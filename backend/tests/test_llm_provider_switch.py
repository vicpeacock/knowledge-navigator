"""
Tests for LLM provider switching between Ollama and Gemini
"""
import pytest
from unittest.mock import patch, MagicMock
from app.core.dependencies import init_clients, get_ollama_client, get_planner_client, get_ollama_background_client
from app.core.config import settings


class TestLLMProviderSwitch:
    """Test switching between Ollama and Gemini providers"""
    
    @pytest.fixture
    def mock_ollama_client(self):
        """Mock OllamaClient"""
        with patch('app.core.dependencies.OllamaClient') as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance
    
    @pytest.fixture
    def mock_gemini_client(self):
        """Mock GeminiClient"""
        with patch('app.core.dependencies.GeminiClient') as mock:
            mock_instance = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance
    
    def test_init_with_ollama_provider(self, mock_ollama_client):
        """Test initialization with Ollama provider"""
        with patch.object(settings, 'llm_provider', 'ollama'):
            with patch('app.core.dependencies.init_clients') as mock_init:
                # Reset global state
                import app.core.dependencies as deps
                deps._ollama_client = None
                deps._planner_client = None
                
                init_clients()
                
                client = get_ollama_client()
                assert client is not None
    
    def test_init_with_gemini_provider(self, mock_gemini_client):
        """Test initialization with Gemini provider"""
        with patch.object(settings, 'llm_provider', 'gemini'):
            with patch.object(settings, 'gemini_api_key', 'test-key'):
                with patch.object(settings, 'gemini_model', 'gemini-1.5-pro'):
                    # Reset global state
                    import app.core.dependencies as deps
                    deps._ollama_client = None
                    deps._planner_client = None
                    
                    # Mock other dependencies
                    with patch('app.core.dependencies.MCPClient'):
                        with patch('app.core.dependencies.MemoryManager'):
                            with patch('app.core.dependencies.AgentActivityStream'):
                                with patch('app.core.dependencies.BackgroundTaskManager'):
                                    with patch('app.core.dependencies.NotificationCenter'):
                                        with patch('app.core.dependencies.TaskQueue'):
                                            with patch('app.core.dependencies.AgentScheduler'):
                                                with patch('app.core.dependencies.TaskDispatcher'):
                                                    init_clients()
                                                    
                                                    client = get_ollama_client()
                                                    assert client is not None
    
    def test_get_ollama_client_returns_correct_type(self):
        """Test that get_ollama_client() returns correct client type"""
        with patch.object(settings, 'llm_provider', 'ollama'):
            with patch('app.core.dependencies.OllamaClient') as mock_ollama:
                mock_instance = MagicMock()
                mock_ollama.return_value = mock_instance
                
                import app.core.dependencies as deps
                deps._ollama_client = None
                deps._planner_client = None
                
                init_clients()
                client = get_ollama_client()
                
                # Should be OllamaClient instance
                assert client == mock_instance
    
    def test_get_planner_client_with_gemini(self):
        """Test that planner client uses Gemini when provider is gemini"""
        with patch.object(settings, 'llm_provider', 'gemini'):
            with patch.object(settings, 'gemini_api_key', 'test-key'):
                with patch.object(settings, 'gemini_model', 'gemini-1.5-pro'):
                    with patch.object(settings, 'gemini_planner_model', None):
                        with patch('app.core.dependencies.GeminiClient') as mock_gemini:
                            mock_instance = MagicMock()
                            mock_gemini.return_value = mock_instance
                            
                            import app.core.dependencies as deps
                            deps._ollama_client = None
                            deps._planner_client = None
                            
                            # Mock other dependencies
                            with patch('app.core.dependencies.MCPClient'):
                                with patch('app.core.dependencies.MemoryManager'):
                                    with patch('app.core.dependencies.AgentActivityStream'):
                                        with patch('app.core.dependencies.BackgroundTaskManager'):
                                            with patch('app.core.dependencies.NotificationCenter'):
                                                with patch('app.core.dependencies.TaskQueue'):
                                                    with patch('app.core.dependencies.AgentScheduler'):
                                                        with patch('app.core.dependencies.TaskDispatcher'):
                                                            init_clients()
                                                            
                                                            planner = get_planner_client()
                                                            assert planner is not None
                                                            # Should use gemini_model (fallback)
                                                            mock_gemini.assert_called()
    
    def test_get_background_client_with_gemini(self):
        """Test that background client uses Gemini when provider is gemini"""
        with patch.object(settings, 'llm_provider', 'gemini'):
            with patch.object(settings, 'gemini_api_key', 'test-key'):
                with patch.object(settings, 'gemini_model', 'gemini-1.5-pro'):
                    with patch.object(settings, 'gemini_background_model', None):
                        with patch('app.core.dependencies.GeminiClient') as mock_gemini:
                            mock_instance = MagicMock()
                            mock_gemini.return_value = mock_instance
                            
                            bg_client = get_ollama_background_client()
                            
                            assert bg_client is not None
                            # Should use gemini_model (fallback)
                            mock_gemini.assert_called()
    
    def test_background_client_uses_specified_model(self):
        """Test that background client uses specified Gemini model"""
        with patch.object(settings, 'llm_provider', 'gemini'):
            with patch.object(settings, 'gemini_api_key', 'test-key'):
                with patch.object(settings, 'gemini_model', 'gemini-1.5-pro'):
                    with patch.object(settings, 'gemini_background_model', 'gemini-1.5-flash'):
                        with patch('app.core.dependencies.GeminiClient') as mock_gemini:
                            mock_instance = MagicMock()
                            mock_gemini.return_value = mock_instance
                            
                            bg_client = get_ollama_background_client()
                            
                            # Should use gemini_background_model
                            mock_gemini.assert_called_with(model='gemini-1.5-flash')

