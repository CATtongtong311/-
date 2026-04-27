"""应用入口：启动飞书网关和定时任务调度器。"""

import signal
import sys
from pathlib import Path

from loguru import logger

from config.settings import get_settings
from src.core.database import init_db
from src.feishu.gateway import FeishuGateway
from src.orchestrator import BotOrchestrator
from src.scheduler.jobs import SchedulerManager


def main():
    """启动机器人服务。"""
    logger.info("=" * 50)
    logger.info("智能金融晨报与交互分析系统 启动中...")
    logger.info("=" * 50)

    # 1. 加载并校验配置
    settings = get_settings()
    try:
        settings.validate()
        logger.info("配置校验通过")
    except ValueError as e:
        logger.error("配置错误: {}", e)
        sys.exit(1)

    # 2. 初始化数据库
    init_db()
    logger.info("数据库初始化完成")

    # 3. 创建中央调度器
    orchestrator = BotOrchestrator(settings)
    logger.info("中央调度器就绪")

    # 4. 创建飞书网关
    gateway = FeishuGateway(
        app_id=settings.feishu.app_id,
        app_secret=settings.feishu.app_secret,
        encrypt_key=settings.feishu.encrypt_key,
        verification_token=settings.feishu.verification_token,
        on_message=orchestrator.handle_message,
    )
    logger.info("飞书网关就绪")

    # 5. 创建定时任务调度器
    scheduler = SchedulerManager(
        morning_report_func=orchestrator.send_morning_report,
        chat_id=getattr(settings.feishu, "default_chat_id", ""),
        hour=8,
        minute=30,
    )
    logger.info("定时调度器就绪")

    # 6. 启动服务
    gateway.start()
    scheduler.start()
    logger.info("所有服务已启动，按 Ctrl+C 停止")

    # 7. 优雅退出
    def shutdown(signum, frame):
        logger.info("正在关闭服务...")
        scheduler.stop()
        gateway.stop()
        logger.info("服务已停止")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 阻塞主线程
    try:
        while gateway.is_running():
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
