# utils/reset.py
import logging
from utils.data.repositories import users as users_repo
from utils.imaging.avatar import generate_and_save_avatar
from utils.scheduling.scheduler import archive_all_tables, backfill_all_daily_pv

logger = logging.getLogger(__name__)


def reset_all_avatars():
    """
    重置所有使用默认头像的用户头像，生成个性化头像
    """
    logger.info("开始重置所有默认头像...")

    # 查询所有头像为默认或空的用户
    users = users_repo.list_users_with_default_avatar()

    if not users:
        logger.info("没有需要重置头像的用户")
        return

    total = len(users)
    logger.info(f"找到 {total} 个用户需要重置头像")

    success_count = 0
    fail_count = 0

    for user in users:
        try:
            avatar_url = generate_and_save_avatar(user['id'], user['nickname'])
            users_repo.set_avatar(user['id'], avatar_url)
            success_count += 1
            logger.debug(f"用户 {user['nickname']}(ID:{user['id']}) 头像已更新")
        except Exception as e:
            fail_count += 1
            logger.error(f"用户 {user['nickname']}(ID:{user['id']}) 头像重置失败: {e}")

    logger.info(f"头像重置完成: 成功 {success_count}，失败 {fail_count}")


def reset_all():
    """
    执行所有重置操作（可扩展）
    """
    backfill_all_daily_pv()
    archive_all_tables()
    reset_all_avatars()
    # 未来可以在这里添加其他重置逻辑