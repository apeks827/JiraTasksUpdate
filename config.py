"""Configuration loader for JiraTasksUpdate."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


class Config:
    """Configuration container with environment variable support."""

    def __init__(self, config_path: str = "config.yaml"):
        """Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml file.

        Raises:
            FileNotFoundError: If config file not found.
            yaml.YAMLError: If YAML is malformed.
        """
        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            self.data: Dict[str, Any] = yaml.safe_load(f) or {}

        logger.info("Configuration loaded from %s", config_path)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation.

        Examples:
            config.get("jira.server")
            config.get("telegram.users.main_id")
            config.get("logging.level", default="INFO")
        """
        keys = key.split(".")
        value = self.data

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_jira_token(self) -> str:
        """Get Jira API token from env variable or config.

        Returns:
            API token string.

        Raises:
            ValueError: If token not found.
        """
        env_var = self.get("jira.token_env_var", "JIRA_TOKEN")
        token = os.getenv(env_var)

        if not token:
            raise ValueError(f"Jira token not found in {env_var} environment variable")

        return token

    def get_tg_token(self) -> str:
        """Get Telegram bot token from env variable or config.

        Returns:
            Bot token string.

        Raises:
            ValueError: If token not found.
        """
        env_var = self.get("telegram.token_env_var", "TG_TOKEN")
        token = os.getenv(env_var)

        if not token:
            raise ValueError(f"Telegram token not found in {env_var} environment variable")

        return token

    def get_sleep_hours(self) -> set[int]:
        """Get sleep hours as a set.

        Returns:
            Set of hours (0-23) when bot should sleep.
        """
        hours = self.get("time_control.sleep_hours", [])
        return set(hours) if isinstance(hours, list) else set()

    def get_skip_issue_keys(self) -> set[str]:
        """Get issue keys to skip.

        Returns:
            Set of issue keys (e.g., {"SD911-2689821"}).
        """
        keys = self.get("skip_rules.issue_keys", [])
        return set(keys) if isinstance(keys, list) else set()

    def get_skip_comment_keywords(self) -> set[str]:
        """Get keywords that trigger skip when found in comments.

        Returns:
            Set of keywords.
        """
        keywords = self.get("skip_rules.comment_keywords", [])
        return set(keywords) if isinstance(keywords, list) else set()

    def get_skip_name_keywords(self) -> set[str]:
        """Get keywords that trigger skip when found in issue name.

        Returns:
            Set of keywords.
        """
        keywords = self.get("skip_rules.name_keywords", [])
        return set(keywords) if isinstance(keywords, list) else set()

    def get_skip_creators(self) -> set[str]:
        """Get creator names to skip.

        Returns:
            Set of creator usernames.
        """
        creators = self.get("skip_rules.creator_list", [])
        return set(creators) if isinstance(creators, list) else set()

    def get_assignees(self) -> list[tuple[str, int]]:
        """Get list of (username, chat_id) for rotation.

        Returns:
            List of (username, notify_chat_id) tuples.
        """
        rotation = self.get("assignee.rotation", [])
        return [(item["username"], item["notify_chat_id"]) for item in rotation]

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if feature is enabled.

        Args:
            feature_name: Feature key (e.g., "main_loop", "updates_watcher").

        Returns:
            True if feature is enabled, False otherwise.
        """
        return self.get(f"features.{feature_name}", True)

    def __repr__(self) -> str:
        return f"Config({self.config_path})"


def setup_logging(config: Config) -> None:
    """Configure Python logging based on config.

    Args:
        config: Config instance.
    """
    import logging.handlers

    log_level = config.get("logging.level", "INFO")
    log_format = config.get("logging.format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    log_file = config.get("logging.file", "logs/jira_updater.log")
    max_file_size = config.get("logging.max_file_size", 10485760)  # 10 MB
    backup_count = config.get("logging.backup_count", 5)

    # Create logs directory if needed
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_file_size, backupCount=backup_count
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    logger.info("Logging configured: level=%s, file=%s", log_level, log_file)
