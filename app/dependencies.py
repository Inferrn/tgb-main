from aiogram import BaseMiddleware
from typing import Callable, Awaitable, Dict, Any
from aiogram.types import TelegramObject

class DependencyMiddleware(BaseMiddleware):
    def __init__(self, survey_service, keyboard_factory, message_builder):
        self.survey_service = survey_service
        self.keyboard_factory = keyboard_factory
        self.message_builder = message_builder

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["survey_service"] = self.survey_service
        data["keyboard_factory"] = self.keyboard_factory
        data["message_builder"] = self.message_builder
        return await handler(event, data)