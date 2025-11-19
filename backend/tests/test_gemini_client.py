"""
Tests for GeminiClient adapter compatibility with OllamaClient interface
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.gemini_client import GeminiClient
from app.core.config import settings


@pytest.fixture
def mock_gemini_api():
    """Mock Google Generative AI SDK"""
    with patch('app.core.gemini_client.genai') as mock_genai:
        mock_model = MagicMock()
        mock_chat = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Test response from Gemini"
        
        mock_chat.send_message.return_value = mock_response
        mock_model.start_chat.return_value = mock_chat
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.configure = MagicMock()
        
        yield mock_genai


@pytest.fixture
def gemini_client(mock_gemini_api):
    """Create GeminiClient instance with mocked API"""
    with patch.object(settings, 'gemini_api_key', 'test-api-key'):
        with patch.object(settings, 'gemini_model', 'gemini-1.5-pro'):
            client = GeminiClient(model='gemini-1.5-pro')
            return client


class TestGeminiClientInit:
    """Test GeminiClient initialization"""
    
    def test_init_without_api_key(self):
        """Test that initialization fails without API key"""
        with patch.object(settings, 'gemini_api_key', None):
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                GeminiClient()
    
    def test_init_with_api_key(self, mock_gemini_api):
        """Test successful initialization with API key"""
        with patch.object(settings, 'gemini_api_key', 'test-key'):
            with patch.object(settings, 'gemini_model', 'gemini-1.5-pro'):
                client = GeminiClient()
                assert client.model_name == 'gemini-1.5-pro'
                mock_gemini_api.configure.assert_called_once_with(api_key='test-key')
    
    def test_init_with_custom_model(self, mock_gemini_api):
        """Test initialization with custom model"""
        with patch.object(settings, 'gemini_api_key', 'test-key'):
            client = GeminiClient(model='gemini-1.5-flash')
            assert client.model_name == 'gemini-1.5-flash'


class TestGeminiClientGenerate:
    """Test generate() method compatibility"""
    
    @pytest.mark.asyncio
    async def test_generate_basic(self, gemini_client, mock_gemini_api):
        """Test basic generate() call"""
        result = await gemini_client.generate("Hello, world!")
        
        assert isinstance(result, dict)
        assert "message" in result
        assert result["message"]["role"] == "assistant"
        assert "content" in result["message"]
        assert result["model"] == "gemini-1.5-pro"
        assert result["done"] is True
    
    @pytest.mark.asyncio
    async def test_generate_with_system(self, gemini_client, mock_gemini_api):
        """Test generate() with system prompt"""
        result = await gemini_client.generate(
            "Hello",
            system="You are a helpful assistant"
        )
        
        assert isinstance(result, dict)
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_generate_with_context(self, gemini_client, mock_gemini_api):
        """Test generate() with context messages"""
        context = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"}
        ]
        result = await gemini_client.generate("Follow up", context=context)
        
        assert isinstance(result, dict)
        assert "message" in result


class TestGeminiClientGenerateWithContext:
    """Test generate_with_context() method compatibility"""
    
    @pytest.mark.asyncio
    async def test_generate_with_context_basic(self, gemini_client, mock_gemini_api):
        """Test basic generate_with_context() call"""
        session_context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        result = await gemini_client.generate_with_context(
            prompt="What's the weather?",
            session_context=session_context
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_generate_with_context_memory(self, gemini_client, mock_gemini_api):
        """Test generate_with_context() with retrieved memory"""
        memory = ["Memory item 1", "Memory item 2"]
        
        result = await gemini_client.generate_with_context(
            prompt="Test",
            session_context=[],
            retrieved_memory=memory
        )
        
        assert isinstance(result, str)
    
    @pytest.mark.asyncio
    async def test_generate_with_context_tools(self, gemini_client, mock_gemini_api):
        """Test generate_with_context() with tools"""
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    },
                    "required": ["location"]
                }
            }
        ]
        
        result = await gemini_client.generate_with_context(
            prompt="What's the weather in Rome?",
            session_context=[],
            tools=tools
        )
        
        assert isinstance(result, str)
    
    @pytest.mark.asyncio
    async def test_generate_with_context_return_raw(self, gemini_client, mock_gemini_api):
        """Test generate_with_context() with return_raw=True"""
        result = await gemini_client.generate_with_context(
            prompt="Test",
            session_context=[],
            return_raw=True
        )
        
        assert isinstance(result, dict)
        assert "content" in result
        assert "raw_result" in result


class TestGeminiClientListModels:
    """Test list_models() method"""
    
    @pytest.mark.asyncio
    async def test_list_models(self, gemini_client):
        """Test listing available Gemini models"""
        models = await gemini_client.list_models()
        
        assert isinstance(models, list)
        assert len(models) > 0
        assert "gemini-1.5-pro" in models
        assert "gemini-1.5-flash" in models


class TestGeminiClientCompatibility:
    """Test compatibility with OllamaClient interface"""
    
    @pytest.mark.asyncio
    async def test_same_methods_as_ollama(self, gemini_client):
        """Test that GeminiClient has same methods as OllamaClient"""
        # Check required methods exist
        assert hasattr(gemini_client, 'generate')
        assert hasattr(gemini_client, 'generate_with_context')
        assert hasattr(gemini_client, 'list_models')
        assert hasattr(gemini_client, 'close')
        
        # Check methods are callable
        assert callable(gemini_client.generate)
        assert callable(gemini_client.generate_with_context)
        assert callable(gemini_client.list_models)
        assert callable(gemini_client.close)
    
    @pytest.mark.asyncio
    async def test_generate_returns_ollama_format(self, gemini_client, mock_gemini_api):
        """Test that generate() returns Ollama-compatible format"""
        result = await gemini_client.generate("Test")
        
        # Check Ollama-compatible structure
        assert "model" in result
        assert "message" in result
        assert "done" in result
        assert result["message"]["role"] == "assistant"
        assert "content" in result["message"]
    
    @pytest.mark.asyncio
    async def test_close_method(self, gemini_client):
        """Test close() method (should be no-op for Gemini)"""
        # Should not raise
        await gemini_client.close()
        
        # Client should still be usable
        assert gemini_client.model_name is not None

