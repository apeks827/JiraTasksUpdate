"""Reporting module for Jira task statistics and export.

Provides functionality to generate reports in CSV and Markdown formats,
including metrics, statistics, and issue lists.
"""

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class JiraReporter:
    """Generate reports for Jira issues."""

    def __init__(self, output_dir: str = "reports"):
        """Initialize reporter.

        Args:
            output_dir: Directory to save reports (auto-created).
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def export_issues_csv(self, issues: List, filename: str = "issues.csv") -> str:
        """Export issues list to CSV.

        Args:
            issues: List of Jira issue objects.
            filename: Output filename (without path).

        Returns:
            Full path to created CSV file.
        """
        filepath = self.output_dir / filename

        if not issues:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                f.write("No issues found\n")
            return str(filepath)

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

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        return str(filepath)

    def export_issues_markdown(self, issues: List, filename: str = "issues.md") -> str:
        """Export issues list to Markdown.

        Args:
            issues: List of Jira issue objects.
            filename: Output filename (without path).

        Returns:
            Full path to created Markdown file.
        """
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Jira Issues Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            if not issues:
                f.write("No issues found.\n")
                return str(filepath)

            f.write(f"## Summary\n\nTotal issues: {len(issues)}\n\n")

            f.write("## Issues\n\n")
            f.write("| Key | Summary | Status | Creator | Assignee | Priority |\n")
            f.write("|-----|---------|--------|---------|----------|----------|\n")

            for issue in issues:
                fields = issue.raw["fields"]
                key = issue.key
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
        """Generate metrics and statistics.

        Args:
            new_issues: List of unassigned/new issues.
            updates: List of updated issues.
            assigned_by_user: Dict {username: count} of assignments made.

        Returns:
            Dictionary with metrics.
        """
        # Count by status
        status_count = defaultdict(int)
        for issue in new_issues + updates:
            fields = issue.raw["fields"]
            status = fields.get("status", {}).get("name", "Unknown")
            status_count[status] += 1

        # Count by creator
        creator_count = defaultdict(int)
        for issue in new_issues:
            fields = issue.raw["fields"]
            creator = fields.get("creator", {}).get("name", "Unknown")
            creator_count[creator] += 1

        # Count by priority
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
        """Export metrics report to Markdown.

        Args:
            metrics: Metrics dictionary from generate_metrics_report().
            filename: Output filename (without path).

        Returns:
            Full path to created Markdown file.
        """
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Jira Metrics Report\n\n")
            f.write(f"Generated: {metrics['timestamp']}\n\n")

            # Summary
            f.write("## Summary\n\n")
            f.write(f"- **New Issues**: {metrics['new_issues_count']}\n")
            f.write(f"- **Updated Issues**: {metrics['updated_issues_count']}\n")
            f.write(f"- **Total Issues**: {metrics['total_issues']}\n\n")

            # Status breakdown
            f.write("## Status Breakdown\n\n")
            if metrics.get("status_breakdown"):
                for status, count in metrics["status_breakdown"].items():
                    f.write(f"- {status}: **{count}**\n")
                f.write("\n")
            else:
                f.write("No status data available.\n\n")

            # Creator breakdown
            f.write("## Issues by Creator\n\n")
            if metrics.get("creator_breakdown"):
                creator_sorted = sorted(
                    metrics["creator_breakdown"].items(), key=lambda x: x[1], reverse=True
                )
                for creator, count in creator_sorted:
                    f.write(f"- {creator}: **{count}**\n")
                f.write("\n")
            else:
                f.write("No creator data available.\n\n")

            # Priority breakdown
            f.write("## Issues by Priority\n\n")
            if metrics.get("priority_breakdown"):
                priority_order = ["Highest", "High", "Medium", "Low", "Lowest"]
                for priority in priority_order:
                    count = metrics["priority_breakdown"].get(priority, 0)
                    if count > 0:
                        f.write(f"- {priority}: **{count}**\n")
                f.write("\n")
            else:
                f.write("No priority data available.\n\n")

            # Assignments
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
        """Export metrics to CSV.

        Args:
            metrics: Metrics dictionary from generate_metrics_report().
            filename: Output filename (without path).

        Returns:
            Full path to created CSV file.
        """
        filepath = self.output_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow(["Metric", "Value"])
            writer.writerow(["Timestamp", metrics["timestamp"]])
            writer.writerow(["New Issues", metrics["new_issues_count"]])
            writer.writerow(["Updated Issues", metrics["updated_issues_count"]])
            writer.writerow(["Total Issues", metrics["total_issues"]])
            writer.writerow([""])

            writer.writerow(["Status", "Count"])
            for status, count in metrics.get("status_breakdown", {}).items():
                writer.writerow([status, count])
            writer.writerow([""])

            writer.writerow(["Creator", "Count"])
            for creator, count in metrics.get("creator_breakdown", {}).items():
                writer.writerow([creator, count])
            writer.writerow([""])

            writer.writerow(["Priority", "Count"])
            for priority, count in metrics.get("priority_breakdown", {}).items():
                writer.writerow([priority, count])
            writer.writerow([""])

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
        """Generate full daily report (Markdown + CSV metrics).

        Args:
            new_issues: New unassigned issues.
            updates: Updated issues.
            assigned_by_user: Dict {username: count}.
            basename: Base name for files (timestamps will be added).

        Returns:
            Tuple of (markdown_filepath, metrics_filepath).
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export issues
        md_file = self.export_issues_markdown(
            new_issues + updates, f"{basename}_{timestamp}.md"
        )

        # Generate and export metrics
        metrics = self.generate_metrics_report(new_issues, updates, assigned_by_user)
        metrics_file = self.export_metrics_markdown(metrics, f"metrics_{timestamp}.md")

        return md_file, metrics_file
