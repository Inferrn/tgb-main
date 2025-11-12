"""Загрузка данных опроса из JSON файла"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from app.data.data_models import SurveyData, Module, Question, Level


def _convert_to_level(level_data: Dict[str, Any]) -> Level:
    """Преобразует словарь в объект Level"""
    return Level(
        options=level_data.get("options", []),
        image=level_data.get("image"),
        height=level_data.get("height"),
        angle=level_data.get("angle"),
        surface=level_data.get("surface")
    )


def _convert_to_question(question_data: Dict[str, Any]) -> Question:
    """Преобразует словарь в объект Question"""
    levels = None
    if "levels" in question_data:
        levels = [_convert_to_level(level) for level in question_data["levels"]]

    return Question(
        id=question_data["id"],
        text=question_data["text"],
        type=question_data["type"],
        options=question_data.get("options"),
        levels=levels,
        if_conditions=question_data.get("if"),
        image=question_data.get("image")
    )


def load_survey_data(file_path: str) -> SurveyData:
    """
    Загружает данные опроса из JSON файла
    
    Args:
        file_path: Путь к JSON файлу
        
    Returns:
        SurveyData: Структурированные данные опроса
        
    Raises:
        FileNotFoundError: Если файл не найден
        ValueError: Если формат JSON некорректен
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            
            # Создаем модули с вопросами
            modules = {}
            # Ищем все модули в данных (ключи, начинающиеся с "modul_")
            module_names = [key for key in data.keys() if key.startswith("modul_")]
            for module_name in module_names:
                questions = {q["id"]: _convert_to_question(q) for q in data[module_name]}
                modules[module_name] = Module(questions=questions)

            # Заменяем в уровнях ссылочные строки типа "options_scale" на реальные массивы из корня JSON
            options_scale = data.get("options_scale", [])
            for module in modules.values():
                for q in module.questions.values():
                    if q.levels:
                        for lvl in q.levels:
                            # Если уровень хранит имя массива (строку), подставим реальный массив
                            if isinstance(lvl.options, str):
                                ref = lvl.options
                                if ref == "options_scale":
                                    lvl.options = options_scale
                                else:
                                    # если в будущем будут другие ссылки на корневые массивы
                                    replacement = data.get(ref)
                                    if isinstance(replacement, list):
                                        lvl.options = replacement
            
            # Создаем объект данных опроса
            return SurveyData(
                modules=modules,
                options_scale=data.get("options_scale", [])
            )
            
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл {file_path} не найден.")
    except json.JSONDecodeError:
        raise ValueError(f"Файл {file_path} содержит некорректный JSON.")
    except KeyError as e:
        raise ValueError(f"В файле отсутствует обязательное поле: {str(e)}")