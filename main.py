"""Легаси-точка входа для обратной совместимости.

Если есть config.yaml — пытается использовать его. Если нет —
падает обратно на старую схему с dist.secrets и базовым логированием.
"""

import logging
import os
import sys
from pathlib import Path

try:
    from config import Config, setup_logging
except ImportError:
    logging.error("config.py не найден. Убедитесь, что config.py лежит рядом с main.py.")
    sys.exit(1)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Пытаемся загрузить config.yaml
    config_path = "config.yaml"
    config = None

    if Path(config_path).exists():
        try:
            config = Config(config_path)
            setup_logging(config)
            logger.info("Конфигурация загружена из %s", config_path)
        except Exception as e:  # noqa: BLE001
            logger.error("Ошибка при загрузке конфигурации: %s", e)
            sys.exit(1)
    else:
        # Фоллбек: базовая настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        logger.warning("config.yaml не найден, используется fallback-настройка")

    # Импортируем здесь, чтобы избежать циклических импортов
    from test import JiraTaskUpdater
    from jira.client import JIRA
    import telebot
    from dist import secrets

    # Инициализируем клиенты Jira и Telegram
    try:
        if config:
            jira_token = config.get_jira_token()
            tg_token = config.get_tg_token()
            jira_server = config.get("jira.server", "https://jira.o3.ru")
            my_id = config.get("telegram.users.main_id", 105517177)
            vovan_id = config.get("telegram.users.secondary_id", 1823360851)
        else:
            # Фоллбек на модуль secrets (старый способ)
            jira_token = secrets.api
            tg_token = secrets.tg
            jira_server = "https://jira.o3.ru"
            my_id = 105517177
            vovan_id = 1823360851

        jira = JIRA(server=jira_server, token_auth=jira_token)
        bot = telebot.TeleBot(tg_token)

        logger.info("Клиенты Jira и Telegram успешно инициализированы")
    except Exception as e:  # noqa: BLE001
        logger.exception("Ошибка инициализации клиентов: %s", e)
        sys.exit(1)

    # Создаём и запускаем updater
    updater = JiraTaskUpdater(
        jira_client=jira,
        bot=bot,
        my_id=my_id,
        vovan_id=vovan_id,
        config=config,
    )

    logger.info("Starting JiraTasksUpdate...")
    updater.start()

    # Держим главный поток живым, пока не придёт Ctrl+C
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Получен KeyboardInterrupt, останавливаемся...")
        updater.stop()
