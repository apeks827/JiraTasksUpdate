"""Unit tests for JiraTaskUpdater helper methods.

These tests focus on pure logic (skip rules, caching, list extraction) and do not
require real Jira or Telegram clients.
"""

from types import SimpleNamespace

import pytest

from test import JiraTaskUpdater


class DummyJira:
    def __init__(self, issues=None):
        self._issues = issues or []
        self.search_calls = []

    def search_issues(self, jql):  # noqa: D401
        """Return preconfigured issues and record call."""
        self.search_calls.append(jql)
        return self._issues


class DummyBot:
    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, parse_mode=None):  # noqa: D401
        """Record sent messages for assertions."""
        self.messages.append((chat_id, text, parse_mode))


def make_issue(key: str, creator: str, summary: str, comments: list[str] | None = None):
    comments = comments or []
    raw = {
        "fields": {
            "creator": {"name": creator},
            "summary": summary,
            "comment": {"comments": comments},
            "assignee": None,
        }
    }
    return SimpleNamespace(key=key, raw=raw, __str__=lambda self: self.key)


@pytest.fixture()
def updater():
    jira = DummyJira()
    bot = DummyBot()
    return JiraTaskUpdater(jira_client=jira, bot=bot, my_id=1, vovan_id=2)


def test_skip_by_comment_keyword(updater):
    issue = make_issue("KEY-1", "user", "Some issue", ["comment with vivashov inside"])

    updater._process_new_issue(issue)

    # Issue should be cached and not assigned
    assert "KEY-1" in updater.processed_issues_cache


def test_skip_by_name_keyword(updater):
    issue = make_issue("KEY-2", "user", "Проблема с пропуском", [])

    updater._process_new_issue(issue)

    assert "KEY-2" in updater.processed_issues_cache


def test_skip_by_creator(updater):
    issue = make_issue("KEY-3", "vivashov", "Some issue", [])

    updater._process_new_issue(issue)

    assert "KEY-3" in updater.processed_issues_cache


def test_cache_prevents_double_processing(updater, monkeypatch):
    issue = make_issue("KEY-4", "user", "Some issue", [])

    # First time processed and cached
    updater._assign_issue = lambda *args, **kwargs: None  # type: ignore[assignment]
    updater._process_new_issue(issue)
    assert "KEY-4" in updater.processed_issues_cache

    # Second time should be skipped by cache
    updater._assign_issue = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Should not be called"))  # type: ignore[assignment]
    updater._process_new_issue(issue)


def test_get_list_extraction(updater):
    issues_raw = [
        make_issue("KEY-1", "user1", "Summary 1"),
        make_issue("KEY-2", "user2", "Summary 2"),
    ]

    issues, creators, names = updater._get_list(issues_raw)

    assert issues == ["KEY-1", "KEY-2"]
    assert creators == ["user1", "user2"]
    assert names == ["Summary 1", "Summary 2"]
