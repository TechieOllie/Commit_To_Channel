import json
import asyncio
import re
from pathlib import Path

import discord

import config
from git_manager import GitManager

DISCORD_MAX_LENGTH = 2000


def convert_to_discord_markdown(text: str) -> str:
    text = text.expandtabs(2)
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    return text


class CommitBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.git = GitManager()
        self._tracking_file = Path(config.TRACKING_FILE)
        self._last_commit: str | None = None
        self._file_messages: dict[str, int] = {}
        self._load_tracking()

    def _load_tracking(self):
        if self._tracking_file.exists():
            try:
                data = json.loads(self._tracking_file.read_text())
                self._last_commit = data.get("last_commit")
                self._file_messages = data.get("messages", {})
            except (json.JSONDecodeError, KeyError):
                self._last_commit = None
                self._file_messages = {}

    def _save_tracking(self):
        self._tracking_file.parent.mkdir(parents=True, exist_ok=True)
        self._tracking_file.write_text(
            json.dumps({
                "last_commit": self._last_commit,
                "messages": self._file_messages,
            })
        )

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        self._channel = self.get_channel(config.DISCORD_CHANNEL_ID)
        if not self._channel:
            print(f"Channel {config.DISCORD_CHANNEL_ID} not found")
            await self.close()
            return
        print(f"Watching directory: {config.WATCHED_DIRECTORY or '(repo root)'}")
        self.loop.create_task(self._watch_loop())

    async def _watch_loop(self):
        while True:
            try:
                if self.git.update_repo():
                    await self._process_changed_files()
            except Exception as e:
                print(f"Watch loop error: {e}")
            await asyncio.sleep(config.POLL_INTERVAL)

    def _build_content(self, rel: str, raw: str) -> str:
        content = f"📄 `{rel}`\n\n{convert_to_discord_markdown(raw)}"
        if len(content) > DISCORD_MAX_LENGTH:
            content = content[: DISCORD_MAX_LENGTH - 30] + "\n\n*…truncated*"
        return content

    async def _process_changed_files(self):
        current_commit = self.git.get_current_commit()
        if current_commit == self._last_commit:
            return

        files = self.git.get_changed_md_files(self._last_commit)
        if not files:
            self._last_commit = current_commit
            self._save_tracking()
            return

        for file_path in files:
            rel = str(file_path.relative_to(self.git.repo_dir))
            old_msg_id = self._file_messages.pop(rel, None)

            if not file_path.exists():
                continue

            try:
                raw = file_path.read_text(encoding="utf-8")
                content = self._build_content(rel, raw)

                if old_msg_id:
                    try:
                        msg = await self._channel.fetch_message(old_msg_id)
                        await msg.edit(content=content)
                        self._file_messages[rel] = msg.id
                        print(f"Updated: {rel}")
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                        print(f"Could not edit {rel}, sending new: {e}")
                        msg = await self._channel.send(content)
                        self._file_messages[rel] = msg.id
                        print(f"Uploaded: {rel}")
                else:
                    msg = await self._channel.send(content)
                    self._file_messages[rel] = msg.id
                    print(f"Uploaded: {rel}")

                await asyncio.sleep(config.UPLOAD_DELAY)
            except Exception as e:
                print(f"Failed to process {file_path}: {e}")

        stale = [k for k in self._file_messages if not (self.git.repo_dir / k).exists()]
        for k in stale:
            del self._file_messages[k]

        self._last_commit = current_commit
        self._save_tracking()
