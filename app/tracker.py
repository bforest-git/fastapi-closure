import os
import traceback
import io
import asyncio
from startrek_client import Startrek
import logging

logger = logging.getLogger(__name__)

# Read configuration from environment variables
TRACKER_TOKEN = os.environ.get("TRACKER_TOKEN")
TRACKER_QUEUE = os.environ.get("TRACKER_QUEUE")


def create_tracker_issue(closure) -> str:
    """
    Создает тикет в Яндекс Трекере на основе данных из объекта Closure.
    
    Параметры:
    - closure (Closure): Объект ORM-модели Closure, содержащий следующие поля:
        - text (str): Текст сообщения, который будет использован как описание тикета.
        - messenger (str): Название мессенджера, из которого пришло сообщение.
        - chat_id (int): Идентификатор чата, в котором было отправлено сообщение.
        - message_id (int): Идентификатор сообщения в чате.
        - sent_at (datetime): Дата и время отправки сообщения.
        
    Возвращает:
    - str: Ключ созданного тикета в формате "QUEUE-123".
    """
    if not TRACKER_TOKEN:
        raise EnvironmentError("TRACKER_TOKEN environment variable is not set")
    
    if not TRACKER_QUEUE:
        raise EnvironmentError("TRACKER_QUEUE environment variable is not set")
    
    client = Startrek('Startrek', token=TRACKER_TOKEN)
    
    # Create issue summary
    summary = f"Сообщение о перекрытии из {closure.messenger}"
    description = f"Отправлено {closure.sent_at}\n\n{closure.text}"
    
    # Create the issue
    issue = client.issues.create(
        queue=TRACKER_QUEUE,
        summary=summary,
        description=description,
        tags=[f"{closure.messenger}"]
    )
    
    # Return the issue key
    return issue.key


def sync_tracker_issues(db_session) -> list[dict]:
    """
    Синхронизирует тикеты из Яндекс Трекера с локальной БД.
    
    Параметры:
    - db_session: Сессия SQLAlchemy для работы с БД
    
    Возвращает:
    - list[dict]: Список словарей с данными для уведомления пользователей
    """
    if not TRACKER_TOKEN:
        raise EnvironmentError("TRACKER_TOKEN environment variable is not set")
    
    if not TRACKER_QUEUE:
        raise EnvironmentError("TRACKER_QUEUE environment variable is not set")
    
    client = Startrek('Startrek', token=TRACKER_TOKEN)
    
    try:
        # Получаем тикеты, обновленные за последние 24 часа
        query = f'Queue: {TRACKER_QUEUE} Updated: >now()-24h'
        issues = client.issues.find(query=query)
    except Exception as e:
        logger.error(f"Failed to fetch issues from Tracker: {e}")
        return []
    
    notifications = []

    for issue in issues:
        try:
            # Получаем данные из тикета
            issue_key = issue.key
            issue_status = issue.status.key
            issue_result = str(issue.result) if issue.result else None
            issue_text = str(issue.text) if issue.text else None

            # Ищем запись в БД по tracker_key
            from app.models import Closure
            closure = db_session.query(Closure).filter(Closure.tracker_key == issue_key).first()

            if closure:
                # Проверяем, изменился ли result
                old_result = closure.result
                result_changed = old_result != issue_result

                # Обновляем поля в БД
                closure.status = issue_status
                closure.result = issue_result
                closure.tracker_text = issue_text

                # Если result изменился, добавляем в список уведомлений
                if result_changed and issue_result is not None:
                    closure.is_answered = False
                    notifications.append({
                        "chat_id": closure.chat_id,
                        "message_id": closure.message_id,
                        "messenger": closure.messenger,
                        "result": issue_result,
                        "tracker_text": issue_text,
                        "closure_id": closure.id
                    })

                # Сохраняем изменения
                db_session.commit()

            else:
                logger.warning(
                    f"[sync_tracker_issues] No closure found in DB for tracker_key={issue_key!r}, skipping"
                )

        except Exception as e:
            logger.error(f"[sync_tracker_issues] Error processing issue {issue.key}: {e}", exc_info=True)
            db_session.rollback()

    try:
        from app.models import Closure
        unnotified_closures = db_session.query(Closure).filter(
            Closure.is_answered == False,
            Closure.status.isnot(None),
            Closure.result.isnot(None)
        ).all()

        for closure in unnotified_closures:
            already_queued = any(n["closure_id"] == closure.id for n in notifications)
            if already_queued:
                continue
            notifications.append({
                "chat_id": closure.chat_id,
                "message_id": closure.message_id,
                "messenger": closure.messenger,
                "result": closure.result,
                "tracker_text": closure.tracker_text,
                "closure_id": closure.id
            })
    except Exception as e:
        logger.error(f"[sync_tracker_issues] Error processing unnotified closures: {e}", exc_info=True)

    return notifications


async def attach_files_to_issue(issue_key: str, files: list):
    """
    Attach files to a Yandex Tracker issue and create a comment with those attachments.
    Args:
        issue_key (str): The key of the issue to attach files to
        files (list): List of UploadFile objects from FastAPI
    """
    if not TRACKER_TOKEN:
        raise EnvironmentError("TRACKER_TOKEN environment variable is not set")

    # If no files, don't create a comment
    if not files:
        logger.info(f"No files to attach to issue {issue_key}, skipping comment creation")
        return

    client = Startrek('Startrek', token=TRACKER_TOKEN)

    # Read all file contents upfront (must be done in async context before executor).
    # _upload_attachments() calls Attachments.create(attachment) for each item,
    # which calls _create_from_file(file) and uses _get_filename(file) to get the name
    # via getattr(file, 'name', None). So we subclass BytesIO to carry the filename.
    class NamedBytesIO(io.BytesIO):
        def __init__(self, data: bytes, name: str):
            super().__init__(data)
            self.name = name

    file_objects = []
    for upload_file in files:
        try:
            content = await upload_file.read()
            if not content:
                logger.warning(f"File {upload_file.filename!r} is empty (0 bytes), skipping")
                continue
            filename = upload_file.filename or "unnamed_file"
            file_objects.append(NamedBytesIO(content, filename))
            logger.info(f"Read file {filename!r} ({len(content)} bytes) for issue {issue_key}")
        except Exception as e:
            logger.error(f"Failed to read file {upload_file.filename!r}: {e}", exc_info=True)

    if not file_objects:
        logger.info(f"No readable files for issue {issue_key}, skipping comment creation")
        return

    # Create a comment with attachments in one call.
    # IssueComments.create() calls _upload_attachments(self, kwargs) which:
    #   1. Pops 'attachments' from kwargs
    #   2. For each item calls Attachments.create(item) → uploads via /v2/attachments/
    #   3. Collects returned IDs and sets kwargs['attachmentIds'] = [...]
    #   4. Then the comment is created with those IDs bound to it
    # This is the only correct way to attach files to a comment in Tracker API.
    def create_comment_with_attachments(fo=file_objects):
        logger.info(
            f"[attach] Creating comment with {len(fo)} attachment(s) "
            f"for issue {issue_key}: {[f.name for f in fo]!r}"
        )
        result = client.issues[issue_key].comments.create(
            text="Медиафайлы перекрытия",
            attachments=fo,
        )
        logger.info(
            f"[attach] Comment created id={getattr(result, 'id', None)!r}, "
            f"attachments={getattr(result, 'attachments', 'N/A')!r}"
        )
        return result

    try:
        await asyncio.get_running_loop().run_in_executor(None, create_comment_with_attachments)
        logger.info(f"Created comment with {len(file_objects)} attachment(s) for issue {issue_key}")
    except Exception as e:
        logger.error(f"Failed to create comment with attachments for issue {issue_key}: {e}", exc_info=True)
