# utils/scheduler.py
"""
定时任务核心逻辑
负责每天凌晨自动归档所有资源的昨日数据 + 名誉恢复 + 保存每日PV
+ 成就评定 + 清理过期软删评论

【Phase 5 变更】
  daily_pv_stats JSON 字段不再读写，PV 存储改到 resource_daily_pv 表。
  该 JSON 字段保留做历史备份。
"""
from datetime import datetime, timedelta
import logging

from utils.constants import RESOURCE_TABLE
from utils.data.repositories import resources as resources_repo
from utils.data.repositories import scheduling as scheduling_repo
from utils.data.repositories import system as system_repo

logger = logging.getLogger(__name__)


# ============================================================
#  清理过期软删评论
# ============================================================
def cleanup_deleted_comments(days=30):
    """
    物理删除 N 天前软删的评论（含其表态）。

    · 只删 is_deleted = 1 且 created_at 超过 N 天的
    · 先删关联的 reactions（避免孤儿）
    · 单次最多删 2000 条，防止一次锁表太久
    · 如超出 2000，下次调度会继续删
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

    rows = scheduling_repo.list_purgeable_comment_ids(cutoff) or []

    if not rows:
        logger.info('[清理] 没有需要清理的过期评论')
        return 0

    ids = [r['id'] for r in rows]

    try:
        scheduling_repo.delete_comment_reactions(ids)
    except Exception as e:
        logger.warning(f'[清理] 删除表态失败（不影响评论删除）: {e}')

    affected = scheduling_repo.delete_comments(ids)

    logger.info(f'[清理] 物理删除过期评论 {affected} 条')
    return affected


# ============================================================
#  保存每日 PV 到表（Phase 5）
# ============================================================
def save_daily_pv():
    """
    从 resource_view_log 聚合前一天的 PV，写入 resource_daily_pv 表。
    保证所有资源（包括 PV=0 的）都有当天的记录，趋势图连续。
    """
    yesterday = (datetime.now() - timedelta(days=1)).date()
    yesterday_str = yesterday.isoformat()

    logger.info(f"开始从 resource_view_log 聚合 {yesterday_str} 的PV")

    # ---------- 1. 聚合：昨天有 PV 的 (type, id) → count ----------
    rows = scheduling_repo.aggregate_daily_pv(yesterday_str) or []

    pv_map = {(r['resource_type'], r['resource_id']): r['pv_count'] for r in rows}
    logger.info(f"聚合完成，共 {len(pv_map)} 个资源有PV记录")

    # ---------- 2. 遍历三张表所有资源，逐一写入（含 0） ----------
    total_updated = 0

    for res_type, table_name in RESOURCE_TABLE.items():
        all_resources = resources_repo.get_ids(res_type) or []
        if not all_resources:
            logger.info(f"{table_name} 无数据，跳过")
            continue

        updated_count = 0

        for resource in all_resources:
            res_id = resource['id']
            pv_count = pv_map.get((res_type, res_id), 0)

            scheduling_repo.upsert_daily_pv(res_type, res_id, yesterday_str, pv_count)
            updated_count += 1

        total_updated += updated_count
        logger.info(f"{table_name} 更新完成: {updated_count} 个资源")

    # ---------- 3. 清理 365 天前的旧记录（与原 JSON 逻辑一致） ----------
    try:
        affected = scheduling_repo.delete_daily_pv_older_than_365d()
        if affected:
            logger.info(f"清理 365 天前数据，删除 {affected} 行")
    except Exception as e:
        logger.warning(f"清理 365 天前数据失败: {e}")

    logger.info(f"PV保存完成，共更新 {total_updated} 个资源的 resource_daily_pv")


# ============================================================
#  一次性历史补全函数（Phase 5 后版本）
# ============================================================
def backfill_all_daily_pv():
    """
    一次性补全所有资源的历史 PV 数据。
    从 resource_view_log 聚合每一天的 PV，写入 resource_daily_pv。
    已存在的日期不会被覆盖（INSERT IGNORE）。

    使用场景：
      · resource_view_log 有数据修正，需要重新聚合
      · 表被清空后需要重建历史
    """
    logger.info("===== 开始历史数据补全 =====")

    # ---------- 1. 拿所有有 PV 记录的日期 ----------
    date_rows = scheduling_repo.list_pv_dates() or []

    if not date_rows:
        logger.warning("resource_view_log 表无数据，无需补全")
        return

    dates = [row['date'] for row in date_rows]
    logger.info(f"共找到 {len(dates)} 个有 PV 记录的日期: {dates[0]} ~ {dates[-1]}")

    total_added = 0

    for date_obj in dates:
        date_str = date_obj.isoformat()

        # 该日期所有资源的 PV 聚合（一次拿全）
        pv_rows = scheduling_repo.aggregate_daily_pv_for_backfill(date_obj) or []
        pv_map = {(r['resource_type'], r['resource_id']): r['cnt'] for r in pv_rows}

        for res_type, table_name in RESOURCE_TABLE.items():
            all_resources = resources_repo.get_ids(res_type) or []
            for resource in all_resources:
                res_id = resource['id']
                pv_count = pv_map.get((res_type, res_id), 0)

                affected = scheduling_repo.insert_daily_pv_if_absent(
                    res_type, res_id, date_str, pv_count
                )
                if affected:
                    total_added += 1

        logger.info(f"日期 {date_str} 处理完成")

    logger.info(f"===== 历史数据补全完成，新增 {total_added} 行 =====")


# ============================================================
#  全量归档
# ============================================================
def archive_all_tables():
    """
    全量归档 + 保存每日PV + 名誉恢复 + 成就评定 + 清理过期评论

    执行顺序：
    1. 从 resource_view_log 聚合前一天的PV，写入 resource_daily_pv
    2. 将 today_view_count 转入 yesterday_view_count，重置 today_view_count
    3. 名誉恢复
    4. 成就评定 + 清理过期进度
    5. 清理过期软删评论
    """
    today = datetime.now().date().isoformat()
    logger.info(f"开始全量归档，日期: {today}")

    try:
        # ========== 1. 保存PV到表 ==========
        save_daily_pv()

        # ========== 2~4. 归档三张资源表（表清单收敛到 RESOURCE_TABLE） ==========
        roll_results = system_repo.roll_over_daily_view_counts(today)
        for table_name, affected in roll_results.items():
            logger.info(f"{table_name} 归档完成，影响行数: {affected}")

        # ========== 5. 更新归档状态表 ==========
        system_repo.upsert_archive_status(today)

        # ========== 6. 每日名誉恢复 ==========
        result_reputation = scheduling_repo.restore_daily_reputation()
        logger.info(f"名誉恢复完成，影响行数: {result_reputation}")

        # ========== 7. 成就评定 + 清理过期进度 ==========
        try:
            from utils.achievements import evaluate_all, cleanup_old_periods
            evaluate_all()
            cleanup_old_periods(days=7)
        except Exception as e:
            logger.exception(f"成就评定失败: {e}")

        # ========== 8. 清理过期软删评论 ==========
        try:
            cleanup_deleted_comments(days=30)
        except Exception as e:
            logger.exception(f"清理过期评论失败: {e}")

        logger.info(f"全量归档 + PV保存 + 名誉恢复 + 成就评定 + 评论清理 全部完成！日期: {today}")
        return True

    except Exception as e:
        logger.error(f"全量归档失败: {e}")
        return False


def get_last_archive_date():
    """获取上次归档日期"""
    row = system_repo.get_archive_status()
    if row and row.get('last_archive_date'):
        return row['last_archive_date']
    return None