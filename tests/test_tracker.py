import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.tracker_service import (
    get_tracker_client, 
    create_tracker_issue, 
    create_issue_record,
    attach_files_to_issue,
    create_tracker_issue_with_attachments,
    sync_tracker_issues
)
from app.models import Issue, Closure, Author


@pytest.mark.asyncio
async def test_get_tracker_client():
    """Test getting tracker client"""
    with patch("app.services.tracker_service.settings") as mock_settings:
        mock_settings.tracker_token = "test-token"
        
        # Get client first time
        client1 = get_tracker_client()
        assert client1 is not None
        
        # Get client second time - should be the same instance
        client2 = get_tracker_client()
        assert client1 is client2


@pytest.mark.asyncio
async def test_create_tracker_issue_success():
    """Test successful tracker issue creation"""
    # Mock the tracker client
    mock_client = MagicMock()
    mock_issue = MagicMock()
    mock_issue.key = "TEST-1"
    mock_client.issues.create.return_value = mock_issue
    
    with patch("app.services.tracker_service.get_tracker_client") as mock_get_client:
        mock_get_client.return_value = mock_client
        
        with patch("app.services.tracker_service.settings") as mock_settings:
            mock_settings.tracker_token = "test-token"
            mock_settings.tracker_queue = "TEST"
            
            # Mock closure object
            mock_author = MagicMock()
            mock_author.messenger = "telegram"
            mock_author.id = 123
            
            mock_closure = MagicMock()
            mock_closure.text = "Test closure text"
            mock_closure.message_id = 456
            mock_closure.sent_at = "2026-01-01T12:00:00"
            mock_closure.author = mock_author
            
            # Mock database session
            mock_db = AsyncMock(spec=AsyncSession)
            
            # Call the function
            result = await create_tracker_issue(mock_closure, mock_db)
            
            # Assertions
            assert result == "TEST-1"
            mock_client.issues.create.assert_called_once_with(
                queue="TEST",
                summary="Сообщение о перекрытии из telegram",
                description="Отправлено 2026-01-01T12:00:00\n\nTest closure text",
                tags=["telegram"],
                clientId=123
            )
            mock_db.add.assert_called_once()
            mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_create_issue_record():
    """Test creating issue record in database"""
    # Mock database session
    mock_db = AsyncMock(spec=AsyncSession)
    
    # Mock closure object
    mock_closure = MagicMock()
    mock_closure.id = 1
    
    # Call the function
    await create_issue_record(mock_db, mock_closure, "TEST-1")
    
    # Assertions
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()
    
    # Check that an Issue object was created with correct parameters
    added_issue = mock_db.add.call_args[0][0]
    assert isinstance(added_issue, Issue)
    assert added_issue.tracker_key == "TEST-1"
    assert added_issue.status == "open"
    assert added_issue.is_answered is False


@pytest.mark.asyncio
async def test_attach_files_to_issue_success():
    """Test successful file attachment to issue"""
    # Mock the tracker client
    mock_client = MagicMock()
    mock_issue = MagicMock()
    mock_client.issues.__getitem__.return_value = mock_issue
    
    with patch("app.services.tracker_service.get_tracker_client") as mock_get_client:
        mock_get_client.return_value = mock_client
        
        with patch("app.services.tracker_service.settings") as mock_settings:
            mock_settings.tracker_token = "test-token"
            
            # Mock upload files
            mock_file1 = AsyncMock()
            mock_file1.filename = "test1.jpg"
            mock_file1.read = AsyncMock(return_value=b"test content 1")
            
            mock_file2 = AsyncMock()
            mock_file2.filename = "test2.png"
            mock_file2.read = AsyncMock(return_value=b"test content 2")
            
            files = [mock_file1, mock_file2]
            
            # Call the function
            await attach_files_to_issue("TEST-1", files)
            
            # Assertions
            mock_client.issues.__getitem__.assert_called_with("TEST-1")
            mock_issue.comments.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_tracker_issue_with_attachments():
    """Test creating tracker issue with file attachments"""
    # Mock the create_tracker_issue function
    with patch("app.services.tracker_service.create_tracker_issue", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = "TEST-1"
        
        # Mock the attach_files_to_issue function
        with patch("app.services.tracker_service.attach_files_to_issue", new_callable=AsyncMock) as mock_attach:
            # Mock closure object
            mock_closure = MagicMock()
            mock_closure.id = 1
            
            # Mock database session
            mock_db = AsyncMock(spec=AsyncSession)
            
            # Mock upload files
            mock_file = AsyncMock()
            mock_file.filename = "test.jpg"
            mock_file.read = AsyncMock(return_value=b"test content")
            files = [mock_file]
            
            # Call the function
            result = await create_tracker_issue_with_attachments(mock_closure, mock_db, files)
            
            # Assertions
            assert result == "TEST-1"
            mock_create.assert_called_once_with(mock_closure, mock_db)
            mock_attach.assert_called_once_with("TEST-1", files)


@pytest.mark.asyncio
async def test_sync_tracker_issues_success():
    """Test successful synchronization of tracker issues"""
    # Mock the tracker client
    mock_client = MagicMock()
    
    # Mock issues returned from tracker
    mock_tracker_issue = MagicMock()
    mock_tracker_issue.key = "TEST-1"
    mock_tracker_issue.status.key = "closed"
    mock_tracker_issue.result = "Done"
    mock_tracker_issue.text = "Issue resolved"
    mock_tracker_issue.tags = []
    mock_tracker_issue.assignee.login = "test-user"
    mock_tracker_issue.clientId = None
    
    mock_client.issues.find.return_value = [mock_tracker_issue]
    
    with patch("app.services.tracker_service.get_tracker_client") as mock_get_client:
        mock_get_client.return_value = mock_client
        
        with patch("app.services.tracker_service.settings") as mock_settings:
            mock_settings.tracker_token = "test-token"
            mock_settings.tracker_queue = "TEST"
            
            # Mock database session and query results
            mock_db = AsyncMock(spec=AsyncSession)
            
            # Mock Issue query - no existing issue in DB
            mock_issue_result = MagicMock()
            mock_issue_result.scalar_one_or_none.return_value = None
            mock_db.execute.side_effect = [
                mock_issue_result,  # First call for Issue
                MagicMock(),        # Second call for Closure
                MagicMock(),        # Third call for unnotified issues
            ]
            
            # Mock Closure query - no closure found
            mock_closure_result = MagicMock()
            mock_closure_result.scalar_one_or_none.return_value = None
            mock_db.execute.side_effect = [
                mock_issue_result,     # First call for Issue
                mock_closure_result,   # Second call for Closure
                MagicMock(),           # Third call for unnotified issues
            ]
            
            # Call the function
            result = await sync_tracker_issues(mock_db)
            
            # Assertions
            assert isinstance(result, list)
            mock_client.issues.find.assert_called_once()
            mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_tracker_issues_no_token():
    """Test synchronization when tracker token is not set"""
    with patch("app.services.tracker_service.settings") as mock_settings:
        mock_settings.tracker_token = ""  # Empty token
        mock_settings.tracker_queue = "TEST"
        
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        # Call the function and expect an exception
        with pytest.raises(EnvironmentError):
            await sync_tracker_issues(mock_db)


@pytest.mark.asyncio
async def test_sync_tracker_issues_no_queue():
    """Test synchronization when tracker queue is not set"""
    with patch("app.services.tracker_service.settings") as mock_settings:
        mock_settings.tracker_token = "test-token"
        mock_settings.tracker_queue = ""  # Empty queue
        
        # Mock database session
        mock_db = AsyncMock(spec=AsyncSession)
        
        # Call the function and expect an exception
        with pytest.raises(EnvironmentError):
            await sync_tracker_issues(mock_db)