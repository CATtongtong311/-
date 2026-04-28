"""应用配置管理，基于 pydantic-settings，支持 .env 文件和环境变量。"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


_ENV_FILE = str(PROJECT_ROOT / ".env")


class FeishuConfig(BaseSettings):
    """飞书应用配置。"""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", env_prefix="FEISHU_", extra="ignore"
    )

    app_id: str = Field(default="", description="飞书自建应用 App ID")
    app_secret: str = Field(default="", description="飞书自建应用 App Secret")
    encrypt_key: str = Field(default="", description="消息加密密钥（可选）")
    verification_token: str = Field(default="", description="Webhook 校验 Token（可选）")
    default_chat_id: str = Field(default="", description="默认推送群聊 ID（晨报/预拉取通知）")


class DataSourceConfig(BaseSettings):
    """数据源配置。"""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", env_prefix="TUSHARE_", extra="ignore"
    )

    token: str = Field(default="", description="Tushare Pro Token")
    itick_token: str = Field(default="", description="iTick API Token")


class LLMConfig(BaseSettings):
    """LLM API 配置。"""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    claude_api_key: str = Field(default="", description="Claude API Key")
    kimi_api_key: str = Field(default="", description="Kimi / Moonshot API Key")

    @field_validator("claude_api_key", "kimi_api_key", mode="before")
    @classmethod
    def strip_spaces(cls, v: str) -> str:
        return v.strip() if isinstance(v, str) else v


class DatabaseConfig(BaseSettings):
    """数据库配置。"""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", env_prefix="DATABASE_", extra="ignore"
    )

    url: str = Field(
        default=f"sqlite:///{PROJECT_ROOT / 'data' / 'app.db'}",
        description="SQLite 数据库连接字符串",
    )


class LogConfig(BaseSettings):
    """日志配置。"""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", env_prefix="LOG_", extra="ignore"
    )

    level: str = Field(default="INFO", description="日志级别")
    file: str = Field(
        default=str(PROJECT_ROOT / "logs" / "app.log"),
        description="日志文件路径",
    )


class Settings(BaseSettings):
    """应用全局配置。"""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    data_source: DataSourceConfig = Field(default_factory=DataSourceConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    log: LogConfig = Field(default_factory=LogConfig)

    def check_llm_key(self) -> str:
        """返回可用的 LLM API Key，仅使用 Kimi。"""
        if self.llm.kimi_api_key:
            return "kimi"
        raise ValueError(
            "未配置 Kimi API Key。请在 .env 中设置 KIMI_API_KEY。"
        )

    def validate(self) -> None:
        """启动时校验必填配置，缺失时给出明确错误。"""
        errors = []
        if not self.feishu.app_id:
            errors.append("FEISHU_APP_ID: 飞书自建应用 App ID 未配置")
        if not self.feishu.app_secret:
            errors.append("FEISHU_APP_SECRET: 飞书自建应用 App Secret 未配置")
        if not self.data_source.token:
            errors.append("TUSHARE_TOKEN: Tushare Pro Token 未配置")

        if errors:
            raise ValueError(
                "配置校验失败，请检查 .env 文件或环境变量：\n  - "
                + "\n  - ".join(errors)
            )


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例。"""
    return Settings()
