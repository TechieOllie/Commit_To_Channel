# Commit To Channel

A Discord bot that syncs Markdown files (e.g. from an Obsidian vault) to a Discord channel. Supports both **Git** and **Nextcloud (WebDAV)** as file sources.

## Quick start

```bash
cp .env.example .env        # fill in your config
docker compose up -d        # build and run
```

## Features

- **Two file sources** — Git repository or Nextcloud WebDAV
- **Edits in place** — if a file changes, the bot edits the existing Discord message instead of sending a new one
- **Multi-message split** — files over Discord's 2000-char limit are split across multiple messages; surplus messages are cleaned up when a file shrinks
- **Obsidian frontmatter** — YAML frontmatter (`---` blocks) is stripped before posting
- **Wikilink conversion** — `[[Note]]` → `[Note](Note.md)`, `[[Note|Text]]` → `[Text](Note.md)`
- **Tab indentation** — tabs are expanded to 2 spaces for proper Discord list rendering
- **Horizontal rules removed** — stray `---` lines (after frontmatter) are removed since Discord renders them poorly
- **Stateful tracking** — persists last-processed marker and Discord message IDs, survives restarts

## File sources

### Git (`FILE_SOURCE=git`)

Clones the repo with `--filter=blob:none` (partial clone — only tree metadata, blobs fetched on demand). On each poll:

1. `git fetch --quiet origin`
2. `git reset --hard @{u}` (pins to upstream tracking branch)
3. `git diff --name-only <last_commit> HEAD` to find changed `.md` files

Auth via access token injected into the remote URL at runtime. The `WATCHED_DIRECTORY` var restricts scanning to a subdirectory of the repo.

### Nextcloud (`FILE_SOURCE=nextcloud`)

Connects via WebDAV to Nextcloud's file endpoint. On each poll:

1. `PROPFIND` with `Depth: infinity` lists all `.md` files and their ETags
2. Compares ETags against a local manifest (`{path: etag}`)
3. Downloads only new/changed files to a local cache
4. Updates the manifest

## Configuration

| Variable | Default | Description |
|---|---|---|
| `FILE_SOURCE` | `git` | `"git"` or `"nextcloud"` |
| `DISCORD_TOKEN` | — | Discord bot token |
| `DISCORD_CHANNEL_ID` | — | Target channel ID |
| `POLL_INTERVAL` | `300` | Seconds between polls |
| `UPLOAD_DELAY` | `1.0` | Seconds between sequential uploads (rate limiting) |
| **Git** | | |
| `GIT_REPO_URL` | — | Repository URL (without credentials) |
| `GITEA_TOKEN` | — | Git access token |
| `GIT_USERNAME` | `git` | Username for token auth |
| `WATCHED_DIRECTORY` | `""` | Subdirectory to scan (empty = whole repo) |
| `CLONE_DIR` | `/data/repo` | Clone location |
| **Nextcloud** | | |
| `NEXTCLOUD_URL` | — | Nextcloud server URL |
| `NEXTCLOUD_USERNAME` | — | Nextcloud username |
| `NEXTCLOUD_PASSWORD` | — | App password (not your login password) |
| `NEXTCLOUD_PATH` | `""` | Remote directory containing `.md` files |
| `NEXTCLOUD_CACHE_DIR` | `/data/nextcloud_cache` | Local cache for downloaded files |

## Discord bot permissions

Invite the bot with **View Channels**, **Send Messages**, and **Read Message History** (permission integer `66560`).

## Project structure

```
Commit_To_Channel/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── src/
    ├── bot.py               # Discord client, markdown conversion, message sync
    ├── config.py             # Environment variable loading
    ├── main.py               # Entry point
    ├── source_base.py        # Abstract FileSource interface
    ├── git_source.py         # Git implementation
    └── nextcloud_source.py   # Nextcloud WebDAV implementation
```
