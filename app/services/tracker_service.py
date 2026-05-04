"""Service module for interacting with Yandex Tracker API."""
import io
import asyncio
import logging
from startrek_client import Startrek
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.config import settings
from app.models import Issue, Closure, Author

logger = logging.getLogger(__name__)

_tracker_client: Startrek | None = None  # pylint: disable=invalid-name


def get_tracker_client() -> Startrek:
    """Get or create a Yandex Tracker client instance."""
    global _tracker_client  # pylint: disable=global-statement
    if _tracker_client is None:
        tracker_token = settings.tracker_token
        if not tracker_token:
            logger.warning("TRACKER_TOKEN не задан — интеграция с Tracker отключена")
        _tracker_client = Startrek('Startrek', token=tracker_token)
    return _tracker_client


async def create_tracker_issue(closure, db_session: AsyncSession) -> str:
    """
    Creates a ticket in Yandex Tracker based on data from the Closure object.

    Parameters:
    - closure (Closure): ORM model Closure object containing the following fields:
        - text (str): Message text that will be used as the ticket description.
        - message_id (int): Identifier of the message in the chat.
        - sent_at (datetime): Date and time the message was sent.
        - author (Author): Author object containing messenger and chat_id.

    Returns:
    - str: Key of the created ticket in the format "QUEUE-123".
    """
    tracker_token = settings.tracker_token
    tracker_queue = settings.tracker_queue

    if not tracker_token:
        raise EnvironmentError("TRACKER_TOKEN environment variable is not set")

    if not tracker_queue:
        raise EnvironmentError("TRACKER_QUEUE environment variable is not set")

    client = get_tracker_client()

    summary = f"Сообщение о перекрытии из {closure.author.messenger}"
    description = f"Отправлено {closure.sent_at}\n\n{closure.text}"

    def create_issue():
        logger.info(
            "Вызов issues.create: queue=%r, summary=%r, tags=%r, clientId=%r",
            tracker_queue, summary, [closure.author.messenger], closure.author.id,
        )
        try:
            result = client.issues.create(
                queue=tracker_queue,
                summary=summary,
                description=description,
                tags=[f"{closure.author.messenger}"],
                clientId=closure.author.id
            )
            logger.info("issues.create вернул: %r (key=%s)", result, getattr(result, 'key', 'N/A'))
            return result
        except Exception as exc:  # pylint: disable=broad-except
            response = getattr(exc, 'response', None)
            if response is not None:
                try:
                    body = response.json()
                except Exception:  # pylint: disable=broad-except
                    body = getattr(response, 'text', str(response))
                logger.error(
                    "Ошибка API Tracker: %s — HTTP %s — тело: %s",
                    type(exc).__name__, getattr(response, 'status_code', '?'), body,
                )
            else:
                logger.error("Ошибка Tracker (без HTTP-ответа): %s: %s", type(exc).__name__, exc)
            raise

    # Run the synchronous Startrek SDK call in an executor
    issue = await asyncio.get_running_loop().run_in_executor(None, create_issue)

    if issue is None:
        raise RuntimeError(
            f"Startrek SDK вернул None при создании тикета для closure {closure.id}. "
            "Проверьте TRACKER_TOKEN, TRACKER_QUEUE и права доступа к Яндекс Трекеру."
        )

    # Create Issue record in local database
    await create_issue_record(db_session, closure, issue.key)

    # Return the issue key
    return issue.key


async def create_issue_record(  # pylint: disable=unused-argument
        db_session: AsyncSession, closure, issue_key: str) -> None:
    """
    Creates an Issue record in the local database based on data from the
    Closure object and Tracker issue.

    Parameters:
    - db_session: SQLAlchemy async session for working with the database
    - closure (Closure): ORM model Closure object (unused, reserved for future use)
    - issue_key (str): Key of the created ticket in Tracker
    """
    # Create new Issue object
    issue_obj = Issue(
        tracker_key=issue_key,
        status="open",  # Initial status
        result=None,
        tracker_text=None,
        assignee=None,
        resolved_by=None,
        is_answered=False
    )

    db_session.add(issue_obj)
    await db_session.flush()


async def attach_files_to_issue(issue_key: str, files: list = None):
    """
    Attach files to a Yandex Tracker issue and create a comment with those attachments.

    Args:
        issue_key (str): The key of the issue to attach files to
        files (list): List of UploadFile objects from FastAPI
    """
    tracker_token = settings.tracker_token

    if not tracker_token:
        raise EnvironmentError("TRACKER_TOKEN environment variable is not set")

    if files is None:
        files = []
    if not files:
        return

    client = get_tracker_client()

    class NamedBytesIO(io.BytesIO):  # pylint: disable=missing-class-docstring
        def __init__(self, data: bytes, name: str):
            super().__init__(data)
            self.name = name

    file_objects = []
    for upload_file in files:
        try:
            content = await upload_file.read()
            if not content:
                continue
            filename = upload_file.filename or "unnamed_file"
            file_objects.append(NamedBytesIO(content, filename))
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Ошибка при чтении файла %s: %s", upload_file.filename, e)

    if not file_objects:
        return

    def create_comment_with_attachments():
        result = client.issues[issue_key].comments.create(
            text="Closure media files",
            attachments=file_objects,
        )
        return result

    try:
        await asyncio.get_running_loop().run_in_executor(None, create_comment_with_attachments)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception("Ошибка при прикреплении файлов к тикету %s: %s", issue_key, e)


async def create_tracker_issue_with_attachments(
        closure, db_session: AsyncSession, files=None) -> str:
    """
    Creates a ticket in Yandex Tracker and attaches files if provided.

    Parameters:
    - closure (Closure): ORM model Closure object
    - db_session: SQLAlchemy async session
    - files: Optional list of UploadFile objects

    Returns:
    - str: Key of the created ticket in the format "QUEUE-123".
    """
    # Create tracker issue
    tracker_key = await create_tracker_issue(closure, db_session)

    # If files were uploaded, attach them to the tracker issue
    if files and tracker_key:
        try:
            await attach_files_to_issue(tracker_key, files)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "Не удалось прикрепить файлы к тикету в Tracker для closure %d: %s",
                closure.id, e
            )
            # Continue even if file attachment fails

    return tracker_key


async def sync_tracker_issues(  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        db_session: AsyncSession) -> list[dict]:
    """
    Synchronizes tickets from Yandex Tracker with the local database.

    Parameters:
    - db_session: SQLAlchemy async session for working with the database

    Returns:
    - list[dict]: List of dictionaries with data for user notifications
    """
    tracker_token = settings.tracker_token
    tracker_queue = settings.tracker_queue

    if not tracker_token:
        raise EnvironmentError("TRACKER_TOKEN environment variable is not set")

    if not tracker_queue:
        raise EnvironmentError("TRACKER_QUEUE environment variable is not set")

    client = get_tracker_client()

    def find_issues():
        # Get tickets updated in the last 1 hour
        query = f'Queue: {tracker_queue} Updated: >now()-1h'
        return client.issues.find(query=query)

    try:
        # Run the synchronous Startrek SDK call in an executor
        issues = await asyncio.get_running_loop().run_in_executor(None, find_issues)
    except Exception as e:  # pylint: disable=broad-except
        logger.exception("Ошибка при получении тикетов из Tracker: %s", e)
        return []

    notifications = []

    for issue in issues:  # pylint: disable=too-many-nested-blocks
        try:
            # Get data from the ticket
            issue_key = issue.key
            issue_status = issue.status.key
            issue_result = str(issue.result) if issue.result else None
            issue_text = str(issue.text) if issue.text else None
            issue_tags = issue.tags if issue.tags else []

            # Search for record in DB by tracker_key
            result = await db_session.execute(
                select(Issue).where(Issue.tracker_key == issue_key)
            )
            issue_obj = result.scalar_one_or_none()

            if not issue_obj:
                # Create new Issue object
                issue_obj = Issue(
                    tracker_key=issue_key,
                    status=issue_status,
                    result=issue_result if issue.result else None,
                    tracker_text=issue_text if issue.text else None,
                    assignee=issue.assignee.login if issue.assignee else None,
                    resolved_by=None,  # Will be set when issue is resolved
                    is_answered=False
                )
                db_session.add(issue_obj)
                await db_session.flush()

            # Find closure associated with this issue
            result = await db_session.execute(
                select(Closure)
                .where(Closure.issue_id == issue_key)
                .options(selectinload(Closure.author))
            )
            closure = result.scalar_one_or_none()

            if closure:
                # Check if result has changed
                old_result = issue_obj.result
                result_changed = old_result != issue_result

                # Update fields in DB
                issue_obj.status = issue_status
                issue_obj.result = issue_result
                issue_obj.tracker_text = issue_text
                issue_obj.assignee = issue.assignee.login if issue.assignee else None

                # Handle ban_author tag
                if 'ban_author' in issue_tags:
                    # Get author ID from Tracker's clientId field
                    author_id = issue.clientId if issue.clientId else None

                    if author_id:
                        db_result = await db_session.execute(
                            select(Author).where(Author.id == author_id)
                        )
                        author = db_result.scalar_one_or_none()

                        if author:
                            # Ban the author in DB first
                            author.is_banned = True
                            logger.info(
                                "Author %s has been banned due to ban_author tag", author.id
                            )

                            # Add comment to Tracker
                            def add_comment(key=issue_key):  # pylint: disable=cell-var-from-loop
                                client.issues[key].comments.create(
                                    text="Автор сообщения успешно заблокирован"
                                )
                            await asyncio.get_running_loop().run_in_executor(None, add_comment)
                    else:
                        logger.warning(
                            "Could not find clientId for issue %s with ban_author tag", issue_key
                        )

                # If result has changed, add to notification list
                if result_changed and issue_result is not None:
                    issue_obj.is_answered = False
                    notifications.append({
                        "chat_id": closure.author.chat_id,
                        "message_id": closure.message_id,
                        "result": issue_result,
                        "tracker_text": issue_text,
                        "closure_id": closure.id
                    })

        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Ошибка при обработке тикета %s: %s", issue_key, e)
            await db_session.rollback()

    # Find unnotified issues
    try:
        result = await db_session.execute(
            select(Issue)
            .where(Issue.is_answered.is_(False))
            .where(Issue.status.isnot(None))
            .where(Issue.result.isnot(None))
        )
        unnotified_issues = result.scalars().all()

        for issue_obj in unnotified_issues:
            # Find closure associated with this issue
            result = await db_session.execute(
                select(Closure)
                .where(Closure.issue_id == issue_obj.tracker_key)
                .options(selectinload(Closure.author))
            )
            closure = result.scalar_one_or_none()
            if closure:
                already_queued = any(n["closure_id"] == closure.id for n in notifications)
                if already_queued:
                    continue
                notifications.append({
                    "chat_id": closure.author.chat_id,
                    "message_id": closure.message_id,
                    "result": issue_obj.result,
                    "tracker_text": issue_obj.tracker_text,
                    "closure_id": closure.id
                })
    except Exception as e:  # pylint: disable=broad-except
        logger.exception("Ошибка при поиске неотвеченных тикетов: %s", e)

    # Commit all changes at once
    await db_session.commit()

    return notifications
