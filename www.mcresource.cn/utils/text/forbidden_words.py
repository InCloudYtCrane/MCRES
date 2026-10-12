# utils/forbidden_words.py
"""
违禁词检测器
核心原则：
1. 自上而下：从处罚最严重的等级开始遍历，匹配后立即停止
2. 同级合并：同一处罚等级下的多个词库合并检测，仅算一次
3. 不叠加：不同等级包含同一关键词时，取最严重等级，较轻的不计算
4. 组合匹配：使用 + 连接的词必须同时出现才触发（存储在 combination.txt）
"""
import json
import os
from datetime import datetime

CONFIG_PATH = os.path.join(os.getcwd(), 'forbidden_words.json')
WORDS_DIR = os.path.join(os.getcwd(), 'forbidden_words')


class ForbiddenDetector:
    """违禁词检测器（单例模式，支持热加载）"""

    _instance = None
    _config = None
    _words_cache = {}          # 缓存已加载的词汇
    _combination_cache = {}    # 缓存已加载的组合词汇
    _file_mtimes = {}          # 记录每个 txt 文件的修改时间
    _config_mtime = None       # 记录 JSON 配置的修改时间

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ==================== 词库加载 ====================

    def _load_words_from_file(self, filename):
        """
        从 txt 文件加载关键词列表
        每行一个关键词，空行和 # 开头的行被忽略
        """
        filepath = os.path.join(WORDS_DIR, filename)
        if not os.path.exists(filepath):
            return []

        # 检查文件是否变化（热加载）
        mtime = os.path.getmtime(filepath)
        cache_key = f'words_{filename}'
        if cache_key in self._file_mtimes and self._file_mtimes[cache_key] == mtime:
            return self._words_cache.get(filename, [])

        self._file_mtimes[cache_key] = mtime

        words = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # 如果行中包含 +，说明是组合词，跳过（由专门方法处理）
                    if '+' not in line:
                        words.append(line)
        self._words_cache[filename] = words
        return words

    def _load_combination_from_file(self, filename):
        """
        从 txt 文件加载组合词汇
        每行格式：词1+词2+词3（必须同时存在才触发）
        返回：[[词1, 词2, 词3], [词A, 词B], ...]
        """
        filepath = os.path.join(WORDS_DIR, filename)
        if not os.path.exists(filepath):
            return []

        # 检查文件是否变化（热加载）
        mtime = os.path.getmtime(filepath)
        cache_key = f'comb_{filename}'
        if cache_key in self._file_mtimes and self._file_mtimes[cache_key] == mtime:
            return self._combination_cache.get(filename, [])

        self._file_mtimes[cache_key] = mtime

        combinations = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # 检查是否包含 +，说明是组合词
                    if '+' in line:
                        parts = [p.strip() for p in line.split('+') if p.strip()]
                        if len(parts) >= 2:  # 至少2个词才算组合
                            combinations.append(parts)
        self._combination_cache[filename] = combinations
        return combinations

    def _load_words_from_files(self, filenames):
        """从多个 txt 文件加载关键词，合并去重"""
        all_words = []
        seen = set()
        for filename in filenames:
            words = self._load_words_from_file(filename)
            for w in words:
                if w not in seen:
                    seen.add(w)
                    all_words.append(w)
        return all_words

    def _load_combinations_from_files(self, filenames):
        """从多个 txt 文件加载组合词汇，合并去重"""
        all_combinations = []
        seen = set()
        for filename in filenames:
            combos = self._load_combination_from_file(filename)
            for combo in combos:
                key = '+'.join(combo)
                if key not in seen:
                    seen.add(key)
                    all_combinations.append(combo)
        return all_combinations

    # ==================== 配置加载 ====================

    def _load_config(self):
        """加载 JSON 配置文件"""
        if not os.path.exists(CONFIG_PATH):
            return {'levels': [], 'global': {'exempt_roles': [3, 4], 'auto_delete': True}}

        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _need_reload(self):
        """检查配置或词库是否需要重新加载"""
        if not os.path.exists(CONFIG_PATH):
            return False

        # 检查 JSON 配置是否变化
        mtime = os.path.getmtime(CONFIG_PATH)
        if self._config_mtime is None or mtime != self._config_mtime:
            self._config_mtime = mtime
            return True

        # 检查配置文件里引用的所有 txt 文件是否变化
        config = self._config or self._load_config()
        for level in config.get('levels', []):
            for filename in level.get('files', []):
                filepath = os.path.join(WORDS_DIR, filename)
                if os.path.exists(filepath):
                    current_mtime = os.path.getmtime(filepath)
                    words_key = f'words_{filename}'
                    comb_key = f'comb_{filename}'
                    if words_key not in self._file_mtimes or self._file_mtimes[words_key] != current_mtime:
                        return True
                    if comb_key not in self._file_mtimes or self._file_mtimes[comb_key] != current_mtime:
                        return True
        return False

    def get_config(self):
        """获取配置（自动热加载）"""
        if self._need_reload() or self._config is None:
            self._config = self._load_config()
        return self._config

    # ==================== 核心检测 ====================

    def check(self, text):
        """
        检测文本是否包含违禁词
        遵循原则：
        1. 自上而下：按 levels 顺序遍历（从严重到轻微），匹配后立即停止
        2. 同级合并：同一等级下多个文件合并检测，仅算一次
        3. 不叠加：取最严重等级，较轻的不计算
        4. 组合匹配：+ 连接的词必须全部出现才触发

        返回: (level, matched_keywords, level_config) 或 (None, [], None)
        """
        if not text:
            return None, [], None

        config = self.get_config()
        text_lower = text.lower()

        # 自上而下遍历（从最严重到最轻）
        for level_config in config.get('levels', []):
            filenames = level_config.get('files', [])
            if not filenames:
                continue

            # ----- 1. 检测普通词汇（同级合并） -----
            all_words = self._load_words_from_files(filenames)
            matched = []
            for kw in all_words:
                if kw.lower() in text_lower:
                    matched.append(kw)

            # 如果普通词汇有匹配，立即返回
            if matched:
                return level_config['level'], matched, level_config

            # ----- 2. 检测组合词汇（同级合并） -----
            all_combinations = self._load_combinations_from_files(filenames)
            for combo in all_combinations:
                # 检查组合中的所有词是否都在文本中
                all_found = True
                for word in combo:
                    if word.lower() not in text_lower:
                        all_found = False
                        break
                if all_found:
                    # 组合匹配成功，返回组合词作为匹配结果
                    matched_str = '+'.join(combo)
                    return level_config['level'], [matched_str], level_config

        return None, [], None

    # ==================== 全局配置 ====================

    def get_exempt_roles(self):
        config = self.get_config()
        return config.get('global', {}).get('exempt_roles', [3, 4])

    def should_auto_delete(self):
        config = self.get_config()
        return config.get('global', {}).get('auto_delete', True)

    def should_notify_user(self):
        config = self.get_config()
        return config.get('global', {}).get('notify_user', True)

    def should_log_trigger(self):
        config = self.get_config()
        return config.get('global', {}).get('log_trigger', True)


# 全局单例
detector = ForbiddenDetector()