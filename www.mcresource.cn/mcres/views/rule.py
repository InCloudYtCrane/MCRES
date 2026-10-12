# mcres/views/rule.py
from flask import Blueprint, render_template, abort, jsonify

from utils.data.repositories import site as site_repo
from utils.data.repositories import users as users_repo



rule_bp = Blueprint('rule', __name__)


@rule_bp.route('/rule/<string:rule_key>')
def view_rule(rule_key):
    """展示单条规则内容（含规则目录）"""
    # 获取所有活跃规则列表（用于侧边栏）
    all_rules = site_repo.list_active_rules_with_dates()
    if not all_rules:
        # 如果没有任何规则，可以显示一个友好提示
        return render_template('rule.html', rules=[], current_rule=None, error='暂无站内规则')

    # 查找当前规则
    current = None
    for r in all_rules:
        if r['rule_key'] == rule_key:
            current = r
            break
    if not current:
        abort(404, description='规则不存在')

    # 获取规则完整内容（content）
    row = site_repo.get_rule_by_key(rule_key)
    if not row:
        abort(404)

    # 获取创建者和更新者昵称（可选）
    #
    # 【bug 修复】原实现是：
    #     creator = get_nickname(row['created_by'])
    #     ... creator['nickname'] if creator else '系统'
    # 但 `users.get_nickname()` 返回的是**字符串**（不是行），
    # 于是 `str['nickname']` 抛 TypeError —— 任何一条有效规则页都会 500。
    # 这条路径在渲染回归里被 `/rule/1`（假数据里 rule_key 不匹配 → 提前 404）
    # 挡住了，所以基线一直是绿的。这里改成批量取昵称 + `.get(id, '系统')`，
    # 既修掉 500，也把两次查询合成一次。
    nick_map = users_repo.get_nicknames(
        [row['created_by'], row['updated_by']])

    rule_data = {
        'rule_key': rule_key,
        'title': row['title'],
        'content': row['content'],
        'updated_at': row['updated_at'],
        'created_by_nick': nick_map.get(row['created_by'], '系统'),
        'updated_by_nick': nick_map.get(row['updated_by'], '系统')
    }

    return render_template('rule.html',
                           rules=all_rules,
                           current_rule=rule_data,
                           error=None)


@rule_bp.route('/rule/<string:rule_key>/versions')
def get_rule_versions(rule_key):
    rows = site_repo.list_rule_versions(rule_key)
    versions = []
    for row in rows:
        versions.append({
            'version': row['version'],
            'title': row['title'],
            'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
            'is_active': bool(row['is_active'])
        })
    return jsonify(versions)


@rule_bp.route('/rule/<string:rule_key>/version/<int:version>')
def get_rule_version(rule_key, version):
    row = site_repo.get_rule_version(rule_key, version)
    if not row:
        return jsonify({'error': '版本不存在'}), 404
    return jsonify({'title': row['title'], 'content': row['content']})