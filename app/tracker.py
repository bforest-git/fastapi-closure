import os
import traceback
import io
import asyncio
from startrek_client import Startrek


TRACKER_TOKEN = os.environ.get("TRACKER_TOKEN")
TRACKER_QUEUE = os.environ.get("TRACKER_QUEUE")


def create_tracker_issue(closure) -> str:
    """
    Creates a ticket in Yandex Tracker based on data from the Closure object.
    
    Parameters:
    - closure (Closure): ORM model Closure object containing the following fields:
        - text (str): Message text that will be used as the ticket description.
        - messenger (str): Name of the messenger from which the message was sent.
        - chat_id (int): Identifier of the chat in which the message was sent.
        - message_id (int): Identifier of the message in the chat.
        - sent_at (datetime): Date and time the message was sent.
        
    Returns:
    - str: Key of the created ticket in the format "QUEUE-123".
    """
    if not TRACKER_TOKEN:
        raise EnvironmentError("TRACKER_TOKEN environment variable is not set")
    
    if not TRACKER_QUEUE:
        raise EnvironmentError("TRACKER_QUEUE environment variable is not set")
    
    client = Startrek('Startrek', token=TRACKER_TOKEN)
    
    summary = f"Сообщение о перекрытии из {closure.messenger}"
    description = f"Отправлено {closure.sent_at}\n\n{closure.text}"
    
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
    Synchronizes tickets from Yandex Tracker with the local database.
    
    Parameters:
    - db_session: SQLAlchemy session for working with the database
    
    Returns:
    - list[dict]: List of dictionaries with data for user notifications
    """
    if not TRACKER_TOKEN:
        raise EnvironmentError("TRACKER_TOKEN environment variable is not set")
    
    if not TRACKER_QUEUE:
        raise EnvironmentError("TRACKER_QUEUE environment variable is not set")
    
    client = Startrek('Startrek', token=TRACKER_TOKEN)
    
    try:
        # Get tickets updated in the last 1 hour
        query = f'Queue: {TRACKER_QUEUE} Updated: >now()-1h'
        issues = client.issues.find(query=query)
    except Exception as e:
        return []
    
    notifications = []

    for issue in issues:
        try:
            # Get data from the ticket
            issue_key = issue.key
            issue_status = issue.status.key
            issue_result = str(issue.result) if issue.result else None
            issue_text = str(issue.text) if issue.text else None

            # Search for record in DB by tracker_key
            from app.models import Closure
            closure = db_session.query(Closure).filter(Closure.tracker_key == issue_key).first()

            if closure:
                # Check if result has changed
                old_result = closure.result
                result_changed = old_result != issue_result

                # Update fields in DB
                closure.status = issue_status
                closure.result = issue_result
                closure.tracker_text = issue_text

                # If result has changed, add to notification list
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

                # Save changes
                db_session.commit()

            else:
                pass
        except Exception as e:
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
        pass
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

    if not files:
        return

    client = Startrek('Startrek', token=TRACKER_TOKEN)

    class NamedBytesIO(io.BytesIO):
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
        except Exception as e:
            pass

    if not file_objects:
        return

    def create_comment_with_attachments(fo=file_objects):
        result = client.issues[issue_key].comments.create(
            text="Closure media files",
            attachments=fo,
        )
        return result

    try:
        await asyncio.get_running_loop().run_in_executor(None, create_comment_with_attachments)
    except Exception as e:
        pass
