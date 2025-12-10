"""Main JiraTasksUpdate module with automated Jira task processing and Telegram notifications."""

import logging
import threading
import time
from datetime import datetime
from threading import Timer
from typing import Optional

from aiogram.utils.markdown import hlink
from jira.client import JIRA
import telebot
from telebot import types

logger = logging.getLogger(__name__)


class JiraTaskUpdater:
    """Main class for automated Jira task processing."""

    def __init__(
        self,
        jira_client: JIRA,
        bot: Optional[telebot.TeleBot],
        my_id: int,
        vovan_id: int,
        config=None,
        dry_run: bool = False,
    ):
        """Initialize JiraTaskUpdater.

        Args:
            jira_client: JIRA client instance.
            bot: Telegram bot instance (can be None).
            my_id: Primary user Telegram ID.
            vovan_id: Secondary user Telegram ID.
            config: Config object for settings (optional).
            dry_run: If True, no actual changes are made.
        """
        self.jira = jira_client
        self.bot = bot
        self.my_id = my_id
        self.vovan_id = vovan_id
        self.config = config
        self.dry_run = dry_run

        # State flags
        self.running_main_loop = True
        self.running_by_time = True
        self.to_assign = 0

        # Skip rules
        if config:
            self.to_skip = config.get_skip_issue_keys().copy()
            self.skip_comment_keywords = config.get_skip_comment_keywords()
            self.skip_name_keywords = config.get_skip_name_keywords()
            self.skip_creators = config.get_skip_creators()
            self.sleep_hours = config.get_sleep_hours()
            self.assignees = config.get_assignees()
        else:
            # Fallback to hardcoded defaults
            self.to_skip = {"SD911-2689821"}
            self.skip_comment_keywords = {"isuvorinov", "alpechenin", "vivashov", "asmolensky", "otitov"}
            self.skip_name_keywords = {"пропуск", "скуд", "возврат", "предостав", "ноутбук"}
            self.skip_creators = {"vivashov", "ivsuvorinov", "otitov"}
            self.sleep_hours = {23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
            self.assignees = [("sergmakarov", 105517177), ("vivashov", 1823360851)]

        # Counters for self-reset
        self.main_loop_call_count = 0
        self.search_updates_call_count = 0

        # Cache for processed issues (prevent duplicate notifications)
        self.processed_issues_cache = set()
        self.cache_expiry = {}

        # Threads
        self.thread_main_loop = threading.Thread(target=self.loop, name="main_loop", daemon=True)
        self.thread_check_updates = threading.Thread(target=self.search_updates_timeout, name="updates_loop", daemon=True)
        self.thread_tg_bot = threading.Thread(target=self._telegram_polling, name="tg_bot", daemon=True)
        self.thread_time_loop = threading.Thread(target=self.check_time, name="time_loop", daemon=True)

    def _telegram_polling(self) -> None:
        """Run Telegram bot polling."""
        if self.bot:
            try:
                self.bot.infinity_polling()
            except Exception as e:  # noqa: BLE001
                logger.exception("Telegram polling error: %s", e)

    # --- public API ---

    def start(self) -> None:
        """Start all background threads."""
        logger.info("Starting JiraTaskUpdater threads")
        if self.config and not self.config.is_feature_enabled("main_loop"):
            logger.info("Main loop is disabled in config")
        else:
            self.thread_main_loop.start()

        if self.config and not self.config.is_feature_enabled("updates_watcher"):
            logger.info("Updates watcher is disabled in config")
        else:
            self.thread_check_updates.start()

        if self.config and not self.config.is_feature_enabled("telegram_bot"):
            logger.info("Telegram bot is disabled in config")
        elif self.bot:
            self.thread_tg_bot.start()

        if self.config and not self.config.is_feature_enabled("time_control"):
            logger.info("Time control is disabled in config")
        else:
            self.thread_time_loop.start()

    def stop(self) -> None:
        """Signal threads to stop gracefully."""
        logger.info("Stopping JiraTaskUpdater")
        self.running_main_loop = False
        self.running_by_time = False

    def process_once(self) -> None:
        """Process issues once and return (useful for cron jobs).

        This is a synchronous, single-run mode that processes new issues and updates
        without starting any background threads.
        """
        logger.info("Processing issues once (cron mode)")
        try:
            self._process_new_issues_batch()
        except Exception as e:  # noqa: BLE001
            logger.exception("Error processing new issues: %s", e)

        try:
            self._process_updates_batch()
        except Exception as e:  # noqa: BLE001
            logger.exception("Error processing updates: %s", e)

    # --- internal helpers ---

    def _toggle_main_loop(self, value: bool) -> None:
        self.running_main_loop = value
        logger.info("Set running_main_loop=%s", value)

    def _toggle_by_time(self, value: bool) -> None:
        self.running_by_time = value
        logger.info("Set running_by_time=%s", value)

    def _is_cached(self, issue_key: str) -> bool:
        """Check if issue is in cache and not expired."""
        if issue_key not in self.processed_issues_cache:
            return False

        expiry = self.cache_expiry.get(issue_key)
        if expiry and time.time() < expiry:
            return True

        # Cache expired, remove it
        self.processed_issues_cache.discard(issue_key)
        self.cache_expiry.pop(issue_key, None)
        return False

    def _cache_issue(self, issue_key: str, ttl_seconds: int = 3600) -> None:
        """Add issue to cache with TTL (time to live)."""
        self.processed_issues_cache.add(issue_key)
        self.cache_expiry[issue_key] = time.time() + ttl_seconds
        logger.debug("Cached issue %s for %d seconds", issue_key, ttl_seconds)

    # --- core Jira polling logic ---

    def loop(self) -> None:
        """Main polling loop for new unassigned issues."""
        self.main_loop_call_count += 1

        if self.main_loop_call_count > (self.config.get("polling.max_call_count", 10) if self.config else 10):
            logger.warning("main_loop call count exceeded, reset")
            self.main_loop_call_count = 0
            Timer(5, self.loop).start()
            return

        try:
            while True:
                if not self.running_main_loop or not self.running_by_time:
                    logger.info("Main loop stopped by flags")
                    break

                self._process_new_issues_batch()

                interval = self.config.get("polling.new_issues_interval", 10) if self.config else 10
                time.sleep(interval)

        except Exception as e:  # noqa: BLE001
            logger.exception("Failure in main loop: %s", e)
            if self.running_main_loop:
                restart_delay = self.config.get("polling.restart_delay", 15) if self.config else 15
                Timer(restart_delay, self.loop).start()

    def _process_new_issues_batch(self) -> None:
        """Fetch and process batch of new unassigned issues."""
        logger.info("Start searching new issues...")

        try:
            jql = self.config.get("jira_search.new_issues_jql") if self.config else None
            if not jql:
                jql = (
                    'project = SD911 AND status = "Ожидает обработки" '
                    'AND assignee in (EMPTY) AND "Группа исполнителей" = TS_TMB_team'
                )
            new_issues = self.jira.search_issues(jql)

            if not new_issues:
                logger.info("No new issues")
                return

            logger.info("Found %d new issues", len(new_issues))
            for issue in new_issues:
                self._process_new_issue(issue)

        except Exception as e:  # noqa: BLE001
            logger.exception("Error fetching new issues: %s", e)

    def _process_new_issue(self, issue) -> None:
        """Process a single new issue: check skip conditions, assign if needed."""
        true_issue = str(issue)

        # Check cache and skip list
        if true_issue in self.to_skip:
            logger.info("Issue %s in permanent skip list", true_issue)
            return

        if self._is_cached(true_issue):
            logger.debug("Issue %s in cache, skip", true_issue)
            return

        fields = issue.raw["fields"]
        issue_creator = fields["creator"]["name"]
        issue_name = fields["summary"]
        comments_raw = fields["comment"]["comments"]
        comments = "".join(map(str, comments_raw))

        logger.info("Processing: %s | name: %s | creator: %s", issue, issue_name, issue_creator)

        # Check comment keywords
        if any(name in comments for name in self.skip_comment_keywords):
            logger.info("Skip %s: comment condition matched", issue)
            self._cache_issue(true_issue)
            return

        # Check name and creator conditions
        if (
            any(word in issue_name.lower() for word in self.skip_name_keywords)
            or issue_creator in self.skip_creators
        ):
            logger.info("Skip %s: name/creator condition matched", issue)
            self._cache_issue(true_issue)
            return

        # Assign issue
        self._assign_issue(issue, issue_creator, issue_name)
        self._cache_issue(true_issue, ttl_seconds=300)  # Cache for 5 minutes

    def _assign_issue(self, issue, creator: str, name: str) -> None:
        """Transition issue status and assign to next user in rotation."""
        try:
            transition_id = self.config.get("assignee.transition_id", "21") if self.config else "21"

            if not self.dry_run:
                self.jira.transition_issue(issue, transition_id)
                logger.info("Transitioned %s to status 'In Progress'", issue)
            else:
                logger.info("[DRY-RUN] Would transition %s to status 'In Progress'", issue)

            # Get next assignee
            assignee_username, chat_id = self.assignees[self.to_assign]
            self.to_assign = (self.to_assign + 1) % len(self.assignees)

            logger.info("Assigning to %s (notify: %d)", assignee_username, chat_id)

            if not self.dry_run:
                self._safe_send_message(chat_id, issue, creator, name)
                self._reassign_if_needed(issue, assignee_username)
            else:
                logger.info("[DRY-RUN] Would notify %d and assign to %s", chat_id, assignee_username)

        except Exception as e:  # noqa: BLE001
            logger.exception("Error assigning issue %s: %s", issue, e)

    def _reassign_if_needed(self, issue, expected_assignee: str) -> None:
        """Reassign issue if current assignee differs from expected."""
        try:
            current_assignee = issue.raw["fields"].get("assignee")
            if current_assignee != expected_assignee:
                self.jira.assign_issue(issue, expected_assignee)
                logger.info("Reassigned %s to %s", issue, expected_assignee)
        except Exception as e:  # noqa: BLE001
            logger.exception("Error reassigning issue: %s", e)

    def _safe_send_message(self, chat_id: int, issue, creator: str, name: str) -> None:
        """Send Telegram message safely with error handling."""
        try:
            self.send_message(chat_id, issue, creator, name)
        except Exception as e:  # noqa: BLE001
            logger.exception("Error sending message: %s", e)

    # --- updates watcher ---

    def search_updates_timeout(self) -> None:
        """Periodic watcher for updated issues."""
        self.search_updates_call_count += 1

        max_count = self.config.get("polling.max_call_count", 10) if self.config else 10
        if self.search_updates_call_count > max_count:
            logger.warning("search_updates_timeout call count exceeded, stop")
            return

        try:
            while True:
                interval = self.config.get("polling.updates_interval", 300) if self.config else 300
                time.sleep(interval)

                if not self.running_main_loop or not self.running_by_time:
                    break

                self._process_updates_batch()

        except Exception as e:  # noqa: BLE001
            logger.exception("Failure in updates watcher: %s", e)
            restart_delay = self.config.get("polling.restart_delay", 30) if self.config else 30
            Timer(restart_delay, self.search_updates_timeout).start()

    def _process_updates_batch(self) -> None:
        """Fetch and process batch of watched issue updates."""
        logger.info("Start searching updates...")

        try:
            jql = self.config.get("jira_search.updates_jql") if self.config else None
            if not jql:
                jql = (
                    "updatedDate >= -6m AND key in watchedIssues() "
                    "AND status not in (Обработано, Закрыто, Отменено)"
                )
            new_issues = self.jira.search_issues(jql)

            if not new_issues:
                logger.info("No new updates")
                return

            logger.info("Found %d updated issues", len(new_issues))
            for issue in new_issues:
                fields = issue.raw["fields"]
                issue_creator = fields["creator"]["name"]
                issue_name = fields["summary"]
                logger.info("Updated: %s", issue)

                if not self.dry_run:
                    self._safe_send_message_updates(issue, issue_creator, issue_name)
                else:
                    logger.info("[DRY-RUN] Would send update for %s", issue)

        except Exception as e:  # noqa: BLE001
            logger.exception("Error fetching updates: %s", e)

    def _safe_send_message_updates(self, issue, creator: str, name: str) -> None:
        """Send update notification safely."""
        try:
            self.send_message_updates(issue, creator, name)
        except Exception as e:  # noqa: BLE001
            logger.exception("Error sending update message: %s", e)

    # --- Jira helpers (get lists for Telegram commands) ---

    def _get_list(self, issues_raw):
        """Extract lists of (issues, creators, names) from Jira issues."""
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
        """Get list of unassigned issues waiting for processing."""
        jql = self.config.get("jira_search.new_issues_jql") if self.config else None
        if not jql:
            jql = (
                'project = SD911 AND status = "Ожидает обработки" '
                'AND assignee in (EMPTY) AND "Группа исполнителей" = TS_TMB_team'
            )
        new_issues = self.jira.search_issues(jql)
        return self._get_list(new_issues)

    def issues_on_me(self):
        """Get list of my assigned issues."""
        jql = self.config.get("jira_search.my_issues_jql") if self.config else None
        if not jql:
            jql = (
                'status in ("Ожидает обработки", "Повторно открыта", "Ожидает разработки", Уточнено, '
                '"В работе", Согласовано) AND assignee in (currentUser())'
            )
        raw = self.jira.search_issues(jql)
        logger.info("issues_on_me: %s", raw)
        return self._get_list(raw)

    def search_updates(self):
        """Get recent updates in watched issues."""
        jql = self.config.get("jira_search.recent_updates_jql") if self.config else None
        if not jql:
            jql = (
                'updatedDate >= -4d AND key in watchedIssues() '
                'AND status not in (Обработано, Закрыто, Отменено)'
            )
        raw = self.jira.search_issues(jql)
        return self._get_list(raw)

    # --- Telegram helpers ---

    def send_message(self, to_send_id: int, issue, creator: str, name: str) -> None:
        """Send new issue notification to Telegram."""
        if not self.bot:
            logger.warning("Telegram bot not initialized, cannot send message")
            return

        try:
            answer = hlink(f"{issue}: {name}", f"https://jira.ozon.ru/browse/{issue}")
            teams_link = hlink(creator, f"https://teams.microsoft.com/l/chat/0/0?users={creator}@ozon.ru")
            msg = f"Hi! There is a new issue: {answer} from: {teams_link}"
            self.bot.send_message(to_send_id, msg, parse_mode="HTML")
            logger.info("Sent notification for %s to %d", issue, to_send_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("Error sending message: %s", e)
            raise

    def send_message_updates(self, issue, creator: str, name: str) -> None:
        """Send update notification to Telegram."""
        if not self.bot:
            logger.warning("Telegram bot not initialized, cannot send message")
            return

        try:
            answer = hlink(f"{issue}: {name}", f"https://jira.ozon.ru/browse/{issue}")
            msg = f"Hi! There is a new update: {answer} from {creator}"
            self.bot.send_message(self.my_id, msg, parse_mode="HTML")
            logger.info("Sent update notification for %s", issue)
        except Exception as e:  # noqa: BLE001
            logger.exception("Error sending update message: %s", e)
            raise

    # --- time-based control ---

    def check_time(self) -> None:
        """Monitor current time and toggle sleep/wake mode."""
        flag = False

        while True:
            current_time = datetime.now()
            logger.info("Hour is %s", current_time.hour)

            if current_time.hour in self.sleep_hours:
                logger.info("Sleep mode enabled")
                flag = False
                self._toggle_by_time(False)
            else:
                wake_up_hour = self.config.get("time_control.wake_up_hour", 11) if self.config else 11
                if current_time.hour == wake_up_hour and not flag:
                    flag = True
                    self._toggle_by_time(False)
                    time.sleep(11)
                    self._toggle_by_time(True)
                    self.loop()

            interval = self.config.get("polling.time_check_interval", 300) if self.config else 300
            time.sleep(interval)
