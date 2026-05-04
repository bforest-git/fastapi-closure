import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_issues_empty(client: AsyncClient):
    """Test listing issues when DB is empty."""
    response = await client.get("/issues/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_issues_with_data(client: AsyncClient, sample_issue):
    """Test listing issues with data."""
    response = await client.get("/issues/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["tracker_key"] == sample_issue.tracker_key


@pytest.mark.asyncio
async def test_list_issues_pagination(client: AsyncClient, sample_issue, db_session):
    """Test issues pagination."""
    from app.models import Issue
    from datetime import datetime

    # Create another issue directly in DB
    async with db_session() as session:
        issue = Issue(
            tracker_key="TEST-2",
            status="open",
            is_answered=False,
        )
        session.add(issue)
        await session.commit()

    # Get first page
    response = await client.get("/issues/?skip=0&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_get_issue_found(client: AsyncClient, sample_issue):
    """Test getting issue by existing key."""
    response = await client.get(f"/issues/{sample_issue.tracker_key}")
    assert response.status_code == 200
    data = response.json()
    assert data["tracker_key"] == sample_issue.tracker_key


@pytest.mark.asyncio
async def test_get_issue_not_found(client: AsyncClient):
    """Test getting issue by non-existing key."""
    response = await client.get("/issues/NON-EXISTENT")
    assert response.status_code == 404
    assert response.json() == {"detail": "Issue not found"}


@pytest.mark.asyncio
async def test_update_issue_found(client: AsyncClient, sample_issue, admin_headers):
    """Test updating existing issue with valid key."""
    response = await client.patch(
        f"/issues/{sample_issue.tracker_key}",
        json={"status": "closed", "result": "Проблема решена"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "closed"
    assert data["result"] == "Проблема решена"


@pytest.mark.asyncio
async def test_update_issue_not_found(client: AsyncClient, admin_headers):
    """Test updating non-existing issue."""
    response = await client.patch(
        "/issues/NON-EXISTENT",
        json={"status": "closed"},
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Issue not found"}


@pytest.mark.asyncio
async def test_update_issue_no_admin_key(client: AsyncClient, sample_issue):
    """Test updating issue without admin key - returns 401 (missing header) or 403 (wrong key)."""
    response = await client.patch(
        f"/issues/{sample_issue.tracker_key}",
        json={"status": "closed"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_issue_wrong_admin_key(client: AsyncClient, sample_issue):
    """Test updating issue with wrong admin key."""
    response = await client.patch(
        f"/issues/{sample_issue.tracker_key}",
        json={"status": "closed"},
        headers={"X-Admin-Key": "wrong-key"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_issue_partial(client: AsyncClient, sample_issue, admin_headers):
    """Test partial update of issue."""
    response = await client.patch(
        f"/issues/{sample_issue.tracker_key}",
        json={"is_answered": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_answered"] is True
    assert data["status"] == sample_issue.status
