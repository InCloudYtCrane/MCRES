# utils/afdian_reply.py
"""
调用 DeepSeek API 为爱发电订单留言生成简短感谢回复。
"""
import os
import logging

import requests

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
DEEPSEEK_MODEL = 'deepseek-chat'

# ------------------------------------------------------------
# 系统提示词：严格约束 AI，避免说出不该说的话
# ------------------------------------------------------------
_SYSTEM_PROMPT = """你是「方块工坊」（MCRES）的站长，一个非营利性质的 Minecraft 知识共享与社区站点。
用户刚刚通过爱发电勉励了你的站点，并可能留下了留言。
请根据用户的留言，写一段简短、真诚的感谢回复。

硬性要求：
1. 20个以内的汉字，一句话或两句话
2. 语气克制、亲切，不要过分热情、不要用感叹号堆砌，但可以稍显活泼可爱
3. 不要使用 emoji、网络流行语、颜文字
4. 不要承诺任何回报、特权、优先服务、专属内容
5. 不要提及"钱"、"金额"、"赞助级别"
6. 如果留言为空、只有一个符号、或与站点无关，就简单表达感谢
7. 直接输出回复正文，不要任何前缀、解释、引号、标点符号以外的修饰
8. 不要像AI生成的
9. 如果用户有互动，你也可以进行简单互动
"""


def generate_reply(remark, nickname='爱心人士', amount=0):
    """
    调用 DeepSeek API 生成回复。
    成功返回字符串；失败或无 key 返回 None。
    """
    if not DEEPSEEK_API_KEY:
        logger.warning('[afdian_reply] 未配置 DEEPSEEK_API_KEY，跳过')
        return None

    # 留言为空直接返回 None，让 webhook 跳过
    if not remark or not remark.strip():
        return None

    user_content = (
        f"用户昵称：{nickname}\n"
        f"勉励金额：¥{amount:.2f}\n"
        f"留言原文：{remark.strip()[:300]}"
    )

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': DEEPSEEK_MODEL,
                'messages': [
                    {'role': 'system', 'content': _SYSTEM_PROMPT},
                    {'role': 'user',   'content': user_content},
                ],
                'max_tokens': 200,
                'temperature': 0.7,
                'stream': False,
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        content = (content or '').strip()

        # 去掉可能出现的引号
        content = content.strip('"').strip('“”').strip("'").strip('‘’').strip()

        # 简单校验：长度合理，无换行
        if not content:
            return None
        if len(content) < 5 or len(content) > 200:
            logger.warning(f'[afdian_reply] 长度异常: {len(content)} 字')
            return None
        if '\n' in content:
            content = content.split('\n')[0].strip()

        return content

    except requests.exceptions.RequestException as e:
        logger.warning(f'[afdian_reply] 请求失败: {e}')
        return None
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f'[afdian_reply] 解析响应失败: {e}')
        return None
    except Exception as e:
        logger.exception(f'[afdian_reply] 未知错误: {e}')
        return None