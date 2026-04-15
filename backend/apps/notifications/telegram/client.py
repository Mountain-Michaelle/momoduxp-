import json
import logging

import httpx
from decouple import config

logger = logging.getLogger(__name__)


class TelegramClient:
    """Small Telegram Bot API client shared by FastAPI routes and Django tasks."""

    def __init__(self, bot_token: str | None = None, base_url: str | None = None):
        token = bot_token or config("TELEGRAM_BOT_TOKEN", default="")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not configured")

        api_base = (base_url or config("TELEGRAM_BASE_URL", default="https://api.telegram.org")).rstrip("/")
        self.base_url = f"{api_base}/bot{token}"

    @staticmethod
    def build_automation_keyboard(reference_id: str) -> str:
        return json.dumps(
            {
                "inline_keyboard": [
                    [
                        {"text": "Confirm", "callback_data": f"automation:confirm:{reference_id}"},
                        {"text": "Stop", "callback_data": f"automation:stop:{reference_id}"},
                    ]
                ]
            }
        )

    def send_message_sync(
        self,
        *,
        chat_id: str,
        text: str,
        reply_markup: str | None = None,
    ) -> dict:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        logger.info(
            "Telegram send_message_sync request chat_id=%s text_length=%s has_reply_markup=%s",
            chat_id,
            len(text),
            bool(reply_markup),
        )
        with httpx.Client(timeout=10) as client:
            response = client.post(f"{self.base_url}/sendMessage", json=payload)
            logger.info(
                "Telegram send_message_sync response status=%s body=%s",
                response.status_code,
                response.text,
            )
            response.raise_for_status()
            return response.json()

    async def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        reply_markup: str | None = None,
    ) -> dict:
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        logger.info(
            "Telegram send_message request chat_id=%s text_length=%s has_reply_markup=%s",
            chat_id,
            len(text),
            bool(reply_markup),
        )
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{self.base_url}/sendMessage", json=payload)
            logger.info(
                "Telegram send_message response status=%s body=%s",
                response.status_code,
                response.text,
            )
            response.raise_for_status()
            return response.json()

    async def answer_callback_query(self, *, callback_query_id: str, text: str, show_alert: bool = False) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.base_url}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_query_id,
                    "text": text,
                    "show_alert": show_alert,
                },
            )
            response.raise_for_status()
            return response.json()
