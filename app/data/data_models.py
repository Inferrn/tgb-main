"""Модели данных для работы с опросами"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union


@dataclass
class Level:
    """Уровень вопроса с его параметрами"""
    options: Union[List[str], str]
    image: Optional[str] = None
    height: Optional[str] = None
    angle: Optional[str] = None
    surface: Optional[str] = None


@dataclass
class Question:
    """Модель вопроса опроса"""
    id: int
    text: str
    type: str
    options: Optional[List[str]] = None
    levels: Optional[List[Level]] = None
    if_conditions: Optional[Dict[str, Dict[str, Any]]] = field(default=None, metadata={"field_name": "if"})
    image: Optional[str] = None


@dataclass
class Module:
    """Модуль опроса, содержащий вопросы"""
    questions: Dict[int, Question]


@dataclass
class SurveyData:
    """Полные данные опроса"""
    modules: Dict[str, Module]
    options_scale: List[str]