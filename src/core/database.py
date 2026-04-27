"""数据库连接管理，基于 peewee + SQLite。"""

from pathlib import Path

from peewee import SqliteDatabase

from config.settings import get_settings

_db_instance: SqliteDatabase | None = None


def get_db() -> SqliteDatabase:
    """获取 SQLite 数据库单例，自动创建数据库文件和目录。"""
    global _db_instance
    if _db_instance is None:
        settings = get_settings()
        db_path = settings.database.url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _db_instance = SqliteDatabase(db_path, pragmas={
            "journal_mode": "wal",       # WAL 模式提升并发性能
            "foreign_keys": 1,           # 启用外键约束
            "synchronous": "normal",     # 平衡性能与安全性
        })
    return _db_instance


def init_db() -> None:
    """初始化数据库：创建所有表。"""
    from src.core.models import ApiCallLog, DiagnosisHistory, PortfolioCache

    db = get_db()
    db.create_tables([PortfolioCache, DiagnosisHistory, ApiCallLog], safe=True)
