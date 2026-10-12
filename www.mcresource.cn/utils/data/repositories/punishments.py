# utils/data/repositories/punishments.py
"""处罚执行器的落库查询。

目前只有违禁词触发的 `forbidden_log` 写入（原先内联在
`utils/users/punishment.py`）。名誉扣减与角色/封禁字段的读写都在 `users.py`，
因为它们都是 `user_info` 上的单列写入。
"""
from utils.data import execute_update


def insert_forbidden_log(user_id, level, matched_keywords_json,
                         reputation_after, punishment, created_at):
    """记录一条违禁词触发日志。"""
    return execute_update('''
        INSERT INTO forbidden_log
        (user_id, level, matched_keywords, reputation_after, punishment_applied, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', [
        user_id,
        level,
        matched_keywords_json,
        reputation_after,
        punishment,
        created_at,
    ])
