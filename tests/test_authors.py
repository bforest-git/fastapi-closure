import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ban_author_not_found(client: AsyncClient, admin_headers):
    """Test banning non-existing author returns 404."""
    response = await client.post(
        "/authors/ban",
        json={"user_id": 99999},
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Author not found"}


@pytest.mark.asyncio
async def test_ban_existing_author(client: AsyncClient, sample_author, admin_headers):
    """Test banning existing author."""
    response = await client.post(
        "/authors/ban",
        json={"user_id": sample_author.id},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_banned"] is True
    assert data["id"] == sample_author.id


@pytest.mark.asyncio
async def test_ban_already_banned_author(client: AsyncClient, banned_author, admin_headers):
    """Test banning already banned author."""
    response = await client.post(
        "/authors/ban",
        json={"user_id": banned_author.id},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_banned"] is True
    assert data["id"] == banned_author.id


@pytest.mark.asyncio
async def test_ban_no_admin_key(client: AsyncClient):
    """Test banning without admin key - returns 401 (missing header) or 403 (wrong key)."""
    response = await client.post(
        "/authors/ban",
        json={"user_id": 1},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ban_wrong_admin_key(client: AsyncClient):
    """Test banning with wrong admin key."""
    response = await client.post(
        "/authors/ban",
        json={"user_id": 1},
        headers={"X-Admin-Key": "wrong-key"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unban_banned_author(client: AsyncClient, banned_author, admin_headers):
    """Test unbanning banned author."""
    response = await client.post(
        "/authors/unban",
        json={"user_id": banned_author.id},
        headers=admin_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_banned"] is False
    assert data["id"] == banned_author.id


@pytest.mark.asyncio
async def test_unban_not_found(client: AsyncClient, admin_headers):
    """Test unbanning non-existing author."""
    response = await client.post(
        "/authors/unban",
        json={"user_id": 99999},
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Author not found"}


@pytest.mark.asyncio
async def test_unban_no_admin_key(client: AsyncClient, banned_author):
    """Test unbanning without admin key - returns 401 (missing header) or 403 (wrong key)."""
    response = await client.post(
        "/authors/unban",
        json={"user_id": banned_author.id},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_authors_empty(client: AsyncClient):
    """Test listing authors when DB is empty."""
    response = await client.get("/authors/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_author(client: AsyncClient):
    """Test successful author creation."""
    response = await client.post(
        "/authors/",
        json={"messenger": "telegram", "chat_id": 55555},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["messenger"] == "telegram"
    assert data["chat_id"] == 55555
    assert data["is_banned"] is False
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_author_duplicate(client: AsyncClient):
    """Test creating duplicate author returns 409."""
    # Create first author
    response1 = await client.post(
        "/authors/",
        json={"messenger": "telegram", "chat_id": 66666},
    )
    assert response1.status_code == 201
    
    # Try to create duplicate
    response2 = await client.post(
        "/authors/",
        json={"messenger": "telegram", "chat_id": 66666},
    )
    assert response2.status_code == 409
    assert response2.json() == {"detail": "Author with this messenger and chat_id already exists"}
@pytest.mark.asyncio
async def test_list_authors_pagination(client: AsyncClient, sample_author, banned_author, third_author):
    """Test authors pagination."""
    # Ban the third author
    await client.post(
        "/authors/ban",
        json={"user_id": third_author.id},
        headers={"X-Admin-Key": "test-admin-key"},
    )

    # Get first page
    response = await client.get("/authors/?skip=0&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_list_banned_authors(client: AsyncClient, sample_author, banned_author):
    """Test listing banned authors."""
    response = await client.get("/authors/banned")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["is_banned"] is True
    assert data[0]["id"] == banned_author.id


@pytest.mark.asyncio
async def test_list_banned_authors_empty(client: AsyncClient, sample_author):
    """Test listing banned authors when none exist."""
    response = await client.get("/authors/banned")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_author_found(client: AsyncClient, sample_author):
    """Test searching for an existing author."""
    response = await client.get(
        "/authors/search",
        params={"messenger": sample_author.messenger, "chat_id": sample_author.chat_id}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_author.id
    assert data["messenger"] == sample_author.messenger
    assert data["chat_id"] == sample_author.chat_id
    assert data["is_banned"] == sample_author.is_banned


@pytest.mark.asyncio
async def test_search_author_not_found(client: AsyncClient):
    """Test searching for a non-existing author."""
    response = await client.get(
        "/authors/search",
        params={"messenger": "telegram", "chat_id": 99999}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Author not found"}
