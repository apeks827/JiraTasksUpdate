"""CLI (командный интерфейс) для JiraTasksUpdate.

Этот модуль позволяет запускать бота из командной строки с различными
режимами: обычный запуск, dry-run, единичный прогон (cron), отключение
Telegram и time-контроля и т.п.
"""

import argparse
import logging
import sys
from typing import Optional

from config import Config, setup_logging

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов командной строки.

    Returns:
        Настроенный экземпляр ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        description="JiraTasksUpdate - Автоматизированный обработчик задач Jira с уведомлениями в Telegram",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Запуск с конфигом по умолчанию
  python cli.py
  
  # Сухой прогон (без реальных назначений и уведомлений)
  python cli.py --dry-run
  
  # Одноразовый запуск и выход (режим cron)
  python cli.py --once
  
  # Запуск с уровнем логирования DEBUG
  python cli.py --log-level DEBUG
  
  # Использовать кастомный конфиг-файл
  python cli.py --config my_config.yaml
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Путь к файлу конфигурации (по умолчанию: config.yaml)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Переопределить уровень логирования из config.yaml",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Запуск без реальных изменений (без переходов статусов и отправки сообщений)",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Обработать задачи один раз и завершиться (подходит для cron)",
    )

    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Отключить отправку уведомлений в Telegram",
    )

    parser.add_argument(
        "--no-time-control",
        action="store_true",
        help="Отключить контроль по времени (бот работает 24/7)",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Переопределить интервал поллинга новых задач (в секундах)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0",
    )

    return parser


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Распарсить аргументы командной строки.

    Args:
        argv: Список аргументов (по умолчанию sys.argv[1:]).

    Returns:
        Пространство имён с распарсенными аргументами.
    """
    parser = create_parser()
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Основная точка входа CLI.

    Args:
        argv: Список аргументов (по умолчанию sys.argv[1:]).

    Returns:
        Код выхода (0 при успехе, 1 при ошибке).
    """
    args = parse_args(argv)

    try:
        # Загружаем конфигурацию
        config = Config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    # Настраиваем логирование
    if args.log_level:
        # Переопределяем уровень логирования из конфигурации
        config.data.setdefault("logging", {})["level"] = args.log_level

    setup_logging(config)

    logger.info("JiraTasksUpdate started")
    logger.info("Configuration: %s", config)
    logger.info("CLI arguments: %s", args)

    if args.dry_run:
        logger.warning("DRY-RUN MODE: реальных изменений производиться не будет")

    # Импортируем здесь, чтобы избежать циклических импортов
    from test import JiraTaskUpdater
    from jira.client import JIRA
    import telebot

    try:
        # Инициализируем Jira-клиент
        jira_token = config.get_jira_token()
        jira = JIRA(server=config.get("jira.server"), token_auth=jira_token)
        logger.info("Jira client initialized")
    except ValueError as e:
        logger.error("%s", e)
        return 1
    except Exception as e:  # noqa: BLE001
        logger.exception("Error initializing Jira client: %s", e)
        return 1

    try:
        # Инициализируем Telegram-бота (если не отключен флагом)
        if not args.no_telegram:
            tg_token = config.get_tg_token()
            bot = telebot.TeleBot(tg_token)
            logger.info("Telegram bot initialized")
        else:
            bot = None
            logger.info("Telegram bot disabled")
    except ValueError as e:
        logger.error("%s", e)
        return 1
    except Exception as e:  # noqa: BLE001
        logger.exception("Error initializing Telegram bot: %s", e)
        return 1

    # Получаем ID пользователей из конфигурации
    main_id = config.get("telegram.users.main_id", 105517177)
    vovan_id = config.get("telegram.users.secondary_id", 1823360851)

    # Создаём экземпляр JiraTaskUpdater
    updater = JiraTaskUpdater(
        jira_client=jira,
        bot=bot,
        my_id=main_id,
        vovan_id=vovan_id,
        config=config,
        dry_run=args.dry_run,
    )

    try:
        if args.once:
            # Режим однократного прогона (cron)
            logger.info("Running in ONCE mode (cron)")
            updater.process_once()
            logger.info("Done. Exiting.")
            return 0
        else:
            # Обычный режим: запускаем фоновые потоки
            logger.info("Starting background threads")
            updater.start()

            # Держим главный поток живым, пока не придёт Ctrl+C
            import time
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received KeyboardInterrupt, stopping...")
                updater.stop()
                return 0
    except Exception as e:  # noqa: BLE001
        logger.exception("Error during execution: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
