"""Сервис для работы с изображениями"""
import os
from typing import Dict, Optional
from aiogram.types import FSInputFile
import logging

logger = logging.getLogger(__name__)


class ImageService:
    """Сервис для кеширования и получения изображений"""
    
    def __init__(self, images_dir: str):
        self.images_dir = images_dir
        self.image_cache = {}
        self._load_images()

    def _load_images(self):
        if not os.path.exists(self.images_dir):
            logger.warning(f"Папка с изображениями не найдена: {self.images_dir}")
            return
        
        for filename in os.listdir(self.images_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.jfif')):
                path = os.path.join(self.images_dir, filename)
                try:
                    key = filename.lower()
                    self.image_cache[key] = FSInputFile(path)
                    logger.info(f"Кешировано изображение: {key}")
                except Exception as e:
                    logger.error(f"Ошибка кеширования {filename}: {e}")

    def has_image(self, filename: str) -> bool:
        key = filename.lower()
        if key in self.image_cache:
            logger.info(f"Проверка изображения '{key}': найдено")
            return True

        # попробуем альтернативные расширения
        name, _ = os.path.splitext(key)
        for ext in ('.png', '.jpg', '.jpeg', '.jfif'):
            alt = name + ext
            if alt in self.image_cache:
                logger.info(f"Проверка изображения '{key}': найдено по альтернативному имени {alt}")
                return True

        # попытка найти по basename (устранение опечаток, например 'rafficlights.png' -> 'trafficlights.png')
        for cached in self.image_cache.keys():
            if os.path.splitext(cached)[0].endswith(name) or name.endswith(os.path.splitext(cached)[0]):
                logger.info(f"Проверка изображения '{key}': найдено по похожему имени {cached}")
                return True

        logger.info(f"Проверка изображения '{key}': не найдено")
        return False

    def get_image(self, filename: str) -> Optional[FSInputFile]:
        key = filename.lower()
        img = self.image_cache.get(key)
        if img:
            return img

        # альтернативные расширения
        name, _ = os.path.splitext(key)
        for ext in ('.png', '.jpg', '.jpeg', '.jfif'):
            alt = name + ext
            img = self.image_cache.get(alt)
            if img:
                logger.info(f"get_image: resolved {key} -> {alt}")
                return img

        # похожие имена (суффикс/префикс)
        for cached, imgf in self.image_cache.items():
            if os.path.splitext(cached)[0].endswith(name) or name.endswith(os.path.splitext(cached)[0]):
                logger.info(f"get_image: resolved {key} -> {cached}")
                return imgf

        logger.warning(f"Изображение '{key}' не найдено в кеше")
        return None
    