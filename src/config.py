import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
GIT_REPO_URL = os.getenv("GIT_REPO_URL")
GITEA_TOKEN = os.getenv("GITEA_TOKEN")
GIT_USERNAME = os.getenv("GIT_USERNAME", "git")
WATCHED_DIRECTORY = os.getenv("WATCHED_DIRECTORY", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))
CLONE_DIR = os.getenv("CLONE_DIR", "/data/repo")
TRACKING_FILE = os.getenv("TRACKING_FILE", "/data/tracking.json")
UPLOAD_DELAY = float(os.getenv("UPLOAD_DELAY", "1.0"))
