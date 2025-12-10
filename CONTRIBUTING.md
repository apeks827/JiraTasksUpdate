# Внесение изменений (Contributing)

Спасибо за интерес к проекту! Этот документ описывает, как принести вклад.

## 📋 Кодекс поведения

Мы придерживаемся дружелюбного и инклюзивного сообщества. Будьте уважительны к другим, независимо от уровня опыта.

## 🐛 Reportинг ошибок

1. Проверьте, что ошибка не описана в [FAQ](README.md#faq) или существующих issues
2. Создайте новый issue с заголовком в формате: `[BUG] Описание проблемы`
3. Укажите:
   - Версию Python
   - Версию пакета (из requirements.txt)
   - Полный stacktrace ошибки
   - Шаги для воспроизведения
   - Конфиг (без чувствительных данных)

Пример:
```
[BUG] JiraTaskUpdater crashes on startup with config.yaml

**Environment:**
- Python: 3.10.5
- jira==3.13.0
- pyTelegramBotAPI==4.14.0

**Steps to reproduce:**
1. `cp .env.example .env`
2. Заполнить токены в .env
3. `python cli.py`

**Error:**
```
Traceback (most recent call last):
  File "cli.py", line 123, in main
    config = Config(args.config)
FileNotFoundError: [Errno 2] No such file: 'config.yaml'
```

**Expected behavior:**
Должно загрузить config.yaml или использовать defaults
```

## ✨ Предложение функций

1. Создайте issue с заголовком в формате: `[FEATURE] Описание идеи`
2. Опишите:
   - Какую проблему решает эта функция?
   - Как её использовать?
   - Есть ли альтернативы?

Пример:
```
[FEATURE] Поддержка WebHook вместо поллинга

**Problem:**
Текущий поллинг на интервале создаёт задержку в обработке новых issues.

**Solution:**
Добавить WebHook endpoint, чтобы Jira отправляла уведомления в реальном времени.

**Alternatives:**
- Кэширование (уже реализовано)
- Уменьшение интервала поллинга (может перегрузить API)
```

## 🔧 Pull Request процесс

1. **Fork репозиторий** и создайте ветку из `refactor/modular-structure`:
   ```bash
   git checkout refactor/modular-structure
   git pull origin refactor/modular-structure
   git checkout -b feature/my-feature
   ```

2. **Разработка**
   - Следуйте стилю кода (see [Code Style](#code-style))
   - Добавьте тесты для новой логики
   - Обновите документацию (README, CHANGELOG)

3. **Коммиты**
   ```bash
   git add .
   git commit -m "[FEATURE/BUG/REFACTOR] Короткое описание"
   ```
   
   Форматы сообщений:
   - `[FEATURE]` — новая функция
   - `[BUG]` — исправление ошибки
   - `[REFACTOR]` — улучшение кода
   - `[DOCS]` — обновление документации
   - `[TEST]` — добавление/улучшение тестов

4. **Push и создание PR**
   ```bash
   git push origin feature/my-feature
   ```
   
   Перейдите на GitHub и создайте Pull Request.
   
   **Template для PR:**
   ```markdown
   ## Описание
   Кратко опишите, что делает PR.
   
   ## Тип изменения
   - [ ] Новая функция
   - [ ] Исправление ошибки
   - [ ] Рефакторинг
   - [ ] Обновление документации
   
   ## Связанные issues
   Closes #123
   
   ## Тестирование
   Описание того, как тестировать изменения:
   1. `pip install -r requirements.txt`
   2. `pytest`
   3. `python cli.py --dry-run`
   
   ## Checklist
   - [ ] Код следует стилю проекта
   - [ ] Добавлены тесты
   - [ ] Обновлена документация
   - [ ] Нет breaking changes
   ```

5. **Review и merge**
   - Владельцы проекта рассмотрят PR
   - Могут потребоваться изменения
   - После одобрения PR будет merged в `refactor/modular-structure`

## 🎨 Code Style

### Python стиль

Следуйте [PEP 8](https://www.python.org/dev/peps/pep-0008/). Основные правила:

```python
# ✅ Хорошо
def process_issue(issue: dict, skip_list: set) -> bool:
    """Process single issue with skip rules.
    
    Args:
        issue: Issue dictionary.
        skip_list: Set of issue keys to skip.
    
    Returns:
        True if processed, False if skipped.
    """
    if issue["key"] in skip_list:
        return False
    
    # Process logic
    return True


# ❌ Плохо
def processIssue(iss, skip):
    if iss["key"] in skip:
        return False
    return True
```

### Типизация

Используйте type hints для всех функций:

```python
from typing import Optional, List, Dict

def fetch_issues(jql: str, limit: Optional[int] = None) -> List[Dict]:
    pass
```

### Документация

Докстринги в формате Google:

```python
def method(arg1: str, arg2: int) -> bool:
    """Short description.
    
    Longer description if needed.
    
    Args:
        arg1: Description of arg1.
        arg2: Description of arg2.
    
    Returns:
        Description of return value.
    
    Raises:
        ValueError: When something is invalid.
    """
    pass
```

### Инструменты для проверки

```bash
# Форматирование (Black)
black *.py tests/

# Линтинг (Flake8)
flake8 --max-line-length=100 *.py tests/

# Проверка типов (mypy)
mypy --ignore-missing-imports *.py

# Все вместе
make lint  # если есть Makefile
```

## 🧪 Тестирование

### Написание тестов

Все тесты в папке `tests/`. Используйте pytest.

```python
import pytest
from test import JiraTaskUpdater

def test_skip_by_keyword():
    """Test that issues with skip keywords are not processed."""
    # Arrange
    issue = make_issue("KEY-1", "user", "Problem with пропуск", [])
    updater = JiraTaskUpdater(...)
    
    # Act
    updater._process_new_issue(issue)
    
    # Assert
    assert "KEY-1" in updater.processed_issues_cache
```

Имя функции теста должно начинаться с `test_`. Используйте Arrange-Act-Assert паттерн.

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=test --cov=config --cov=reporting

# Конкретный файл
pytest tests/test_jira_updater.py -v

# С одним тестом
pytest tests/test_jira_updater.py::test_skip_by_keyword -v
```

## 📚 Обновление документации

1. Отредактируйте соответствующий файл (README.md, CHANGELOG.md и т.д.)
2. Проверьте, что markdown синтаксис корректен
3. Добавьте примеры кода, если нужно

## 🚀 Процесс релиза

Овнеры проекта:
1. Обновляют версию в коде (если нужно)
2. Пишут release notes
3. Создают git tag
4. Merging `refactor/modular-structure` → `main` при достижении стабильности

## ❓ Вопросы?

Создавайте issues, обсуждайте идеи открыто. Сообщество готово помочь!

---

**Спасибо за вклад!** 🙏
