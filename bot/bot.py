import json
import asyncio
import re
import urllib.parse
from pathlib import Path

import discord

from . import config
from .source_base import FileSource
from .git_source import GitSource
from .nextcloud_source import NextcloudSource

DISCORD_MAX_LENGTH = 2000


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            text = text[end + 3:]
            if text.startswith("\n"):
                text = text[1:]
    return text


def convert_to_discord_markdown(text: str) -> str:
    text = strip_frontmatter(text)
    text = text.expandtabs(2)
    text = re.sub(r'^---\s*$', '', text, flags=re.MULTILINE)

    def _wikilink_pipe(m):
        return f'[{m.group(2)}]({urllib.parse.quote(m.group(1), safe="/")}.md)'

    def _wikilink(m):
        return f'[{m.group(1)}]({urllib.parse.quote(m.group(1), safe="/")}.md)'

    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', _wikilink_pipe, text)
    text = re.sub(r'\[\[([^\]]+)\]\]', _wikilink, text)
    return text


def chunk_content(header: str, body: str) -> list[str]:
    full = f"{header}\n{body}"
    if len(full) <= DISCORD_MAX_LENGTH:
        return [full]

    chunks = []
    remaining = body
    while remaining:
        if len(remaining) <= DISCORD_MAX_LENGTH:
            chunks.append(remaining)
            break

        split = remaining.rfind('\n', 0, DISCORD_MAX_LENGTH)
        if split <= 0:
            split = remaining.rfind(' ', 0, DISCORD_MAX_LENGTH)
        if split <= 0:
            split = DISCORD_MAX_LENGTH

        chunks.append(remaining[:split])
        remaining = remaining[split:]

    return [f"{header}\n{chunks[0]}"] + chunks[1:]


def _create_source() -> FileSource:
    if config.FILE_SOURCE == "nextcloud":
        return NextcloudSource()
    return GitSource()


class CommitBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.source = _create_source()
        self._tracking_file = Path(config.TRACKING_FILE)
        self._last_marker: str | None = None
        self._file_messages: dict[str, list[int]] = {}
        self._watch_task: asyncio.Task | None = None
        self._load_tracking()

    def _load_tracking(self):
        if self._tracking_file.exists():
            try:
                data = json.loads(self._tracking_file.read_text())
                self._last_marker = data.get("last_marker") or data.get("last_commit")
                raw = data.get("messages", {})
                self._file_messages = {
                    k: v if isinstance(v, list) else [v]
                    for k, v in raw.items()
                }
            except (json.JSONDecodeError, KeyError):
                self._last_marker = None
                self._file_messages = {}

    def _save_tracking(self):
        self._tracking_file.parent.mkdir(parents=True, exist_ok=True)
        self._tracking_file.write_text(
            json.dumps({
                "last_marker": self._last_marker,
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
        print(f"File source: {config.FILE_SOURCE}")
        # on_ready runs again after every reconnect: start the loop only once.
        if self._watch_task is None:
            self._watch_task = asyncio.create_task(self._watch_loop())

    async def _watch_loop(self):
        while True:
            try:
                # Blocking (git subprocesses, WebDAV requests): keep it off the
                # event loop so the gateway heartbeat keeps running.
                success, marker, files = await asyncio.to_thread(
                    self.source.poll, self._last_marker
                )
                if not success:
                    print("Source poll returned False, will retry")
                    await asyncio.sleep(config.POLL_INTERVAL)
                    continue

                if marker == self._last_marker:
                    await asyncio.sleep(config.POLL_INTERVAL)
                    continue

                if files:
                    await self._process_files(files)

                self._last_marker = marker
                self._save_tracking()
            except Exception as e:
                print(f"Watch loop error: {e}")
            await asyncio.sleep(config.POLL_INTERVAL)

    async def _sync_messages(self, rel: str, chunks: list[str]):
        old_ids = self._file_messages.pop(rel, [])
        new_ids = []

        for i, chunk in enumerate(chunks):
            if i < len(old_ids):
                try:
                    msg = await self._channel.fetch_message(old_ids[i])
                    await msg.edit(content=chunk)
                    new_ids.append(msg.id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    msg = await self._channel.send(chunk)
                    new_ids.append(msg.id)
            else:
                msg = await self._channel.send(chunk)
                new_ids.append(msg.id)

            await asyncio.sleep(config.UPLOAD_DELAY)

        stale = old_ids[len(chunks):]
        for mid in stale:
            try:
                msg = await self._channel.fetch_message(mid)
                await msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        self._file_messages[rel] = new_ids

    async def _process_files(self, files: list[Path]):
        for file_path in files:
            rel = str(file_path.relative_to(self.source.base_dir))

            if not file_path.exists():
                continue

            try:
                raw = file_path.read_text(encoding="utf-8")
                body = convert_to_discord_markdown(raw)
                header = f"📄 `{rel}`"
                chunks = chunk_content(header, body)
                await self._sync_messages(rel, chunks)
                print(f"Synced: {rel} ({len(chunks)} message{'s' if len(chunks) > 1 else ''})")
            except Exception as e:
                print(f"Failed to process {file_path}: {e}")

        stale = [k for k in self._file_messages if not (self.source.base_dir / k).exists()]
        for k in stale:
            for mid in self._file_messages[k]:
                try:
                    msg = await self._channel.fetch_message(mid)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            del self._file_messages[k]
