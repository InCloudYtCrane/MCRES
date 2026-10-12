// static/js/components/comment/render.js
(function () {
    'use strict';

    var C = window.Comments;
    var state = C.state;
    var esc = function (t) { return C.utils.escapeHtml(t); };

    function buildThreadedComments(flatComments) {
        var top = [];
        var childrenMap = {};
        flatComments.forEach(function (c) {
            if (!c.parent_id) {
                top.push(c);
            } else {
                if (!childrenMap[c.parent_id]) childrenMap[c.parent_id] = [];
                childrenMap[c.parent_id].push(c);
            }
        });
        for (var pid in childrenMap) {
            childrenMap[pid].sort(function (a, b) {
                return (a.created_at || '').localeCompare(b.created_at || '');
            });
        }
        return { top: top, childrenMap: childrenMap };
    }

    function renderComments() {
        var listEl = state.dom.listEl;
        var countEl = state.dom.countEl;
        var emptyEl = state.dom.emptyEl;
        var paginationTop = state.dom.paginationTop;
        var paginationBottom = state.dom.paginationBottom;
        if (!listEl) return;

        if (state.comments.length === 0) {
            listEl.innerHTML = '';
            emptyEl.style.display = 'flex';
            countEl.textContent = '0';
            paginationTop.style.display = 'none';
            paginationBottom.style.display = 'none';
            return;
        }
        emptyEl.style.display = 'none';

        var result = buildThreadedComments(state.comments);
        var top = result.top;
        var childrenMap = result.childrenMap;

        countEl.textContent = state.totalCount || state.comments.length;

        var pinnedTop = top.filter(function (c) { return c.is_pinned === true; });
        var normalTop = top.filter(function (c) { return !c.is_pinned; });

        var startIdx = (state.currentPage - 1) * C.cfg.PAGE_SIZE;
        normalTop.forEach(function (c, localIdx) {
            c._floorNumber = state.totalNormalTop - startIdx - localIdx;
        });

        var paginationHtml = C.pagination.generateHtml(state.currentPage, state.totalPages);
        if (state.totalPages > 1) {
            paginationTop.style.display = 'flex';
            paginationTop.innerHTML = paginationHtml;
            paginationBottom.style.display = 'flex';
            paginationBottom.innerHTML = paginationHtml;
        } else {
            paginationTop.style.display = 'none';
            paginationBottom.style.display = 'none';
        }

        var html = '';
        pinnedTop.forEach(function (c) { html += renderCommentItem(c, childrenMap, true); });
        normalTop.forEach(function (c) { html += renderCommentItem(c, childrenMap, false); });

        listEl.innerHTML = html;

        // ★ 防御：即使 events.js 加载失败也不会崩
        if (C.events && typeof C.events.bindCommentEvents === 'function') {
            C.events.bindCommentEvents();
        } else {
            console.warn('[render] C.events 未就绪，跳过事件绑定');
        }
        if (C.pagination && typeof C.pagination.bindEvents === 'function') {
            C.pagination.bindEvents();
        }
    }

    // ============================================================
    // 单条评论（桌面 / 移动）
    // ============================================================
    function renderCommentItem(c, childrenMap, isPinned) {
        var avatar = c.avatar || '/images/avatar/default.jpg';
        var nickname = c.nickname || '匿名用户';
        var time = c.created_at || '';
        var content = c.content || '';
        // ★ 优先用后端渲染好的 HTML（含表情图片），无则走纯文本转义兜底
        var contentHtml = c.content_html || esc(content);

        var profileUrl = '/profile/' + c.user_id;
        var canDelete = c.can_delete === true;
        var canReport = state.IS_LOGGED_IN && c.user_id !== state.CURRENT_USER_ID;
        var canPin = c.can_pin === true && !c.parent_id;
        var isPinnedFlag = c.is_pinned === true;
        var isOwnComment = c.user_id === state.CURRENT_USER_ID;

        // ★ IP 属地（省级），"未知" 也不显示
        var ipRegionHtml = (c.ip_region && c.ip_region !== '未知')
            ? '<span class="comment-ip">' + esc(c.ip_region) + '</span>'
            : '';

        var titleHtml = c.title
            ? '<span class="user-title-badge" style="background-color:' + c.title.color + ';color:#fff;">' + esc(c.title.text) + '</span>'
            : '';

        var reactions = c.reactions || {};
        var userReaction = c.user_reaction || null;
        var totalReactions = state.REACTION_KEYS.reduce(function (s, k) {
            return s + (reactions[k] || 0);
        }, 0);

        // ---------- 桌面端 ----------
        if (!C.utils.isMobile()) {
            var floorLabel;
            if (isPinnedFlag) {
                floorLabel = '置顶';
            } else {
                var floor = c._floorNumber;
                if (floor === 1) floorLabel = '沙发';
                else if (floor === 2) floorLabel = '板凳';
                else if (floor === 3) floorLabel = '地板';
                else floorLabel = floor + '楼';
            }
            var isSpecial = !isPinnedFlag && ['沙发', '板凳', '地板'].indexOf(floorLabel) !== -1;

            var reactionStatsHtml = '';
            var triggerHtml = '';
            var reactionPickerHtml = '';

            if (!isOwnComment) {
                state.REACTION_TYPES.forEach(function (rt) {
                    var count = reactions[rt.key] || 0;
                    var isActive = userReaction === rt.key;
                    if (count > 0 || isActive) {
                        reactionStatsHtml += '<button class="reaction-stat' + (isActive ? ' active' : '') + '" data-reaction="' + rt.key + '" title="' + rt.label + '">' +
                            '<span class="reaction-emoji">' + rt.emoji + '</span>' +
                            '<span class="reaction-count-num">' + count + '</span></button>';
                    }
                });
                if (!userReaction) {
                    triggerHtml = '<button class="reaction-trigger" title="表态"><i class="fas fa-smile"></i></button>';
                }
                reactionPickerHtml = '<div class="reaction-picker">' +
                    state.REACTION_TYPES.map(function (rt) {
                        return '<button class="reaction-option' + (rt.key === userReaction ? ' active' : '') + '" data-reaction="' + rt.key + '">' +
                            '<span class="reaction-emoji">' + rt.emoji + '</span>' +
                            '<span class="reaction-label">' + rt.label + '</span></button>';
                    }).join('') + '</div>';
            } else {
                state.REACTION_TYPES.forEach(function (rt) {
                    var count = reactions[rt.key] || 0;
                    if (count > 0) {
                        reactionStatsHtml += '<span class="reaction-stat readonly" title="' + rt.label + '">' +
                            '<span class="reaction-emoji">' + rt.emoji + '</span>' +
                            '<span class="reaction-count-num">' + count + '</span></span>';
                    }
                });
            }

            var reactionHtml = '';
            if (reactionStatsHtml || triggerHtml) {
                var roClass = isOwnComment ? ' readonly' : '';
                reactionHtml = '<div class="comment-reactions' + roClass + (totalReactions > 0 ? ' has-reactions' : '') + '" data-comment="' + c.id + '">' +
                    triggerHtml + reactionStatsHtml + reactionPickerHtml + '</div>';
            }

            var pinBadgeHtml = isPinnedFlag ? '<span class="pin-badge"><i class="fas fa-thumbtack"></i> 置顶</span>' : '';
            var pinButtonHtml = canPin
                ? '<button class="btn-pin' + (isPinnedFlag ? ' pinned' : '') + '" data-comment="' + c.id + '" title="' + (isPinnedFlag ? '取消置顶' : '置顶') + '"><i class="fas fa-thumbtack"></i></button>'
                : '';

            var children = childrenMap[c.id] || [];
            var pinnedChildren = children.filter(function (ch) { return ch.is_pinned === true; });
            var normalChildren = children.filter(function (ch) { return !ch.is_pinned; });

            var childTotal = normalChildren.length;
            var childTotalPages = Math.ceil(childTotal / C.cfg.CHILD_PAGE_SIZE);
            if (!state.childPageMap[c.id]) state.childPageMap[c.id] = 1;
            var childPage = state.childPageMap[c.id];
            if (childPage < 1) childPage = 1;
            if (childPage > childTotalPages && childTotalPages > 0) childPage = childTotalPages;
            state.childPageMap[c.id] = childPage;

            var childStart = (childPage - 1) * C.cfg.CHILD_PAGE_SIZE;
            var childEnd = Math.min(childStart + C.cfg.CHILD_PAGE_SIZE, normalChildren.length);
            var pageNormalChildren = normalChildren.slice(childStart, childEnd);

            var childrenHtml = '';
            if (children.length > 0) {
                var childHtml = '';
                pinnedChildren.forEach(function (child) { childHtml += renderChildComment(child); });
                pageNormalChildren.forEach(function (child) { childHtml += renderChildComment(child); });
                if (childTotalPages > 1) {
                    childHtml += '<div class="children-pagination" data-parent="' + c.id + '">' +
                        C.pagination.generateHtml(childPage, childTotalPages) + '</div>';
                }
                var isExpanded = state.expandedThreads[c.id] === true;
                var visibleClass = isExpanded ? 'visible' : '';
                var arrowClass = isExpanded ? 'open' : '';
                var arrowSymbol = isExpanded ? '▲' : '▼';
                var btnText = isExpanded ? '收起会话' : '查看会话 (' + children.length + ')';
                childrenHtml = '<button class="btn-view-thread" data-parent="' + c.id + '">' +
                    '<span class="arrow ' + arrowClass + '">' + arrowSymbol + '</span> ' + btnText +
                    '</button>' +
                    '<div class="comment-children ' + visibleClass + '" data-parent="' + c.id + '">' +
                    childHtml + '</div>';
            }

            return '<div class="comment-top' + (isPinnedFlag ? ' is-pinned' : '') + '" id="comment-' + c.id + '" data-id="' + c.id + '">' +
                '<div class="comment-main">' +
                '<div class="comment-floor' + (isSpecial ? ' special' : '') + '">' + floorLabel + '</div>' +
                '<div class="comment-avatar"><a href="' + profileUrl + '" target="_blank">' +
                '<img src="' + esc(avatar) + '" alt="' + esc(nickname) + '" loading="lazy" /></a></div>' +
                '<div class="comment-body">' +
                '<div class="comment-meta">' +
                '<a href="' + profileUrl + '" target="_blank"><span class="comment-author">' + esc(nickname) + '</span></a>' +
                titleHtml +
                '<span class="comment-time">' + esc(time) + '</span>' +
                ipRegionHtml +
                pinBadgeHtml +
                '</div>' +
                // ★ 用 contentHtml（已含表情图片的安全 HTML）
                '<div class="comment-content">' + contentHtml + '</div>' +
                '</div>' +
                '<div class="comment-actions">' +
                '<button class="btn-reply" data-id="' + c.id + '" data-nickname="' + esc(nickname) + '">回复</button>' +
                (canReport ? '<button class="btn-report" data-id="' + c.id + '" title="举报"><i class="fas fa-flag"></i></button>' : '') +
                (canDelete ? '<button class="btn-delete" data-id="' + c.id + '" title="删除"><i class="fas fa-trash"></i></button>' : '') +
                pinButtonHtml +
                '</div>' + reactionHtml + '</div>' +
                (children.length > 0 ? childrenHtml : '') +
                '</div>';
        }

        // ---------- 移动端 ----------
        var pinBadgeMobile = isPinnedFlag ? '<span class="pin-badge"><i class="fas fa-thumbtack"></i> 置顶</span>' : '';
        var actionsHtml =
            '<button class="btn-reply-mobile" data-id="' + c.id + '" data-nickname="' + esc(nickname) + '"><i class="fas fa-reply"></i></button>' +
            '<button class="btn-reaction-mobile" data-id="' + c.id + '"><i class="fas fa-smile"></i></button>' +
            '<button class="btn-more-mobile" data-id="' + c.id + '">⋯</button>';

        var children2 = childrenMap[c.id] || [];
        var threadBtnMobile = children2.length > 0
            ? '<button class="btn-view-thread-mobile" data-id="' + c.id + '">查看会话 (' + children2.length + ')</button>'
            : '';

        return '<div class="comment-top-mobile' + (isPinnedFlag ? ' is-pinned-mobile' : '') + '" id="comment-' + c.id + '" data-id="' + c.id + '">' +
            '<div class="comment-main-mobile">' +
            '<div class="comment-avatar-mobile"><a href="' + profileUrl + '" target="_blank">' +
            '<img src="' + esc(avatar) + '" alt="' + esc(nickname) + '" loading="lazy" /></a>' + titleHtml + '</div>' +
            '<div class="comment-body-mobile">' +
            '<div class="comment-meta-mobile"><a href="' + profileUrl + '" target="_blank">' +
            '<span class="comment-author-mobile">' + esc(nickname) + '</span></a>' + pinBadgeMobile + '</div>' +
            // ★ 用 contentHtml
            '<div class="comment-content-mobile">' + contentHtml + '</div>' +
            '<div class="comment-footer-mobile">' +
            '<span class="comment-time-mobile">' + esc(time) + '</span>' +
            ipRegionHtml.replace('comment-ip', 'comment-ip-mobile') +
            '<div class="comment-actions-mobile">' + actionsHtml + '</div>' +
            '</div></div></div>' +
            threadBtnMobile +
            '</div>';
    }

    // ============================================================
    // 子评论（桌面）
    // ============================================================
    function renderChildComment(child) {
        var avatar = child.avatar || '/images/avatar/default.jpg';
        var nickname = child.nickname || '匿名用户';
        var time = child.created_at || '';
        var content = child.content || '';
        // ★ 优先用后端渲染好的 HTML
        var contentHtml = child.content_html || esc(content);

        var profileUrl = '/profile/' + child.user_id;
        var canDelete = child.can_delete === true;
        var canReport = state.IS_LOGGED_IN && child.user_id !== state.CURRENT_USER_ID;
        var replyToNickname = child.reply_to_nickname || '';
        var isPinned = child.is_pinned === true;
        var isOwnComment = child.user_id === state.CURRENT_USER_ID;

        // ★ 子评论的 IP 属地
        var childIpHtml = (child.ip_region && child.ip_region !== '未知')
            ? '<span class="comment-ip">' + esc(child.ip_region) + '</span>'
            : '';

        var titleHtml = child.title
            ? '<span class="user-title-badge" style="background-color:' + child.title.color + ';color:#fff;">' + esc(child.title.text) + '</span>'
            : '';

        var childReactions = child.reactions || {};
        var childUserReaction = child.user_reaction || null;

        var childStatsHtml = '';
        var childTriggerHtml = '';
        var childPickerHtml = '';

        if (!isOwnComment) {
            state.REACTION_TYPES.forEach(function (rt) {
                var count = childReactions[rt.key] || 0;
                var isActive = childUserReaction === rt.key;
                if (count > 0 || isActive) {
                    childStatsHtml += '<button class="reaction-stat' + (isActive ? ' active' : '') + '" data-reaction="' + rt.key + '" title="' + rt.label + '">' +
                        '<span class="reaction-emoji">' + rt.emoji + '</span>' +
                        '<span class="reaction-count-num">' + count + '</span></button>';
                }
            });
            if (!childUserReaction) {
                childTriggerHtml = '<button class="reaction-trigger" title="表态"><i class="fas fa-smile"></i></button>';
            }
            childPickerHtml = '<div class="reaction-picker">' +
                state.REACTION_TYPES.map(function (rt) {
                    return '<button class="reaction-option' + (rt.key === childUserReaction ? ' active' : '') + '" data-reaction="' + rt.key + '">' +
                        '<span class="reaction-emoji">' + rt.emoji + '</span>' +
                        '<span class="reaction-label">' + rt.label + '</span></button>';
                }).join('') + '</div>';
        } else {
            state.REACTION_TYPES.forEach(function (rt) {
                var count = childReactions[rt.key] || 0;
                if (count > 0) {
                    childStatsHtml += '<span class="reaction-stat readonly" title="' + rt.label + '">' +
                        '<span class="reaction-emoji">' + rt.emoji + '</span>' +
                        '<span class="reaction-count-num">' + count + '</span></span>';
                }
            });
        }

        var childReactionHtml = '';
        if (childStatsHtml || childTriggerHtml) {
            var roClass = isOwnComment ? ' readonly' : '';
            childReactionHtml = '<div class="comment-reactions' + roClass + '" data-comment="' + child.id + '">' +
                childTriggerHtml + childStatsHtml + childPickerHtml + '</div>';
        }

        var childPinBadge = isPinned ? '<span class="pin-badge"><i class="fas fa-thumbtack"></i> 置顶</span>' : '';

        return '<div class="comment-child' + (isPinned ? ' is-pinned' : '') + '" id="comment-' + child.id + '" data-id="' + child.id + '">' +
            '<div class="comment-avatar"><a href="' + profileUrl + '" target="_blank">' +
            '<img src="' + esc(avatar) + '" alt="' + esc(nickname) + '" loading="lazy" /></a></div>' +
            '<div class="comment-body">' +
            '<div class="comment-meta"><a href="' + profileUrl + '" target="_blank">' +
            '<span class="comment-author">' + esc(nickname) + '</span></a>' + titleHtml +
            '<span class="comment-time">' + esc(time) + '</span>' +
            childIpHtml +
            childPinBadge + '</div>' +
            (replyToNickname ? '<div class="comment-reply-to">回复 <span class="at">@</span>' + esc(replyToNickname) + '</div>' : '') +
            // ★ 用 contentHtml
            '<div class="comment-content">' + contentHtml + '</div>' +
            '</div>' +
            '<div class="comment-actions">' +
            '<button class="btn-reply" data-id="' + child.id + '" data-nickname="' + esc(nickname) + '">回复</button>' +
            (canReport ? '<button class="btn-report" data-id="' + child.id + '" title="举报"><i class="fas fa-flag"></i></button>' : '') +
            (canDelete ? '<button class="btn-delete" data-id="' + child.id + '" title="删除"><i class="fas fa-trash"></i></button>' : '') +
            '</div>' + childReactionHtml + '</div>';
    }

    C.render = {
        renderComments: renderComments,
        renderCommentItem: renderCommentItem,
        renderChildComment: renderChildComment
    };
})();