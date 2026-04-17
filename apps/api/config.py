"""
Configuration for RoBoCop API
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
env_path = PROJECT_ROOT / ".env"
secrets_path = PROJECT_ROOT / ".streamlit" / "secrets.toml"

# Load the repo-root .env first so local dev works from the project root.
print(f"[DEBUG] Looking for .env at: {env_path}")
print(f"[DEBUG] .env exists: {env_path.exists()}")
if env_path.exists():
    load_dotenv(env_path, override=False)

if secrets_path.exists():
    # Parse secrets.toml manually since it's not a standard .env file
    try:
        import toml
        with open(secrets_path, 'r') as f:
            secrets = toml.load(f)
        
        # Set OpenAI config from secrets
        if 'OPENAI_API_KEY' in secrets:
            os.environ['OPENAI_API_KEY'] = secrets['OPENAI_API_KEY']
            print(f"[DEBUG] Loaded OPENAI_API_KEY from secrets.toml")
        if 'OPENAI_MODEL' in secrets:
            os.environ['OPENAI_MODEL'] = secrets['OPENAI_MODEL']
        if 'OPENAI_MAX_TOKENS' in secrets:
            os.environ['OPENAI_MAX_TOKENS'] = str(secrets['OPENAI_MAX_TOKENS'])
        if 'OPENAI_TEMPERATURE' in secrets:
            os.environ['OPENAI_TEMPERATURE'] = str(secrets['OPENAI_TEMPERATURE'])
            
    except ImportError:
        print("[DEBUG] toml not installed, trying to parse manually")
        # Simple manual parsing for the OpenAI keys we care about.
        with open(secrets_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith('#') or '=' not in stripped:
                    continue

                key, raw_value = stripped.split('=', 1)
                key = key.replace(' ', '')
                if key not in {
                    'OPENAI_API_KEY',
                    'OPENAI_MODEL',
                    'OPENAI_MAX_TOKENS',
                    'OPENAI_TEMPERATURE',
                }:
                    continue

                value = raw_value.strip().strip('"').strip("'")
                os.environ[key] = value
                print(f"[DEBUG] Manually loaded {key}")


class Settings(BaseSettings):
    """Application settings"""
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4")
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "1000"))
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    
    # API Configuration
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    
    class Config:
        # Look for .env at the repository root.
        env_file = str(PROJECT_ROOT / ".env")
        case_sensitive = False
        extra = "ignore"


settings = Settings()


def is_openai_configured() -> bool:
    """Check if OpenAI is properly configured"""
    configured = bool(settings.openai_api_key)
    print(f"[DEBUG] OpenAI configured: {configured}")
    return configured
