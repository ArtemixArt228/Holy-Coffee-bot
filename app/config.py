import os

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from a .env file (for local development)


class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# Validate critical configurations
if not Config.BOT_TOKEN:
    raise ValueError("BOT_TOKEN must be set in the environment variables.")
if not Config.SUPABASE_URL:
    raise ValueError("SUPABASE_URL must be set in the environment variables.")
if not Config.SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY must be set in the environment variables.")
