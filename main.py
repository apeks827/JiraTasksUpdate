"""Legacy entry point for backward compatibility.

Prefers config.yaml if available, falls back to old hardcoded setup.
"""

import logging
import os
import sys
from pathlib import Path

try:
    from config import Config, setup_logging
except ImportError:
    logging.error("config.py not found. Please ensure config.py is in the same directory.")
    sys.exit(1)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Try to load config.yaml
    config_path = "config.yaml"
    config = None

    if Path(config_path).exists():
        try:
            config = Config(config_path)
            setup_logging(config)
            logger.info("Loaded configuration from %s", config_path)
        except Exception as e:  # noqa: BLE001
            logger.error("Error loading config: %s", e)
            sys.exit(1)
    else:
        # Fallback: setup basic logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        logger.warning("config.yaml not found, using fallback setup")

    # Import here to avoid circular imports
    from test import JiraTaskUpdater
    from jira.client import JIRA
    import telebot
    from dist import secrets

    # Initialize clients
    try:
        if config:
            jira_token = config.get_jira_token()
            tg_token = config.get_tg_token()
            jira_server = config.get("jira.server", "https://jira.o3.ru")
            my_id = config.get("telegram.users.main_id", 105517177)
            vovan_id = config.get("telegram.users.secondary_id", 1823360851)
        else:
            # Fallback to secrets module
            jira_token = secrets.api
            tg_token = secrets.tg
            jira_server = "https://jira.o3.ru"
            my_id = 105517177
            vovan_id = 1823360851

        jira = JIRA(server=jira_server, token_auth=jira_token)
        bot = telebot.TeleBot(tg_token)

        logger.info("Clients initialized successfully")
    except Exception as e:  # noqa: BLE001
        logger.exception("Error initializing clients: %s", e)
        sys.exit(1)

    # Create and start updater
    updater = JiraTaskUpdater(
        jira_client=jira,
        bot=bot,
        my_id=my_id,
        vovan_id=vovan_id,
        config=config,
    )

    logger.info("Starting JiraTasksUpdate...")
    updater.start()

    # Keep main thread alive
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, stopping...")
        updater.stop()
