"""Telegram bot handlers for JiraTasksUpdate.

Handles user commands and interactions with the Telegram bot.
Separated from main logic for better maintainability.
"""

import logging
from typing import Optional

from aiogram.utils.markdown import hlink
from telebot import types

logger = logging.getLogger(__name__)


class TelegramHandlers:
    """Encapsulates Telegram bot message handlers."""

    def __init__(self, updater, bot):
        """Initialize handlers.

        Args:
            updater: JiraTaskUpdater instance.
            bot: TeleBot instance.
        """
        self.updater = updater
        self.bot = bot
        self.authorized_id = updater.my_id

    def is_authorized(self, chat_id: int) -> bool:
        """Check if user is authorized.

        Args:
            chat_id: Telegram chat ID.

        Returns:
            True if authorized, False otherwise.
        """
        return chat_id == self.authorized_id

    def register_handlers(self) -> None:
        """Register all message handlers with the bot."""
        self.bot.message_handler(commands=["start", "help"])(self.handle_start)
        self.bot.message_handler(content_types=["text"])(self.handle_message)
        logger.info("Telegram handlers registered")

    def handle_start(self, message) -> None:
        """Handle /start and /help commands.

        Args:
            message: Telegram message object.
        """
        if not self.is_authorized(message.chat.id):
            logger.warning("Unauthorized access attempt from %s", message.chat.id)
            self.bot.send_message(message.chat.id, "Access denied.")
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        itembtn1 = types.KeyboardButton("Issues on me")
        itembtn2 = types.KeyboardButton("-")
        itembtn3 = types.KeyboardButton("Updates")
        itembtn4 = types.KeyboardButton("Daily Report")
        markup.add(itembtn1, itembtn2, itembtn3, itembtn4)

        help_text = (
            "JiraTasksUpdate Bot\n\n"
            "Commands:\n"
            "- **Issues on me**: Show my assigned issues\n"
            "- **Updates**: Show recent updates in watched issues\n"
            "- **Daily Report**: Generate and send daily metrics\n"
            "- **-**: Stop the bot (graceful shutdown)"
        )

        self.bot.send_message(message.chat.id, help_text, reply_markup=markup)

        if not self.updater.running_main_loop:
            self.updater._toggle_main_loop(True)
            logger.info("Main loop restarted from /start")

    def handle_message(self, message) -> None:
        """Handle text messages.

        Args:
            message: Telegram message object.
        """
        if not self.is_authorized(message.chat.id):
            return

        text = message.text

        if text == "Issues on me":
            self._show_issues_on_me(message.chat.id)
        elif text == "-":
            self._stop_bot(message.chat.id)
        elif text == "Updates":
            self._show_updates(message.chat.id)
        elif text == "Daily Report":
            self._show_daily_report(message.chat.id)
        else:
            self.bot.send_message(message.chat.id, "Unknown command. Use /start for help.")

    def _show_issues_on_me(self, chat_id: int) -> None:
        """Show user's assigned issues.

        Args:
            chat_id: Telegram chat ID.
        """
        try:
            issues, _, names = self.updater.issues_on_me()

            if not names:
                self.bot.send_message(chat_id, "No issues assigned to you.")
                return

            keyboard = types.InlineKeyboardMarkup()
            for issue, issue_name in zip(issues, names):
                button = types.InlineKeyboardButton(
                    f"{issue}: {issue_name[:40]}",
                    url=f"https://jira.ozon.ru/browse/{issue}",
                )
                keyboard.add(button)

            self.bot.send_message(chat_id, "Your assigned issues:", reply_markup=keyboard)
            logger.info("Sent 'issues on me' list to %d", chat_id)

        except Exception as e:  # noqa: BLE001
            logger.exception("Error showing issues on me: %s", e)
            self.bot.send_message(chat_id, f"Error: {e}")

    def _show_updates(self, chat_id: int) -> None:
        """Show recent updates.

        Args:
            chat_id: Telegram chat ID.
        """
        try:
            issues, _, names = self.updater.search_updates()

            if not issues:
                self.bot.send_message(chat_id, "No recent updates.")
                return

            keyboard = types.InlineKeyboardMarkup()
            for issue, issue_name in zip(issues, names):
                button = types.InlineKeyboardButton(
                    f"{issue}: {issue_name[:40]}",
                    url=f"https://jira.ozon.ru/browse/{issue}",
                )
                keyboard.add(button)

            self.bot.send_message(chat_id, "Recent updates:", reply_markup=keyboard)
            logger.info("Sent updates list to %d", chat_id)

        except Exception as e:  # noqa: BLE001
            logger.exception("Error showing updates: %s", e)
            self.bot.send_message(chat_id, f"Error: {e}")

    def _show_daily_report(self, chat_id: int) -> None:
        """Generate and send daily report.

        Args:
            chat_id: Telegram chat ID.
        """
        try:
            from reporting import JiraReporter

            logger.info("Generating daily report for %d", chat_id)

            # Fetch issues
            new_issues_data = self.updater.jira.search_issues(
                'project = SD911 AND status = "Ожидает обработки" '
                'AND assignee in (EMPTY) AND "Группа исполнителей" = TS_TMB_team'
            )
            updates_data = self.updater.jira.search_issues(
                'updatedDate >= -4d AND key in watchedIssues() '
                'AND status not in (Обработано, Закрыто, Отменено)'
            )

            # Create reporter and generate report
            reporter = JiraReporter()
            metrics = reporter.generate_metrics_report(
                new_issues_data, updates_data, {}
            )

            # Format metrics as text
            report_text = (
                f"**Daily Jira Metrics**\n\n"
                f"New Issues: {metrics['new_issues_count']}\n"
                f"Updated Issues: {metrics['updated_issues_count']}\n"
                f"Total: {metrics['total_issues']}\n\n"
            )

            if metrics.get("status_breakdown"):
                report_text += "**Status Breakdown:**\n"
                for status, count in metrics["status_breakdown"].items():
                    report_text += f"  {status}: {count}\n"
                report_text += "\n"

            if metrics.get("creator_breakdown"):
                report_text += "**Top Creators:**\n"
                sorted_creators = sorted(
                    metrics["creator_breakdown"].items(), key=lambda x: x[1], reverse=True
                )[:5]
                for creator, count in sorted_creators:
                    report_text += f"  {creator}: {count}\n"

            self.bot.send_message(chat_id, report_text)
            logger.info("Sent daily report to %d", chat_id)

        except Exception as e:  # noqa: BLE001
            logger.exception("Error generating daily report: %s", e)
            self.bot.send_message(chat_id, f"Error generating report: {e}")

    def _stop_bot(self, chat_id: int) -> None:
        """Stop the bot gracefully.

        Args:
            chat_id: Telegram chat ID.
        """
        answer = hlink("/start", "/start")
        self.bot.send_message(
            chat_id,
            f"Bot stopped. Click {answer} to resume.",
            parse_mode="HTML",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        self.updater._toggle_main_loop(False)
        logger.info("Bot stopped from chat %d", chat_id)
