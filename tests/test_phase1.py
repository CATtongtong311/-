"""Phase 1 验证脚本：测试配置、日志、数据库是否正常初始化。"""

import os
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_settings_validation():
    """测试配置管理：必填项缺失时应抛出异常。"""
    print("\n[1/4] 测试配置管理...")

    # 备份当前环境变量
    original_env = {k: os.environ.get(k) for k in [
        "FEISHU_APP_ID", "FEISHU_APP_SECRET", "TUSHARE_TOKEN",
        "CLAUDE_API_KEY", "KIMI_API_KEY"
    ]}

    try:
        # 清除所有相关环境变量，模拟无 .env 场景
        for k in original_env:
            os.environ.pop(k, None)

        # 重新导入以触发新的 Settings 实例
        import importlib
        from config import settings
        importlib.reload(settings)

        try:
            s = settings.Settings()
            s.validate()  # 启动时校验
            print("  [FAIL] 缺少必填配置时应拒绝启动")
            return False
        except ValueError as e:
            if "配置校验失败" in str(e):
                print("  [OK] 缺少必填配置时正确拒绝启动")
                return True
            raise
    finally:
        # 恢复环境变量
        for k, v in original_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)


def test_logger_setup():
    """测试日志系统初始化。"""
    print("\n[2/4] 测试日志系统...")

    from src.core.logger import setup_logger

    try:
        setup_logger()
        print("  [OK] 日志系统初始化完成")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_database_init():
    """测试数据库自动创建和表结构。"""
    print("\n[3/4] 测试数据库...")

    from src.core.database import init_db

    try:
        init_db()

        # 验证数据库文件是否存在
        db_path = PROJECT_ROOT / "data" / "app.db"
        if db_path.exists():
            print(f"  [OK] 数据库文件已创建 ({db_path})")
            return True
        else:
            print("  [FAIL] 数据库文件未创建")
            return False
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False


def test_models():
    """测试数据模型操作。"""
    print("\n[4/4] 测试数据模型...")

    from src.core.database import get_db, init_db
    from src.core.models import ApiCallLog, DiagnosisHistory, PortfolioCache

    try:
        init_db()
        db = get_db()

        # 测试写入持仓缓存
        PortfolioCache.create(
            symbol="000001",
            name="平安银行",
            cost_price=12.5,
            quantity=100,
            sector="银行",
        )

        # 测试写入诊断历史
        DiagnosisHistory.create(
            symbol="000001",
            name="平安银行",
            current_price=13.0,
            change_pct=2.5,
            analysis_text="测试分析",
            strategy="进攻型",
            score=75,
            llm_model="claude-sonnet-4-6",
        )

        # 测试写入 API 调用日志
        from datetime import date
        ApiCallLog.create(
            source="tushare",
            endpoint="daily",
            call_date=date.today(),
            call_count=10,
            error_count=0,
        )

        # 验证查询
        count = PortfolioCache.select().count()
        print(f"  [OK] 持仓缓存写入并查询通过 (记录数: {count})")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    finally:
        # 清理测试数据
        try:
            PortfolioCache.delete().execute()
            DiagnosisHistory.delete().execute()
            ApiCallLog.delete().execute()
        except Exception:
            pass


if __name__ == "__main__":
    print("=" * 50)
    print("Phase 1 验证：基础骨架")
    print("=" * 50)

    results = [
        test_settings_validation(),
        test_logger_setup(),
        test_database_init(),
        test_models(),
    ]

    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 50)
    print(f"结果: {passed}/{total} 通过")
    print("=" * 50)

    sys.exit(0 if passed == total else 1)
