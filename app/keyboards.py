from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="/survey"), KeyboardButton(text="/help")]
    ], resize_keyboard=True)
    return kb

def question_inline_keyboard(question) -> InlineKeyboardMarkup:
    """
    Ожидается, что question.options — список объектов с полями id и text.
    Callback-format: survey:answer:<question_id>:<option_id>
    """
    kb = InlineKeyboardMarkup(row_width=1)
    for opt in getattr(question, "options", []):
        cb = f"survey:answer:{question.id}:{opt.id}"
        kb.add(InlineKeyboardButton(text=opt.text, callback_data=cb))
    return kb