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