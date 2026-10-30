"""Announce a new release on Slack through an incoming webhook.

python-semantic-release has no Slack plugin: this script posts the message that
semantic-release-slack-bot posts for the other Enix projects, from the outputs of the
python-semantic-release action. With --dry-run, it prints the payload instead of posting it.

Environment: SLACK_WEBHOOK, PACKAGE_NAME, RELEASE_VERSION, RELEASE_TAG, RELEASE_NOTES (Markdown),
REPOSITORY (owner/name) and SERVER_URL (https://github.com).
"""

import json
import os
import re
import sys
import urllib.request

# The limit of a Slack section block is 3000 characters, the plugin keeps a margin.
MAX_LENGTH = 2900


def slackify(markdown):
    """Convert the Markdown release notes of python-semantic-release to Slack mrkdwn."""
    text = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"^#+\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"^- ", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # A blank line between bullets of the same list only stretches the message.
    text = re.sub(r"^(• .*)\n\n(?=• )", r"\1\n", text, flags=re.MULTILINE)
    return text.strip()


def truncate(text, length=MAX_LENGTH):
    if len(text) <= length:
        return text
    return text[: length - 3] + "..."


def build_message(package, version, tag, notes, repo_url, repo_path):
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"A new version of `{package}` has been released!\nCurrent version is *{version}*",
            },
        }
    ]
    notes = truncate(slackify(notes))
    if notes:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": notes}})
    return {
        "text": f"A new version of {package} has been released!",
        "blocks": blocks,
        "attachments": [
            {
                "color": "#2cbe4e",
                "blocks": [
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f":package: *<{repo_url}|{repo_path}>:*   <{repo_url}/releases/tag/{tag}|{tag}>",
                            }
                        ],
                    }
                ],
            }
        ],
    }


def main():
    dry_run = "--dry-run" in sys.argv[1:]
    repo_path = os.environ["REPOSITORY"]
    message = build_message(
        package=os.environ["PACKAGE_NAME"],
        version=os.environ["RELEASE_VERSION"],
        tag=os.environ["RELEASE_TAG"],
        notes=os.environ.get("RELEASE_NOTES", ""),
        repo_url=f"{os.environ.get('SERVER_URL', 'https://github.com')}/{repo_path}",
        repo_path=repo_path,
    )
    if dry_run:
        print(json.dumps(message, indent=2, ensure_ascii=False))
        return
    webhook = os.environ.get("SLACK_WEBHOOK")
    if not webhook:
        sys.exit("SLACK_WEBHOOK is not set")
    request = urllib.request.Request(
        webhook,
        data=json.dumps(message).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(f"Slack answered {response.status}: {response.read().decode()}")


if __name__ == "__main__":
    main()
