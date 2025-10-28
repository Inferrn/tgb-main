"""Сервис для управления логикой опроса"""
from typing import Dict, List, Optional, Any, Tuple
import logging
from dataclasses import asdict, dataclass

from app.data.data_models import SurveyData, Question, Level

logger = logging.getLogger(__name__)


class SurveyService:
    """Сервис для управления опросами и их логикой"""
    
    def __init__(self, survey_data: SurveyData):
        """
        Инициализирует сервис опросов
        
        Args:
            survey_data: Данные опроса
        """
        self.survey_data = survey_data
    
    def get_question(self, module: str, question_id: int) -> Optional[Question]:
        """
        Получает вопрос по ID и модулю
        
        Args:
            module: Название модуля
            question_id: ID вопроса
            
        Returns:
            Optional[Question]: Объект вопроса или None, если не найден
        """
        try:
            return self.survey_data.modules[module].questions[question_id]
        except KeyError:
            logger.error(f"Вопрос не найден: модуль={module}, id={question_id}")
            return None
    
    def get_level(self, module: str, question_id: int, level_index: int) -> Optional[Level]:
        """
        Получает уровень вопроса
        
        Args:
            module: Название модуля
            question_id: ID вопроса
            level_index: Индекс уровня
            
        Returns:
            Optional[Level]: Объект уровня или None, если не найден
        """
        question = self.get_question(module, question_id)
        if not question or not question.levels or level_index >= len(question.levels):
            return None
        return question.levels[level_index]
    
    def get_options_for_level(self, level: Level) -> List[str]:
        """
        Получает варианты ответов для уровня вопроса
        
        Args:
            level: Объект уровня
            
        Returns:
            List[str]: Список вариантов ответов
        """
        if level.options == "options_scale":
            return self.survey_data.options_scale
        elif isinstance(level.options, list):
            return level.options
        return []
    
    def get_next_question(self, module: str, current_question_id: int, answer: Any) -> Tuple[str, int]:
        """
        Определяет следующий вопрос на основе ответа на текущий
        
        Args:
            module: Текущий модуль
            current_question_id: ID текущего вопроса
            answer: Ответ на текущий вопрос
            
        Returns:
            Tuple[str, int]: (следующий модуль, ID следующего вопроса)
        """
        question = self.get_question(module, current_question_id)
        next_module = module
        next_question_id = None

        if not question:
            logger.error(f"Не удалось получить вопрос: модуль={module}, id={current_question_id}")
            return module, current_question_id

        # Логируем входные данные для отладки
        logger.info(f"get_next_question: module={module}, current_id={current_question_id}, answer={answer}")
        logger.info(f"get_next_question: if_conditions={question.if_conditions}")

        # Проверяем условные переходы
        if question.if_conditions and answer in question.if_conditions:
            next_info = question.if_conditions[answer]
            if "id" in next_info:
                next_question_id = next_info["id"]
                logger.info(f"Выполнен условный переход к вопросу {next_question_id}")

        # Если условный переход не задан, идем к следующему по порядку
        if next_question_id is None:
            module_questions = list(sorted(self.survey_data.modules[module].questions.keys()))
            current_index = module_questions.index(current_question_id)

            if current_index + 1 < len(module_questions):
                next_question_id = module_questions[current_index + 1]
            else:
                # Если текущий модуль закончился, переходим к следующему
                if module == "modul_1" and "modul_2" in self.survey_data.modules:
                    next_module = "modul_2"
                    next_question_id = min(self.survey_data.modules[next_module].questions.keys())
                else:
                    # Конец опроса
                    return None, None

        logger.info(f"Следующий вопрос: модуль={next_module}, id={next_question_id}")
        return next_module, next_question_id