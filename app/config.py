"""Конфигурация приложения"""
import os
from pathlib import Path


class Config:
    """Конфигурация приложения"""
    
    # Пути к файлам и директориям
    BASE_DIR = Path(__file__).parent
    DATA_FILE = os.path.join(BASE_DIR, 'data', 'ovz.json')
    IMAGES_DIR = os.path.join(BASE_DIR, 'images')
    
    # Логирование
    LOG_LEVEL = "INFO"
    
    # Параметры опроса
    DEFAULT_MODULE = "modul_1"
    DEFAULT_QUESTION_ID = 1