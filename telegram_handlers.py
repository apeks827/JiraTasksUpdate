"""Telegram-обработчики для JiraTasksUpdate.

Отдельный модуль, инкапсулирующий всю логику работы с Telegram:
- обработка команд /start и /help
- кнопки "Issues on me", "Updates", "Daily Report", "-"
- авторизация по chat_id

Позволяет держать основной класс JiraTaskUpdater чище и не завязывать
его на конкретные детали Telegram API.
"""

import logging
from typing import Optional

from aiogram.utils.markdown import hlink
from telebot import types

logger = logging.getLogger(__name__)


class TelegramHandlers:
    """Класс-обёртка для Telegram-обработчиков.

    Основная задача — связать TeleBot и JiraTaskUpdater так, чтобы
    вся логика обработки сообщений была сосредоточена в одном месте.
    """

    def __init__(self, updater, bot):
        """Инициализация обработчиков.

        Args:
            updater: Экземпляр JiraTaskUpdater
            bot: Экземпляр TeleBot
        """
        self.updater = updater
        self.bot = bot
        # Авторизованный пользователь (владелец бота)
        self.authorized_id = updater.my_id

    def is_authorized(self, chat_id: int) -> bool:
        """Проверить, имеет ли пользователь право пользоваться ботом.

        Сейчас авторизован только один пользователь (owner),
        но можно легко расширить до списка ID.

        Args:
            chat_id: Telegram chat ID пользователя

        Returns:
            True, если пользователь авторизован, иначе False
        """
        return chat_id == self.authorized_id

    def register_handlers(self) -> None:
        """Зарегистрировать все обработчики сообщений в боте.

        Подключает методы `handle_start` и `handle_message` к
        соответствующим хендлерам TeleBot.
        """
        self.bot.message_handler(commands=["start", "help"])(self.handle_start)
        self.bot.message_handler(content_types=["text"])(self.handle_message)
        logger.info("Telegram handlers registered")

    def handle_start(self, message) -> None:
        """Обработка команд /start и /help.

        Отображает главное меню и краткую справку по функциям бота.

        Args:
            message: Объект сообщения Telegram
        """
        if not self.is_authorized(message.chat.id):
            logger.warning("Unauthorized access attempt from %s", message.chat.id)
            self.bot.send_message(message.chat.id, "Access denied.")
            return

        # Клавиатура с основными командами
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        itembtn1 = types.KeyboardButton("Issues on me")
        itembtn2 = types.KeyboardButton("-")
        itembtn3 = types.KeyboardButton("Updates")
        itembtn4 = types.KeyboardButton("Daily Report")
        markup.add(itembtn1, itembtn2, itembtn3, itembtn4)

        help_text = (
            "JiraTasksUpdate Bot\n\n"
            "Команды:\n"
            "- **Issues on me**: показать мои задачи\n"
            "- **Updates**: показать обновления в watched задачах\n"
            "- **Daily Report**: сгенерировать и показать метрики за период\n"
            "- **-**: остановить основной цикл бота (graceful shutdown)"
        )

        self.bot.send_message(message.chat.id, help_text, reply_markup=markup)

        # Если основной цикл был остановлен — перезапускаем
        if not self.updater.running_main_loop:
            self.updater._toggle_main_loop(True)
            logger.info("Main loop restarted from /start")

    def handle_message(self, message) -> None:
        """Обработка всех текстовых сообщений.

        В зависимости от текста вызывает соответствующий приватный метод.

        Args:
            message: Объект сообщения Telegram
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
        """Показать список задач, назначенных на текущего пользователя.

        Строит inline-клавиатуру с кнопками-ссылками на задачи в Jira.

        Args:
            chat_id: Telegram chat ID, куда слать ответ
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
        """Показать список последних обновлений в watched задачах.

        Args:
            chat_id: Telegram chat ID, куда слать ответ
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
        """Сгенерировать и отправить краткий дневной отчёт в Telegram.

        Использует JiraReporter для расчёта метрик и отправляет
        краткую выжимку в текстовом виде.

        Args:
            chat_id: Telegram chat ID, куда слать отчёт
        """
        try:
            from reporting import JiraReporter

            logger.info("Generating daily report for %d", chat_id)

            # Получаем данные по задачам (используем дефолтные JQL из updater)
            new_issues_data = self.updater.jira.search_issues(
                'project = SD911 AND status = "Ожидает обработки" '
                'AND assignee in (EMPTY) AND "Группа исполнителей" = TS_TMB_team'
            )
            updates_data = self.updater.jira.search_issues(
                'updatedDate >= -4d AND key in watchedIssues() '
                'AND status not in (Обработано, Закрыто, Отменено)'
            )

            # Создаём репортера и считаем метрики
            reporter = JiraReporter()
            metrics = reporter.generate_metrics_report(
                new_issues_data, updates_data, {}
            )

            # Формируем человекочитаемый текст отчёта
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
        """Остановить основной цикл бота (graceful shutdown).

        Не завершает процесс полностью, но останавливает основной loop,
        чтобы бот перестал обрабатывать новые задачи.

        Args:
            chat_id: Telegram chat ID, куда слать уведомление
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
