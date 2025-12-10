"""Юнит-тесты для вспомогательных методов JiraTaskUpdater.

Эти тесты проверяют "чистую" бизнес-логику (skip-правила, кэширование,
извлечение списков) и не требуют реальных клиентов Jira или Telegram.
"""

from types import SimpleNamespace

import pytest

from test import JiraTaskUpdater


class DummyJira:
    """Простой заглушечный клиент Jira для тестов."""

    def __init__(self, issues=None):
        self._issues = issues or []
        self.search_calls = []

    def search_issues(self, jql):  # noqa: D401
        """Вернуть заранее подготовленные задачи и запомнить JQL-запрос."""
        self.search_calls.append(jql)
        return self._issues


class DummyBot:
    """Заглушка Telegram-бота, записывающая отправленные сообщения."""

    def __init__(self):
        self.messages = []

    def send_message(self, chat_id, text, parse_mode=None):  # noqa: D401
        """Сохранить параметры отправленного сообщения для последующей проверки."""
        self.messages.append((chat_id, text, parse_mode))


def make_issue(key: str, creator: str, summary: str, comments: list[str] | None = None):
    """Создать объект-обёртку, имитирующий Jira issue.

    Args:
        key: Ключ задачи
        creator: Имя создателя
        summary: Название задачи
        comments: Список комментариев (строки)

    Returns:
        Объект SimpleNamespace с полями key и raw
    """
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
    """Фикстура, создающая JiraTaskUpdater с заглушками Jira и Telegram."""
    jira = DummyJira()
    bot = DummyBot()
    return JiraTaskUpdater(jira_client=jira, bot=bot, my_id=1, vovan_id=2)


def test_skip_by_comment_keyword(updater):
    """Проверка, что задачи с определёнными словами в комментариях пропускаются."""
    issue = make_issue("KEY-1", "user", "Some issue", ["comment with vivashov inside"])

    updater._process_new_issue(issue)

    # Задача должна быть закеширована и не назначена
    assert "KEY-1" in updater.processed_issues_cache


def test_skip_by_name_keyword(updater):
    """Проверка, что задачи с ключевыми словами в названии пропускаются."""
    issue = make_issue("KEY-2", "user", "Проблема с пропуском", [])

    updater._process_new_issue(issue)

    assert "KEY-2" in updater.processed_issues_cache


def test_skip_by_creator(updater):
    """Проверка, что задачи от определённых создателей пропускаются."""
    issue = make_issue("KEY-3", "vivashov", "Some issue", [])

    updater._process_new_issue(issue)

    assert "KEY-3" in updater.processed_issues_cache


def test_cache_prevents_double_processing(updater, monkeypatch):
    """Проверка, что кэш не позволяет обработать одну задачу дважды подряд."""
    issue = make_issue("KEY-4", "user", "Some issue", [])

    # Первый раз задача будет обработана и попадёт в кэш
    updater._assign_issue = lambda *args, **kwargs: None  # type: ignore[assignment]
    updater._process_new_issue(issue)
    assert "KEY-4" in updater.processed_issues_cache

    # Второй раз _assign_issue вызываться не должен, иначе тест упадёт
    updater._assign_issue = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Should not be called"))  # type: ignore[assignment]
    updater._process_new_issue(issue)


def test_get_list_extraction(updater):
    """Проверка, что _get_list корректно извлекает ключи, создателей и названия."""
    issues_raw = [
        make_issue("KEY-1", "user1", "Summary 1"),
        make_issue("KEY-2", "user2", "Summary 2"),
    ]

    issues, creators, names = updater._get_list(issues_raw)

    assert issues == ["KEY-1", "KEY-2"]
    assert creators == ["user1", "user2"]
    assert names == ["Summary 1", "Summary 2"]
