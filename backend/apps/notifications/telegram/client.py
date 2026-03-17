import httpx 
import json
from decouple import config 


class TelegramClient:

    def __init__(self, bot_token:str, chat_id:str):
        self.base_url = f"{config('TELEGRAM_BASE_URL')}/bot/{bot_token}"
        self.chat_id = chat_id

    def send_approval_sync(self, text: str, post_id: str) -> None:
        """
        Synchronous method to send approval request.
        Used by Celery tasks.
        
        Args:
            text: The message text to send
            post_id: The post ID for callback data
        """
        keyboard = {
            "inline_keyboard":
            [
                [
                    {"text":"Approve", "callback_data":f"approve:{post_id}"},
                    {"text": "Reject", "callback_data":f"reject:{post_id}"}
                ]
            ]    
        }

        with httpx.Client(timeout=10) as client:
            client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id":self.chat_id,
                    "text":text, 
                    "reply_markup":json.dumps(keyboard),
                }
            )

    async def send_approval(self, text:str, post_id:str):
        """
        Asynchronous method to send approval request.
        Used by async views and services.
        
        Args:
            text: The message text to send
            post_id: The post ID for callback data
        """
        keyboard = {
            "inline_keyboard":
            [
                [
                    {"text":"Approve", "callback_data":f"approve:{post_id}"},
                    {"text": "Reject", "callback_data":f"reject:{post_id}"}
                ]
            ]    
        }

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id":self.chat_id,
                    "text":text, 
                    "reply_markup":json.dumps(keyboard),
                }
            )

