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
            issue_result = issue.result
            issue_status = issue.status.key
            if issue.text:
                issue_text = issue.text
            else:
                issue_text = None
            
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
                    notifications.append({
                        "chat_id": closure.chat_id,
                        "message_id": closure.message_id,
                        "messenger": closure.messenger,
                        "result": issue_result,
                        "tracker_text": issue_text
                    })
                
                # Сохраняем изменения
                db_session.commit()
                
        except Exception as e:
            logger.error(f"Error processing issue {issue.key}: {e}")
            db_session.rollback()
    
    return notifications