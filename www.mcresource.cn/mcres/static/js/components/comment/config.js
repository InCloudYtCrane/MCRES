// static/js/components/comment/config.js
(function () {
    'use strict';

    window.Comments = window.Comments || {};

    Comments.cfg = {
        PAGE_SIZE: 20,
        CHILD_PAGE_SIZE: 20,
        MAX_LENGTH: 500,
        DEFAULT_REACTIONS: [
            { key: 'love',     emoji: '❤️', label: '爱了' },
            { key: 'laugh',    emoji: '😂', label: '笑不活了' },
            { key: 'learn',    emoji: '📖', label: '学到了' },
            { key: 'taste',    emoji: '✨', label: '有品位' },
            { key: 'melon',    emoji: '🍉', label: '吃瓜' },
            { key: 'confused', emoji: '🤔', label: '我不理解' }
        ]
    };

    Comments.state = {
        comments: [],
        currentPage: 1,
        totalPages: 1,
        totalCount: 0,
        totalNormalTop: 0,
        childPageMap: {},
        expandedThreads: {},
        reportTargetId: null,
        isSubmitting: false,
        currentPath: '',
        USER_INFO: window.USER_INFO || null,
        IS_LOGGED_IN: window.IS_LOGGED_IN || false,
        CURRENT_USER_ID: (window.CURRENT_USER_ID != null)
            ? Number(window.CURRENT_USER_ID) : null,
        REACTION_TYPES: Comments.cfg.DEFAULT_REACTIONS.slice(),
        REACTION_KEYS: Comments.cfg.DEFAULT_REACTIONS.map(function (t) { return t.key; }),
        EMOJI_LIST: [],          // ★ 站内表情列表
        dom: {}
    };

    Comments.loadReactionTypes = function () {
        return fetch('/comments/reactions', {
            credentials: 'same-origin',
            cache: 'default'
        })
        .then(function (res) {
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return res.json();
        })
        .then(function (data) {
            if (data && data.success && Array.isArray(data.data) && data.data.length > 0) {
                var valid = data.data.every(function (item) {
                    return item && item.key && item.emoji && item.label;
                });
                if (valid) {
                    Comments.state.REACTION_TYPES = data.data;
                    Comments.state.REACTION_KEYS = data.data.map(function (t) { return t.key; });
                    console.log('[表态] 已加载表态类型，共 ' + data.data.length + ' 种');
                } else {
                    console.warn('[表态] 数据结构异常，使用兜底值');
                }
            }
        })
        .catch(function (err) {
            console.warn('[表态] 加载失败，使用兜底值：', err);
        });
    };

    Comments.getReactionEmoji = function (key) {
        var found = Comments.state.REACTION_TYPES.find(function (t) { return t.key === key; });
        return found ? found.emoji : '😊';
    };

    // ============================================================
    // ★ 站内表情列表加载
    // ============================================================
    Comments.loadEmojiList = function () {
        return fetch('/comments/emojis', {
            credentials: 'same-origin',
            cache: 'default'
        })
        .then(function (res) {
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return res.json();
        })
        .then(function (data) {
            if (data && data.success && Array.isArray(data.data)) {
                var valid = data.data.filter(function (item) {
                    return item && item.key && item.url;
                });
                Comments.state.EMOJI_LIST = valid;
                console.log('[表情] 已加载 ' + valid.length + ' 个站内表情');
            }
        })
        .catch(function (err) {
            console.warn('[表情] 加载失败：', err);
        });
    };
})();