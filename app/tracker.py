import os
import traceback
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
            issue_result = str(issue.result) if issue.result else None
            issue_status = issue.status.key
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
