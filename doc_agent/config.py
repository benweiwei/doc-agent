"""Configuration management for doc-agent."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load .env file early
load_dotenv()


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = "127.0.0.1"
    port: int = 3966
    auto_open_browser: bool = True


class CloudModelConfig(BaseModel):
    """Cloud LLM provider configuration."""

    service: Literal["anthropic", "openai"] = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key_env: str = "ANTHROPIC_API_KEY"
    api_key: Optional[str] = None  # Direct API key (takes precedence over env var)
    base_url: Optional[str] = None  # Custom base URL for OpenAI-compatible APIs


class LocalModelConfig(BaseModel):
    """Local LLM provider configuration."""

    service: Literal["ollama"] = "ollama"
    model: str = "llama3"
    endpoint: str = "http://localhost:11434"


class ModelConfig(BaseModel):
    """LLM model configuration."""

    provider: Literal["cloud", "local"] = "cloud"
    cloud: CloudModelConfig = Field(default_factory=CloudModelConfig)
    local: LocalModelConfig = Field(default_factory=LocalModelConfig)
    fallback: bool = False


class StyleConfig(BaseModel):
    """Writing style configuration."""

    default_template: Optional[str] = None
    habit_profile: Optional[str] = None


class WorkspaceConfig(BaseModel):
    """Workspace configuration."""

    path: str = "~/.doc-agent/workspace"


class SearchConfig(BaseModel):
    """Web search backend configuration."""

    provider: Literal["duckduckgo", "tavily", "brave", "bocha"] = "duckduckgo"
    api_key_env: Optional[str] = None  # env var holding the API key (tavily/brave/bocha)
    api_key: Optional[str] = None  # direct API key (takes precedence over api_key_env)


class AgentConfig(BaseModel):
    """Agent loop (tool-use) configuration."""

    max_steps: int = 10  # max tool-use iterations before forcing a stop
    token_budget: int = 0  # cumulative output-token budget; 0 = unlimited
    enable_web_search: bool = True
    search: SearchConfig = Field(default_factory=SearchConfig)


class AppConfig(BaseSettings):
    """Application configuration.

    Priority: environment variables > config.yaml > defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix="DOC_AGENT_",
        env_nested_delimiter="__",
    )

    server: ServerConfig = Field(default_factory=ServerConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    style: StyleConfig = Field(default_factory=StyleConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)


def _find_config_file(config_path: Optional[Path] = None) -> Optional[Path]:
    """Search for config file in standard locations.

    Search order:
    1. Explicitly specified path
    2. ./config.yaml in current directory
    3. ~/.doc-agent/config.yaml
    """
    if config_path is not None:
        resolved = Path(config_path).resolve()
        if resolved.is_file():
            return resolved
        return None

    # Current directory
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.is_file():
        return cwd_config

    # User home directory
    home_config = Path.home() / ".doc-agent" / "config.yaml"
    if home_config.is_file():
        return home_config

    return None


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """Load configuration from file and environment.

    Priority: environment variables > config.yaml > defaults.

    Args:
        config_path: Optional explicit path to config.yaml.

    Returns:
        Fully resolved AppConfig instance.
    """
    config_file = _find_config_file(config_path)

    if config_file is None:
        return AppConfig()

    with open(config_file, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f) or {}

    # Build nested config from YAML, then let pydantic-settings overlay env vars
    return AppConfig(**yaml_data)
