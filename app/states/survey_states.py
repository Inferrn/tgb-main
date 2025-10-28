"""Состояния FSM для опроса"""
from aiogram.fsm.state import State, StatesGroup


class SurveyStates(StatesGroup):
    """Состояния опроса"""
    
    # Опрос в процессе
    in_progress = State()
    
    # Работа с уровнем вопроса
    processing_level = State()