import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.sync import send_notification, send_bot_notification


@pytest.mark.asyncio
async def test_send_notification_success():
    """Test successful notification sending"""
    # Mock database session and query results
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Mock the database query result
    mock_closure = MagicMock()
    mock_closure.author.messenger = "telegram"
    mock_closure.author.chat_id = 12345
    mock_closure.issue = MagicMock()
    mock_closure.issue.is_answered = False
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_closure
    mock_db.execute.return_value = mock_result
    
    # Mock the send_bot_notification function
    with patch("app.sync.send_bot_notification", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        
        # Test data
        notif = {
            "closure_id": 1,
            "chat_id": 12345,
            "message_id": 67890,
            "result": "Test result",
            "tracker_text": "Test tracker text"
        }
        
        # Call the function
        result = await send_notification(notif, mock_db)
        
        # Assertions
        assert result is True
        mock_send.assert_called_once_with({
            "chat_id": 12345,
            "message_id": 67890,
            "result": "Test result",
            "tracker_text": "Test tracker text",
            "closure_id": 1
        })
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_no_closure():
    """Test notification sending when closure is not found"""
    # Mock database session and query results
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Mock the database query result - no closure found
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Test data
    notif = {"closure_id": 999}  # Non-existent closure ID
    
    # Call the function
    result = await send_notification(notif, mock_db)
    
    # Assertions
    assert result is False
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_send_notification_non_telegram():
    """Test notification sending for non-Telegram messenger"""
    # Mock database session and query results
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Mock the database query result
    mock_closure = MagicMock()
    mock_closure.author.messenger = "whatsapp"  # Not Telegram
    mock_closure.author.chat_id = 12345
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_closure
    mock_db.execute.return_value = mock_result
    
    # Test data
    notif = {"closure_id": 1}
    
    # Call the function
    result = await send_notification(notif, mock_db)
    
    # Assertions
    assert result is False
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_send_bot_notification_success():
    """Test successful bot notification sending"""
    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    
    # Create a context manager for the response
    class MockResponseContext:
        async def __aenter__(self):
            return mock_response
        async def __aexit__(self, *args):
            pass
    
    # Create a context manager for the session
    class MockSessionContext:
        def post(self, *args, **kwargs):
            return MockResponseContext()
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    
    # Mock the ClientSession to return our session context
    with patch("aiohttp.ClientSession", return_value=MockSessionContext()):
        # Test data
        notif = {
            "chat_id": 12345,
            "message_id": 67890,
            "result": "Test result",
            "tracker_text": "Test tracker text",
            "closure_id": 1
        }

        # Call the function
        with patch("app.sync.settings") as mock_settings:
            mock_settings.bot_url = "http://test-bot:8080"
            result = await send_bot_notification(notif)

        # Assertions
        assert result is True


@pytest.mark.asyncio
async def test_send_bot_notification_failure():
    """Test bot notification sending failure"""
    # Create a context manager mock for the session
    class MockSessionContext:
        def __init__(self):
            self.post = AsyncMock()
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, *args):
            pass
    
    # Create mock response
    mock_response = AsyncMock()
    mock_response.status = 500
    
    # Set up the session context
    mock_session_context = MockSessionContext()
    mock_session_context.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    
    # Mock the ClientSession to return our context
    with patch("aiohttp.ClientSession", return_value=mock_session_context):
        # Test data
        notif = {
            "chat_id": 12345,
            "message_id": 67890,
            "result": "Test result",
            "tracker_text": "Test tracker text",
            "closure_id": 1
        }

        # Call the function
        with patch("app.sync.settings") as mock_settings:
            mock_settings.bot_url = "http://test-bot:8080"
            result = await send_bot_notification(notif)

        # Assertions
        assert result is False


@pytest.mark.asyncio
async def test_send_bot_notification_exception():
    """Test bot notification sending with exception"""
    # Create a context manager mock for the session
    class MockSessionContext:
        def __init__(self):
            self.post = AsyncMock()
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, *args):
            pass
    
    # Set up the session context to raise an exception
    mock_session_context = MockSessionContext()
    mock_session_context.post.return_value.__aenter__ = AsyncMock(side_effect=Exception("Network error"))
    
    # Mock the ClientSession to return our context
    with patch("aiohttp.ClientSession", return_value=mock_session_context):
        # Test data
        notif = {
            "chat_id": 12345,
            "message_id": 67890,
            "result": "Test result",
            "tracker_text": "Test tracker text",
            "closure_id": 1
        }

        # Call the function
        with patch("app.sync.settings") as mock_settings:
            mock_settings.bot_url = "http://test-bot:8080"
            result = await send_bot_notification(notif)

        # Assertions
        assert result is False