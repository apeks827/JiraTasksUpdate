"""Модуль отчётности для JiraTasksUpdate.

Этот модуль отвечает за генерацию отчётов о задачах Jira в различных форматах:
- CSV для импорта в Excel/табличные редакторы
- Markdown для просмотра в GitHub/Slack/Telegram

Отчёты включают:
- Списки задач с полной информацией
- Статистику по создателям, приоритетам, статусам
- Метрики по назначенным задачам

Примеры использования:
    reporter = JiraReporter(output_dir='reports')
    reporter.export_issues_csv(issues_list, 'issues.csv')
    metrics = reporter.generate_metrics_report(new_issues, updates, assigned_by_user)
    reporter.export_metrics_markdown(metrics, 'metrics.md')
"""

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class JiraReporter:
    """Генератор отчётов для задач Jira.
    
    Преобразует список задач Jira в различные форматы отчётов
    и собирает статистику по задачам.
    """

    def __init__(self, output_dir: str = "reports"):
        """Инициализация репортера.

        Args:
            output_dir: Директория для сохранения отчётов
        """
        self.output_dir = Path(output_dir)
        # Создаём директорию если её нет
        self.output_dir.mkdir(exist_ok=True)

    def export_issues_csv(self, issues: List, filename: str = "issues.csv") -> str:
        """Экспортировать список задач в CSV.

        CSV включает столбцы:
        - Key (ключ задачи)
        - Summary (название)
        - Status (статус)
        - Creator (создатель)
        - Assignee (исполнитель)
        - Created (дата создания)
        - Updated (дата последнего обновления)
        - Priority (приоритет)
        - Components (компоненты)

        Args:
            issues: Список объектов задач из Jira
            filename: Имя файла для сохранения

        Returns:
            Полный путь к созданному файлу
        """
        filepath = self.output_dir / filename

        # Если задач нет, создаём пустой файл с сообщением
        if not issues:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                f.write("No issues found\n")
            return str(filepath)

        # Собираем строки с информацией о задачах
        rows = []
        for issue in issues:
            fields = issue.raw["fields"]
            rows.append({
                "Key": issue.key,
                "Summary": fields.get("summary", ""),
                "Status": fields.get("status", {}).get("name", ""),
                "Creator": fields.get("creator", {}).get("name", ""),
                "Assignee": fields.get("assignee", {}).get("name", "Unassigned"),
                "Created": fields.get("created", ""),
                "Updated": fields.get("updated", ""),
                "Priority": fields.get("priority", {}).get("name", ""),
                "Components": "; ".join(
                    [c.get("name", "") for c in fields.get("components", [])]
                ),
            })

        # Пишем в CSV файл
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        return str(filepath)

    def export_issues_markdown(self, issues: List, filename: str = "issues.md") -> str:
        """Экспортировать список задач в Markdown.

        Создаёт красиво отформатированную Markdown таблицу с задачами,
        которую можно вставить в документацию, Slack, GitHub и т.д.

        Args:
            issues: Список объектов задач из Jira
            filename: Имя файла для сохранения

        Returns:
            Полный путь к созданному файлу
        """
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Jira Issues Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            if not issues:
                f.write("No issues found.\n")
                return str(filepath)

            # Сводная информация
            f.write(f"## Summary\n\nTotal issues: {len(issues)}\n\n")

            # Таблица с задачами
            f.write("## Issues\n\n")
            f.write("| Key | Summary | Status | Creator | Assignee | Priority |\n")
            f.write("|-----|---------|--------|---------|----------|----------|\n")

            for issue in issues:
                fields = issue.raw["fields"]
                key = issue.key
                # Экранируем символ | в названии задачи
                summary = fields.get("summary", "").replace("|", "\\|")[:50]
                status = fields.get("status", {}).get("name", "")
                creator = fields.get("creator", {}).get("name", "")
                assignee = fields.get("assignee", {}).get("name", "Unassigned")
                priority = fields.get("priority", {}).get("name", "-")

                f.write(f"| `{key}` | {summary} | {status} | {creator} | {assignee} | {priority} |\n")

        return str(filepath)

    def generate_metrics_report(
        self, new_issues: List, updates: List, assigned_by_user: Dict[str, int]
    ) -> Dict[str, Any]:
        """Сгенерировать метрики и статистику по задачам.

        Подсчитывает:
        - Количество новых и обновлённых задач
        - Распределение по статусам
        - Распределение по создателям
        - Распределение по приоритетам
        - Количество назначений на каждого пользователя

        Args:
            new_issues: Список новых/необработанных задач
            updates: Список обновлённых задач
            assigned_by_user: Словарь {username: count} количеств назначений

        Returns:
            Словарь с метриками
        """
        # Подсчитываем задачи по статусам
        status_count = defaultdict(int)
        for issue in new_issues + updates:
            fields = issue.raw["fields"]
            status = fields.get("status", {}).get("name", "Unknown")
            status_count[status] += 1

        # Подсчитываем задачи по создателям
        creator_count = defaultdict(int)
        for issue in new_issues:
            fields = issue.raw["fields"]
            creator = fields.get("creator", {}).get("name", "Unknown")
            creator_count[creator] += 1

        # Подсчитываем задачи по приоритетам
        priority_count = defaultdict(int)
        for issue in new_issues:
            fields = issue.raw["fields"]
            priority = fields.get("priority", {}).get("name", "Unknown")
            priority_count[priority] += 1

        return {
            "timestamp": datetime.now().isoformat(),
            "new_issues_count": len(new_issues),
            "updated_issues_count": len(updates),
            "total_issues": len(new_issues) + len(updates),
            "status_breakdown": dict(status_count),
            "creator_breakdown": dict(creator_count),
            "priority_breakdown": dict(priority_count),
            "assignments_by_user": assigned_by_user,
        }

    def export_metrics_markdown(
        self, metrics: Dict[str, Any], filename: str = "metrics.md"
    ) -> str:
        """Экспортировать метрики в Markdown.

        Создаёт красиво оформленный отчёт метрик для чтения.

        Args:
            metrics: Словарь метрик из generate_metrics_report()
            filename: Имя файла для сохранения

        Returns:
            Полный путь к созданному файлу
        """
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Jira Metrics Report\n\n")
            f.write(f"Generated: {metrics['timestamp']}\n\n")

            # Сводка
            f.write("## Summary\n\n")
            f.write(f"- **New Issues**: {metrics['new_issues_count']}\n")
            f.write(f"- **Updated Issues**: {metrics['updated_issues_count']}\n")
            f.write(f"- **Total Issues**: {metrics['total_issues']}\n\n")

            # Распределение по статусам
            f.write("## Status Breakdown\n\n")
            if metrics.get("status_breakdown"):
                for status, count in metrics["status_breakdown"].items():
                    f.write(f"- {status}: **{count}**\n")
                f.write("\n")
            else:
                f.write("No status data available.\n\n")

            # Распределение по создателям
            f.write("## Issues by Creator\n\n")
            if metrics.get("creator_breakdown"):
                # Сортируем по количеству (больше всего сверху)
                creator_sorted = sorted(
                    metrics["creator_breakdown"].items(), key=lambda x: x[1], reverse=True
                )
                for creator, count in creator_sorted:
                    f.write(f"- {creator}: **{count}**\n")
                f.write("\n")
            else:
                f.write("No creator data available.\n\n")

            # Распределение по приоритетам
            f.write("## Issues by Priority\n\n")
            if metrics.get("priority_breakdown"):
                # Выводим в стандартном порядке приоритетов
                priority_order = ["Highest", "High", "Medium", "Low", "Lowest"]
                for priority in priority_order:
                    count = metrics["priority_breakdown"].get(priority, 0)
                    if count > 0:
                        f.write(f"- {priority}: **{count}**\n")
                f.write("\n")
            else:
                f.write("No priority data available.\n\n")

            # Назначения по пользователям
            f.write("## Assignments by User\n\n")
            if metrics.get("assignments_by_user"):
                for user, count in sorted(
                    metrics["assignments_by_user"].items(), key=lambda x: x[1], reverse=True
                ):
                    f.write(f"- {user}: **{count}**\n")
                f.write("\n")
            else:
                f.write("No assignment data available.\n\n")

        return str(filepath)

    def export_metrics_csv(
        self, metrics: Dict[str, Any], filename: str = "metrics.csv"
    ) -> str:
        """Экспортировать метрики в CSV для импорта в Excel.

        Args:
            metrics: Словарь метрик из generate_metrics_report()
            filename: Имя файла для сохранения

        Returns:
            Полный путь к созданному файлу
        """
        filepath = self.output_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Основная статистика
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Timestamp", metrics["timestamp"]])
            writer.writerow(["New Issues", metrics["new_issues_count"]])
            writer.writerow(["Updated Issues", metrics["updated_issues_count"]])
            writer.writerow(["Total Issues", metrics["total_issues"]])
            writer.writerow([""])

            # Статусы
            writer.writerow(["Status", "Count"])
            for status, count in metrics.get("status_breakdown", {}).items():
                writer.writerow([status, count])
            writer.writerow([""])

            # Создатели
            writer.writerow(["Creator", "Count"])
            for creator, count in metrics.get("creator_breakdown", {}).items():
                writer.writerow([creator, count])
            writer.writerow([""])

            # Приоритеты
            writer.writerow(["Priority", "Count"])
            for priority, count in metrics.get("priority_breakdown", {}).items():
                writer.writerow([priority, count])
            writer.writerow([""])

            # Назначения
            writer.writerow(["User", "Assignments"])
            for user, count in metrics.get("assignments_by_user", {}).items():
                writer.writerow([user, count])

        return str(filepath)

    def daily_report(
        self,
        new_issues: List,
        updates: List,
        assigned_by_user: Dict[str, int],
        basename: str = "daily_report",
    ) -> Tuple[str, str]:
        """Сгенерировать полный дневной отчёт (Markdown + CSV метрики).

        Создаёт оба файла отчёта с временными метками в именах файлов.

        Args:
            new_issues: Список новых задач
            updates: Список обновлённых задач
            assigned_by_user: Словарь {username: count}
            basename: Базовое имя для файлов

        Returns:
            Кортеж (путь_к_markdown_отчёту, путь_к_метрикам)
        """
        # Генерируем временную метку для имён файлов
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Экспортируем задачи
        md_file = self.export_issues_markdown(
            new_issues + updates, f"{basename}_{timestamp}.md"
        )

        # Генерируем и экспортируем метрики
        metrics = self.generate_metrics_report(new_issues, updates, assigned_by_user)
        metrics_file = self.export_metrics_markdown(metrics, f"metrics_{timestamp}.md")

        return md_file, metrics_file
