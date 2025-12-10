"""Модуль конфигурации для JiraTasksUpdate.

Этот модуль отвечает за загрузку и парсинг конфигурации из YAML-файла,
а также управление переменными окружения для хранения чувствительных данных
типа API-токенов.

Примеры использования:
    config = Config('config.yaml')
    jira_server = config.get('jira.server')
    jira_token = config.get_jira_token()  # из переменной окружения
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class Config:
    """Контейнер конфигурации с поддержкой переменных окружения.
    
    Загружает конфигурацию из YAML-файла и предоставляет методы доступа
    к значениям с использованием dot-нотации (например, 'jira.server').
    Также поддерживает загрузку чувствительных данных из переменных окружения.
    """

    def __init__(self, config_path: str = "config.yaml"):
        """Инициализация конфигурации.

        Args:
            config_path: Путь к YAML-файлу конфигурации.

        Raises:
            FileNotFoundError: Если файл конфигурации не найден.
            yaml.YAMLError: Если YAML имеет синтаксические ошибки.
        """
        self.config_path = Path(config_path)

        # Проверяем наличие файла конфигурации
        if not self.config_path.exists():
            raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")

        # Загружаем YAML-файл
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.data: Dict[str, Any] = yaml.safe_load(f) or {}

        logger.info("Конфигурация загружена из %s", config_path)

    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение конфигурации используя dot-нотацию.

        Поддерживает иерархический доступ к значениям через точку.
        Например: 'jira.server', 'telegram.users.main_id'

        Args:
            key: Ключ в формате 'section.subsection.key'
            default: Значение по умолчанию если ключ не найден

        Returns:
            Значение из конфигурации или default если не найдено

        Examples:
            >>> config.get('jira.server')
            'https://jira.o3.ru'
            >>> config.get('telegram.users.main_id')
            105517177
            >>> config.get('nonexistent.key', 'fallback')
            'fallback'
        """
        keys = key.split(".")
        value = self.data

        try:
            # Проходим по иерархии ключей
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            # Если ключ не найден, возвращаем значение по умолчанию
            return default

    def get_jira_token(self) -> str:
        """Получить Jira API-токен из переменной окружения.

        Ищет переменную окружения, указанную в конфигурации
        (по умолчанию 'JIRA_TOKEN').

        Returns:
            API-токен для Jira

        Raises:
            ValueError: Если переменная окружения не установлена
        """
        env_var = self.get("jira.token_env_var", "JIRA_TOKEN")
        token = os.getenv(env_var)

        if not token:
            raise ValueError(f"Jira токен не найден в переменной окружения {env_var}")

        return token

    def get_tg_token(self) -> str:
        """Получить Telegram Bot токен из переменной окружения.

        Ищет переменную окружения, указанную в конфигурации
        (по умолчанию 'TG_TOKEN').

        Returns:
            Токен бота Telegram

        Raises:
            ValueError: Если переменная окружения не установлена
        """
        env_var = self.get("telegram.token_env_var", "TG_TOKEN")
        token = os.getenv(env_var)

        if not token:
            raise ValueError(f"Telegram токен не найден в переменной окружения {env_var}")

        return token

    def get_sleep_hours(self) -> set[int]:
        """Получить часы сна в виде множества.

        Парсит список часов из конфигурации, когда бот должен спать.

        Returns:
            Множество часов (0-23) когда бот неактивен
        """
        hours = self.get("time_control.sleep_hours", [])
        return set(hours) if isinstance(hours, list) else set()

    def get_skip_issue_keys(self) -> set[str]:
        """Получить точные ключи задач для пропуска.

        Returns:
            Множество ключей задач типа {"SD911-2689821"}
        """
        keys = self.get("skip_rules.issue_keys", [])
        return set(keys) if isinstance(keys, list) else set()

    def get_skip_comment_keywords(self) -> set[str]:
        """Получить ключевые слова в комментариях для пропуска задач.

        Если любое из этих слов найдено в комментариях задачи,
        задача будет пропущена.

        Returns:
            Множество ключевых слов
        """
        keywords = self.get("skip_rules.comment_keywords", [])
        return set(keywords) if isinstance(keywords, list) else set()

    def get_skip_name_keywords(self) -> set[str]:
        """Получить ключевые слова в названии задачи для пропуска.

        Поиск выполняется без учёта регистра (case-insensitive).

        Returns:
            Множество ключевых слов
        """
        keywords = self.get("skip_rules.name_keywords", [])
        return set(keywords) if isinstance(keywords, list) else set()

    def get_skip_creators(self) -> set[str]:
        """Получить список создателей для пропуска задач.

        Если создатель задачи в этом списке, задача будет пропущена.

        Returns:
            Множество имён пользователей
        """
        creators = self.get("skip_rules.creator_list", [])
        return set(creators) if isinstance(creators, list) else set()

    def get_assignees(self) -> list[tuple[str, int]]:
        """Получить список исполнителей для ротации.

        Возвращает список пар (имя_пользователя, chat_id_для_уведомления)
        для циклического распределения задач.

        Returns:
            Список кортежей (username, notify_chat_id)
        """
        rotation = self.get("assignee.rotation", [])
        return [(item["username"], item["notify_chat_id"]) for item in rotation]

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Проверить, включена ли фича.

        Позволяет динамически включать/выключать функциональность
        через конфигурацию без изменения кода.

        Args:
            feature_name: Имя фичи (например, "main_loop", "updates_watcher")

        Returns:
            True если фича включена, False иначе
        """
        return self.get(f"features.{feature_name}", True)

    def __repr__(self) -> str:
        return f"Config({self.config_path})"


def setup_logging(config: Config) -> None:
    """Настроить логирование на основе конфигурации.

    Настраивает логирование в консоль и файл с ротацией по размеру.
    Максимальный размер файла и количество резервных копий
    берутся из конфигурации.

    Args:
        config: Объект конфигурации
    """
    import logging.handlers

    # Получаем параметры логирования из конфигурации
    log_level = config.get("logging.level", "INFO")
    log_format = config.get("logging.format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    log_file = config.get("logging.file", "logs/jira_updater.log")
    max_file_size = config.get("logging.max_file_size", 10485760)  # 10 MB
    backup_count = config.get("logging.backup_count", 5)

    # Создаём директорию для логов если её нет
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Получаем root логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Удаляем старые хендлеры (если были)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Хендлер для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # Хендлер для записи в файл с ротацией по размеру
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_file_size, backupCount=backup_count
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    logger.info("Логирование настроено: уровень=%s, файл=%s", log_level, log_file)
