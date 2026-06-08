import os
import json
import logging
import httpx

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


class SlackNotifier:

    @staticmethod
    def _post_to_slack(blocks: list, text: str = "DevPulse Notification") -> bool:
        if not SLACK_WEBHOOK_URL:
            logger.warning("SLACK_WEBHOOK_URL not configured. Skipping Slack notification.")
            return False

        try:
            response = httpx.post(
                SLACK_WEBHOOK_URL,
                json={"text": text, "blocks": blocks},
                timeout=10.0,
            )
            if response.status_code == 200:
                logger.info("Slack notification sent successfully.")
                return True
            logger.error(f"Slack API returned {response.status_code}: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return False

    @classmethod
    def send_standup(cls, username: str, standup_data: dict) -> bool:
        summary = standup_data.get("synthesis_summary", "No summary available.")
        action_items = standup_data.get("action_items", [])

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"📋 Daily Standup — {username}", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
        ]

        if action_items:
            blocks.append({"type": "divider"})
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Action Items*"}})

            for item in action_items:
                pr_num = item.get("pr_number", "?")
                action = item.get("action", "")
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"• *PR #{pr_num}*: {action}"},
                })

        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "_Sent by DevPulse_"}]})

        return cls._post_to_slack(blocks, text=f"Daily Standup for {username}")

    @classmethod
    def send_bottleneck_alert(cls, username: str, bottleneck_data: dict) -> bool:
        summary = bottleneck_data.get("summary", {})
        total = summary.get("total_stale_prs", 0)
        critical = summary.get("critical_count", 0)
        warning = summary.get("warning_count", 0)
        repos = bottleneck_data.get("bottlenecks_by_repo", {})

        severity_line = f"🔴 {critical} critical  •  🟡 {warning} warning  •  Total: {total}"

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"🚨 Bottleneck Alert — {username}", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": severity_line}},
            {"type": "divider"},
        ]

        for repo, prs in repos.items():
            pr_lines = []
            for pr in prs:
                sev = pr.get("severity", "stale")
                icon = "🔴" if sev == "critical" else "🟡" if sev == "warning" else "⚪"
                pr_lines.append(f"{icon} #{pr['number']} — {pr['title']} ({pr['hours_open']}h)")

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{repo}*\n" + "\n".join(pr_lines)},
            })

        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "_Sent by DevPulse_"}]})

        return cls._post_to_slack(blocks, text=f"Bottleneck Alert for {username}")
