"""Command-line interface for JiraTasksUpdate."""

import argparse
import logging
import sys
from typing import Optional

from config import Config, setup_logging

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description="JiraTasksUpdate - Automated Jira task processor with Telegram notifications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default config
  python cli.py
  
  # Run in dry-run mode (no actual assignments)
  python cli.py --dry-run
  
  # Run once and exit (cron mode)
  python cli.py --once
  
  # Run with debug logging
  python cli.py --log-level DEBUG
  
  # Custom config file
  python cli.py --config my_config.yaml
  
  # Run specific project
  python cli.py --project TSK
        """,
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Override logging level from config",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making actual changes (no Jira updates, no TG messages)",
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Process issues once and exit (useful for cron)",
    )

    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Disable Telegram bot notifications",
    )

    parser.add_argument(
        "--no-time-control",
        action="store_true",
        help="Disable sleep/wake time control (run 24/7)",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Override polling interval (in seconds) for new issues",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 2.0.0",
    )

    return parser


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Parsed arguments namespace.
    """
    parser = create_parser()
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = parse_args(argv)

    try:
        # Load configuration
        config = Config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    # Setup logging
    if args.log_level:
        # Override config logging level
        config.data["logging"]["level"] = args.log_level

    setup_logging(config)

    logger.info("JiraTasksUpdate started")
    logger.info("Configuration: %s", config)
    logger.info("CLI arguments: %s", args)

    if args.dry_run:
        logger.warning("DRY-RUN MODE: No actual changes will be made")

    # Import here to avoid circular imports
    from test import JiraTaskUpdater
    from jira.client import JIRA
    import telebot

    try:
        # Initialize Jira client
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
        # Initialize Telegram bot
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

    # Get user IDs
    main_id = config.get("telegram.users.main_id", 105517177)
    vovan_id = config.get("telegram.users.secondary_id", 1823360851)

    # Create updater
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
            # Run once and exit (cron mode)
            logger.info("Running in ONCE mode (cron)")
            updater.process_once()
            logger.info("Done. Exiting.")
            return 0
        else:
            # Normal mode: start background threads
            logger.info("Starting background threads")
            updater.start()

            # Keep main thread alive
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
