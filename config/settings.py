import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # Paths
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    BACKGROUNDS_DIR = os.path.join(ASSETS_DIR, "backgrounds")
    SPEAKERS_DIR = os.path.join(ASSETS_DIR, "speakers")
    TEMP_DIR = os.path.join(BASE_DIR, "temp")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
    SPEAKERS_CONFIG = os.path.join(BASE_DIR, "config", "speakers.json")

    # FFmpeg binary paths (set via env or auto-detected)
    FFMPEG_BIN = os.getenv(
        "FFMPEG_PATH",
        r"C:\Users\Ayush\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe",
    )
    FFPROBE_BIN = os.getenv(
        "FFPROBE_PATH",
        r"C:\Users\Ayush\AppData\Local\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.0.1-full_build\bin\ffprobe.exe",
    )

    # ElevenLabs
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
    ELEVENLABS_MODEL = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")

    # Fish Audio
    FISH_AUDIO_API_KEY = os.getenv("FISH_AUDIO_SECRET_KEY", "")

    # FFmpeg / video — 9:16 portrait (vertical video)
    VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
    VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
    BACKGROUND_VIDEO = os.getenv(
        "BACKGROUND_VIDEO", os.path.join(BACKGROUNDS_DIR, "background.mp4")
    )

    # Speaker image overlay — half screen width, positioned at bottom
    OVERLAY_WIDTH = int(os.getenv("OVERLAY_WIDTH", "480"))
    OVERLAY_HEIGHT = int(os.getenv("OVERLAY_HEIGHT", "480"))

    # Font / subtitles
    FONT_PATH = os.getenv(
        "FONT_PATH",
        os.path.join(ASSETS_DIR, "fonts", "Poppins-ExtraBold.ttf"),
    )
    FONT_NAME = "Poppins ExtraBold"
    SUBTITLE_FONT_SIZE = 116
    SUBTITLE_HIGHLIGHT_EXTRA_SIZE = 8
    SUBTITLE_WORDS_PER_CHUNK = 2

    # Validation limits
    MAX_DIALOGUE_LINES = 200
    MAX_TEXT_LENGTH = 2000

    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("openai_api_key", "")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # YouTube (OAuth2)
    YOUTUBE_CLIENT_SECRETS_FILE = os.getenv(
        "YOUTUBE_CLIENT_SECRETS_FILE",
        os.path.join(BASE_DIR, "config", "client_secrets.json"),
    )
    YOUTUBE_TOKEN_FILE = os.getenv(
        "YOUTUBE_TOKEN_FILE",
        os.path.join(BASE_DIR, "config", "youtube_token.json"),
    )

    # Instagram (Meta Graph API)
    INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")

    # Twitter / X
    TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")

    # LinkedIn
    LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    LINKEDIN_PERSON_URN = os.getenv("LINKEDIN_PERSON_URN", "")

    # Facebook
    FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
    FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")

    # Notion
    NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
