import pytest
from datetime import datetime
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_closure_happy_path(client: AsyncClient, sample_author, mock_tracker):
    """Test successful closure creation with existing author."""
    response = await client.post(
        "/closures/",
        data={
            "text": "Перекрытие на ул. Ленина",
            "user_id": str(sample_author.id),
            "message_id": "1001",
            "sent_at": "2024-01-01T12:00:00",
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Перекрытие на ул. Ленина"
    assert data["id"] is not None
    assert data["author_id"] == sample_author.id
    mock_tracker["create"].assert_called_once()


@pytest.mark.asyncio
async def test_create_closure_with_user_id(client: AsyncClient, sample_author, mock_tracker):
    """Test closure creation with user_id."""
    response = await client.post(
        "/closures/",
        data={
            "text": "Еще одно перекрытие",
            "user_id": str(sample_author.id),
            "message_id": "1002",
            "sent_at": "2024-01-02T12:00:00",
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Еще одно перекрытие"
    assert data["author_id"] == sample_author.id
    mock_tracker["create"].assert_called_once()


@pytest.mark.asyncio
async def test_create_closure_banned_author(client: AsyncClient, banned_author):
    """Test closure creation with banned author should fail."""
    response = await client.post(
        "/closures/",
        data={
            "text": "Перекрытие от забаненного автора",
            "user_id": str(banned_author.id),
            "message_id": "1003",
            "sent_at": "2024-01-03T12:00:00",
        }
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Author is banned"}


@pytest.mark.asyncio
async def test_create_closure_tracker_fails(client: AsyncClient, sample_author, mock_tracker):
    """Test closure creation when tracker fails - closure is still created."""
    mock_tracker["create"].side_effect = Exception("Tracker error")

    response = await client.post(
        "/closures/",
        data={
            "text": "Перекрытие с ошибкой трекера",
            "user_id": str(sample_author.id),
            "message_id": "1004",
            "sent_at": "2024-01-04T12:00:00",
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Перекрытие с ошибкой трекера"
    mock_tracker["create"].assert_called_once()


@pytest.mark.asyncio
async def test_create_closure_with_files(client: AsyncClient, sample_author, mock_tracker):
    """Test closure creation with file attachments."""
    files = [
        ("files", ("test.txt", b"test content", "text/plain")),
    ]

    response = await client.post(
        "/closures/",
        data={
            "text": "Перекрытие с файлами",
            "user_id": str(sample_author.id),
            "message_id": "1005",
            "sent_at": "2024-01-05T12:00:00",
        },
        files=files
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Перекрытие с файлами"
    mock_tracker["create"].assert_called_once()
    mock_tracker["attach"].assert_called_once()


@pytest.mark.asyncio
async def test_create_closure_file_attach_fails(client: AsyncClient, sample_author, mock_tracker):
    """Test closure creation when file attachment fails."""
    mock_tracker["attach"].side_effect = Exception("Attachment error")

    files = [
        ("files", ("test.txt", b"test content", "text/plain")),
    ]

    response = await client.post(
        "/closures/",
        data={
            "text": "Перекрытие с ошибкой прикрепления",
            "user_id": str(sample_author.id),
            "message_id": "1006",
            "sent_at": "2024-01-06T12:00:00",
        },
        files=files
    )
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Перекрытие с ошибкой прикрепления"
    mock_tracker["create"].assert_called_once()
    mock_tracker["attach"].assert_called_once()


@pytest.mark.asyncio
async def test_create_closure_missing_required_field(client: AsyncClient):
    """Test closure creation with missing required field."""
    response = await client.post(
        "/closures/",
        data={
            "user_id": "1",
            "message_id": "1007",
            "sent_at": "2024-01-07T12:00:00",
        }
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_closures_empty(client: AsyncClient):
    """Test listing closures when DB is empty."""
    response = await client.get("/closures/")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_closures_with_data(client: AsyncClient, sample_closure):
    """Test listing closures with data."""
    response = await client.get("/closures/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == sample_closure.text


@pytest.mark.asyncio
async def test_list_closures_pagination(client: AsyncClient, third_author):
    """Test closures pagination."""
    # Create 3 closures
    for i in range(3):
        await client.post(
            "/closures/",
            data={
                "text": f"Перекрытие {i+1}",
                "user_id": str(third_author.id),
                "message_id": str(2000 + i),
                "sent_at": f"2024-01-01T12:0{i}:00",
            }
        )

    # Get first page
    response = await client.get("/closures/?skip=0&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["text"] == "Перекрытие 1"


@pytest.mark.asyncio
async def test_get_closure_found(client: AsyncClient, sample_closure):
    """Test getting closure by existing ID."""
    response = await client.get(f"/closures/{sample_closure.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == sample_closure.text
    assert data["id"] == sample_closure.id


@pytest.mark.asyncio
async def test_get_closure_not_found(client: AsyncClient):
    """Test getting closure by non-existing ID."""
    response = await client.get("/closures/9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Closure not found"}


@pytest.mark.asyncio
async def test_delete_closure_found(client: AsyncClient, sample_closure, admin_headers):
    """Test deleting existing closure."""
    response = await client.delete(f"/closures/{sample_closure.id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.asyncio
async def test_delete_closure_not_found(client: AsyncClient, admin_headers):
    """Test deleting non-existing closure."""
    response = await client.delete("/closures/9999", headers=admin_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Closure not found"}


@pytest.mark.asyncio
async def test_delete_closure_removes_from_db(client: AsyncClient, sample_closure, admin_headers):
    """Test that deleted closure is actually removed from DB."""
    # Delete closure
    await client.delete(f"/closures/{sample_closure.id}", headers=admin_headers)

    # Try to get deleted closure
    response = await client.get(f"/closures/{sample_closure.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_closure_found(client: AsyncClient, sample_closure, admin_headers):
    """Test updating existing closure."""
    response = await client.patch(
        f"/closures/{sample_closure.id}",
        json={"text": "Обновленное перекрытие"},
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Обновленное перекрытие"


@pytest.mark.asyncio
async def test_update_closure_partial(client: AsyncClient, sample_closure, admin_headers):
    """Test partial update of closure - text remains unchanged."""
    response = await client.patch(
        f"/closures/{sample_closure.id}",
        json={"text": "Новый текст перекрытия"},
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "Новый текст перекрытия"
    assert data["id"] == sample_closure.id


@pytest.mark.asyncio
async def test_update_closure_not_found(client: AsyncClient, admin_headers):
    """Test updating non-existing closure."""
    response = await client.patch(
        "/closures/9999",
        json={"text": "Обновленное перекрытие"},
        headers=admin_headers
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Closure not found"}


@pytest.mark.asyncio
async def test_create_closure_user_not_found(client: AsyncClient):
    """Test creating closure with non-existing user_id returns 404."""
    response = await client.post(
        "/closures/",
        data={
            "text": "Перекрытие",
            "user_id": "99999",
            "message_id": "1001",
            "sent_at": "2024-01-01T12:00:00",
        }
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Author not found"}
