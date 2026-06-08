import os
from dotenv import load_dotenv

load_dotenv()

FILE_SOURCE = os.getenv("FILE_SOURCE", "git")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))
TRACKING_FILE = os.getenv("TRACKING_FILE", "/data/tracking.json")
UPLOAD_DELAY = float(os.getenv("UPLOAD_DELAY", "1.0"))

GIT_REPO_URL = os.getenv("GIT_REPO_URL")
GITEA_TOKEN = os.getenv("GITEA_TOKEN")
GIT_USERNAME = os.getenv("GIT_USERNAME", "git")
WATCHED_DIRECTORY = os.getenv("WATCHED_DIRECTORY", "")
CLONE_DIR = os.getenv("CLONE_DIR", "/data/repo")

NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL")
NEXTCLOUD_USERNAME = os.getenv("NEXTCLOUD_USERNAME")
NEXTCLOUD_PASSWORD = os.getenv("NEXTCLOUD_PASSWORD")
NEXTCLOUD_PATH = os.getenv("NEXTCLOUD_PATH", "")
NEXTCLOUD_CACHE_DIR = os.getenv("NEXTCLOUD_CACHE_DIR", "/data/nextcloud_cache")
