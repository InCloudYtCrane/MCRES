# utils/scheduler_manager.py
"""
定时任务管理器 - 使用 APScheduler
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from utils.scheduling.scheduler import archive_all_tables
from mcres.ip_service import cleanup_old_violations
import logging
import atexit

logger = logging.getLogger(__name__)

# 全局调度器实例
_scheduler = None


def init_scheduler(app=None):
    """
    初始化并启动调度器
    每天凌晨 00:05 执行归档任务
    每天凌晨 03:30 清理过期 IP 违规记录
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("调度器已初始化，跳过重复初始化")
        return _scheduler

    _scheduler = BackgroundScheduler(timezone='Asia/Shanghai')

    # 每天凌晨 00:05 执行归档
    _scheduler.add_job(
        func=archive_all_tables,
        trigger=CronTrigger(hour=0, minute=5),
        id='archive_daily',
        name='全量归档昨日数据',
        replace_existing=True,
        max_instances=1
    )

    # 每天凌晨 03:30 清理过期违规记录
    _scheduler.add_job(
        func=cleanup_old_violations,
        trigger=CronTrigger(hour=3, minute=30),
        id='cleanup_ip_violations',
        name='清理过期 IP 违规记录',
        replace_existing=True,
        max_instances=1
    )

    _scheduler.start()
    logger.info("✅ 定时调度器已启动，归档任务将在每天 00:05 执行")
    logger.info("✅ IP 违规记录清理任务将在每天 03:30 执行")

    # 注册关闭钩子
    atexit.register(shutdown_scheduler)

    return _scheduler


def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("⏹️ 调度器已关闭")


def run_archive_now():
    """立即执行归档（用于测试或手动触发）"""
    logger.info("手动触发全量归档...")
    return archive_all_tables()