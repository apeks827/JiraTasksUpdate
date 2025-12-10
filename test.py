import logging
import threading
import time
from datetime import datetime
from threading import Timer

from aiogram.utils.markdown import hlink
from jira.client import JIRA
import telebot
from telebot import types

from dist import secrets


class JiraTaskUpdater:
    def __init__(self, jira_client: JIRA, bot: telebot.TeleBot, my_id: int, vovan_id: int):
        self.jira = jira_client
        self.bot = bot
        self.my_id = my_id
        self.vovan_id = vovan_id

        # state
        self.running_main_loop = True
        self.running_by_time = True
        self.to_assign = 0
        self.to_skip = {"SD911-2689821"}

        # counters for self-reset
        self.main_loop_call_count = 0
        self.search_updates_call_count = 0

        # threads
        self.thread_main_loop = threading.Thread(target=self.loop, name="main_loop", daemon=True)
        self.thread_check_updates = threading.Thread(target=self.search_updates_timeout, name="updates_loop", daemon=True)
        self.thread_tg_bot = threading.Thread(target=self.bot.infinity_polling, name="tg_bot", daemon=True)
        self.thread_time_loop = threading.Thread(target=self.check_time, name="time_loop", daemon=True)

        # logger
        self.logger = logging.getLogger(__name__)

    # --- public API ---

    def start(self) -> None:
        """Start all background threads."""
        self.logger.info("Starting JiraTaskUpdater threads")
        self.thread_main_loop.start()
        self.thread_check_updates.start()
        self.thread_tg_bot.start()
        self.thread_time_loop.start()

    def stop(self) -> None:
        """Signal threads to stop gracefully."""
        self.logger.info("Stopping JiraTaskUpdater")
        self.running_main_loop = False
        self.running_by_time = False

    # --- internal helpers ---

    def _toggle_main_loop(self, value: bool) -> None:
        self.logger.info("Set running_main_loop=%s", value)
        self.running_main_loop = value

    def _toggle_by_time(self, value: bool) -> None:
        self.logger.info("Set running_by_time=%s", value)
        self.running_by_time = value

    # --- core Jira polling loop ---

    def loop(self) -> None:
        self.main_loop_call_count += 1

        if self.main_loop_call_count > 10:
            self.logger.warning("main loop call count exceeded, reset")
            self.main_loop_call_count = 0
            Timer(5, self.loop).start()
            return

        try:
            while True:
                self.logger.info("Start searching new issues...")

                new_issues = self.jira.search_issues(
                    'project = SD911 AND status = "Ожидает обработки" AND assignee in (EMPTY) AND "Группа '
                    'исполнителей" = TS_TMB_team'
                )

                if not new_issues:
                    self.logger.info("No new issues")

                if not self.running_main_loop or not self.running_by_time:
                    self.logger.info("Main loop stopped by flags")
                    self.logger.info("-------------------------------------------------------------------------------")
                    break

                for issue in new_issues:
                    self._process_new_issue(issue)

                self.logger.info("-------------------------------------------------------------------------------")
                time.sleep(10)

        except Exception as err:  # noqa: BLE001
            self.logger.exception("Failure to check new issues: %s", err)
            if self.running_main_loop:
                Timer(15, self.loop).start()

    def _process_new_issue(self, issue) -> None:
        true_issue = str(issue)

        if true_issue in self.to_skip:
            self.logger.info("Issue %s in skip list", true_issue)
            return

        fields = issue.raw["fields"]
        issue_creator = fields["creator"]["name"]
        issue_name = fields["summary"]
        comments_raw = fields["comment"]["comments"]
        comments = "".join(map(str, comments_raw))

        self.logger.info("Issue: %s | name: %s", issue, issue_name)

        names_to_skip = {"isuvorinov", "alpechenin", "vivashov", "asmolensky", "otitov"}
        if any(name in comments for name in names_to_skip):
            self.logger.info("Skip %s by comments conditions", issue)
            self.to_skip.add(true_issue)
            return

        skip_name_keywords = ("пропуск", "скуд", "возврат", "предостав", "ноутбук")
        skip_creators = {"vivashov", "ivsuvorinov", "otitov"}

        if (
            any(word in issue_name.lower() for word in skip_name_keywords)
            or issue_creator in skip_creators
        ):
            self.logger.info("Skip %s by issue_name/creator conditions", issue)
            self.to_skip.add(true_issue)
            return

        self._assign_issue(issue, issue_creator, issue_name)

    def _assign_issue(self, issue, creator: str, name: str) -> None:
        try:
            self.jira.transition_issue(issue, "21")
            assignee = issue.raw["fields"]["assignee"]
            self.logger.info("Assigned to %s", assignee)

            if self.to_assign == 0:
                self._safe_send_message(self.my_id, issue, creator, name)
                self._reassign_if_needed(issue, "sergmakarov")
                self.to_assign = 1
            else:
                self._safe_send_message(self.vovan_id, issue, creator, name)
                self._reassign_if_needed(issue, "vivashov")
                self.to_assign = 0

        except Exception as err:  # noqa: BLE001
            self.logger.exception("Error changing status: %s", err)

    def _safe_send_message(self, chat_id: int, issue, creator: str, name: str) -> None:
        try:
            self.send_message(chat_id, issue, creator, name)
        except Exception as err:  # noqa: BLE001
            self.logger.exception("Error sending message: %s", err)

    def _reassign_if_needed(self, issue, expected_assignee: str) -> None:
        current_assignee = issue.raw["fields"].get("assignee")
        if current_assignee != expected_assignee:
            self.jira.assign_issue(issue, expected_assignee)
            self.logger.info("Reassigned to %s", expected_assignee)

    # --- updates watcher ---

    def search_updates_timeout(self) -> None:
        self.search_updates_call_count += 1

        if self.search_updates_call_count > 10:
            self.logger.warning("search_updates_timeout call count exceeded, stop")
            return

        try:
            while True:
                time.sleep(300)
                self.logger.info("Start searching updates...")

                new_issues = self.jira.search_issues(
                    "updatedDate >= -6m and key in watchedIssues() AND status not in (Обработано, Закрыто, Отменено)"
                )

                if not new_issues:
                    self.logger.info("No new updates")

                for issue in new_issues:
                    fields = issue.raw["fields"]
                    issue_creator = fields["creator"]["name"]
                    issue_name = fields["summary"]
                    self.logger.info("Updated issue: %s", issue)
                    self._safe_send_message_updates(issue, issue_creator, issue_name)

                self.logger.info("-------------------------------------------------------------------------------")

        except Exception as err:  # noqa: BLE001
            self.logger.exception("Failure in updates watcher: %s", err)
            Timer(30, self.search_updates_timeout).start()

    def _safe_send_message_updates(self, issue, creator: str, name: str) -> None:
        try:
            self.send_message_updates(issue, creator, name)
        except Exception as err:  # noqa: BLE001
            self.logger.exception("Error sending update message: %s", err)

    # --- Jira helpers (lists) ---

    def _get_list(self, issues_raw):
        issues = []
        creators = []
        names = []
        for issue in issues_raw:
            fields = issue.raw["fields"]
            creators.append(fields["creator"]["name"])
            names.append(fields["summary"])
            issues.append(issue.key)
        return issues, creators, names

    def new_issues_ondesk(self):
        new_issues = self.jira.search_issues(
            'project = SD911 AND status = "Ожидает обработки" AND assignee in (EMPTY) AND "Группа '
            'исполнителей" = TS_TMB_team'
        )
        return self._get_list(new_issues)

    def issues_on_me(self):
        raw = self.jira.search_issues(
            'status in ("Ожидает обработки", "Повторно открыта", "Ожидает разработки", Уточнено, '
            '"В работе", Согласовано) AND assignee in (currentUser())'
        )
        self.logger.info("issues_on_me raw: %s", raw)
        return self._get_list(raw)

    def search_updates(self):
        raw = self.jira.search_issues(
            'updatedDate >= -4d and key in watchedIssues() AND status not in (Обработано, '
            "Закрыто, Отменено)"
        )
        return self._get_list(raw)

    # --- Telegram helpers ---

    def send_message(self, to_send_id: int, issue, creator: str, name: str) -> None:
        answer = hlink(f"{issue}: {name}", f"https://jira.ozon.ru/browse/{issue}")
        teams_link = hlink(creator, f"https://teams.microsoft.com/l/chat/0/0?users={creator}@ozon.ru")
        self.bot.send_message(to_send_id, f"Hi! There is a new issue: {answer} from: {teams_link}", parse_mode="HTML")

    def send_message_updates(self, issue, creator: str, name: str) -> None:
        answer = hlink(f"{issue}: {name}", f"https://jira.ozon.ru/browse/{issue}")
        self.bot.send_message(self.my_id, f"Hi! There is a new update: {answer} from {creator}", parse_mode="HTML")

    def got_err(self, err) -> None:
        self.bot.send_message(self.my_id, f"Got err, check: {err}")

    # --- time-based control ---

    def check_time(self) -> None:
        flag = False
        sleep_hours = {23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}

        while True:
            current_time = datetime.now()
            self.logger.info("Hour is %s", current_time.hour)

            if current_time.hour in sleep_hours:
                self.logger.info("Sleep mode")
                flag = False
                self._toggle_by_time(False)
            else:
                if current_time.hour == 11 and not flag:
                    flag = True
                    self._toggle_by_time(False)
                    time.sleep(11)
                    self._toggle_by_time(True)
                    self.loop()

            time.sleep(300)


# --- module-level setup to preserve behaviour ---

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

jira_client = JIRA(
    server="https://jira.o3.ru",
    token_auth=secrets.api,
)

bot = telebot.TeleBot(secrets.tg)

MY_ID = 105517177
VOVAN_ID = 1823360851

updater = JiraTaskUpdater(jira_client=jira_client, bot=bot, my_id=MY_ID, vovan_id=VOVAN_ID)


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):  # noqa: D401
    """Handle /start and /help commands."""
    if message.chat.id != MY_ID:
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    itembtn1 = types.KeyboardButton("Issues on me")
    itembtn2 = types.KeyboardButton("-")
    itembtn3 = types.KeyboardButton("Updates")
    markup.add(itembtn1, itembtn2, itembtn3)

    bot.send_message(message.chat.id, "Choose what you want:", reply_markup=markup)

    if not updater.running_main_loop:
        updater._toggle_main_loop(True)
        updater.logger.info("Restart main loop from /start")
        Timer(1, updater.loop).start()


@bot.message_handler(content_types=["text"])
def handle_text(message):
    if message.chat.id != MY_ID:
        return

    keyboard = telebot.types.InlineKeyboardMarkup()
    buttons_in_row = 1
    buttons_added = []

    if message.text == "Issues on me":
        issues, _, names = updater.issues_on_me()
        if not names:
            bot.send_message(MY_ID, text="Nothing!")
        else:
            for issue, issue_name in zip(issues, names):
                buttons_added.append(
                    telebot.types.InlineKeyboardButton(
                        f"{issue}: {issue_name}", url=f"https://jira.ozon.ru/browse/{issue}",
                    )
                )
                if len(buttons_added) == buttons_in_row:
                    keyboard.add(*buttons_added)
                    buttons_added = []
            bot.send_message(MY_ID, text="Issues on me:", reply_markup=keyboard)

    elif message.text == "-":
        answer = hlink("/start", "/start")
        bot.send_message(
            MY_ID,
            f"Click start to open again: {answer}",
            parse_mode="HTML",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        updater._toggle_main_loop(False)

    elif message.text == "Updates":
        issues, _, names = updater.search_updates()
        if not issues:
            bot.send_message(MY_ID, text="Nothing!")
        else:
            for issue, issue_name in zip(issues, names):
                buttons_added.append(
                    telebot.types.InlineKeyboardButton(
                        f"{issue}: {issue_name}", url=f"https://jira.ozon.ru/browse/{issue}",
                    )
                )
                if len(buttons_added) == buttons_in_row:
                    keyboard.add(*buttons_added)
                    buttons_added = []
            bot.send_message(MY_ID, text="Last updates:", reply_markup=keyboard)


# start background processing (preserve old behaviour)
updater.start()
