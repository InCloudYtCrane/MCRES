// static/js/components/comment/drawer.js
(function () {
    'use strict';

    var C = window.Comments;
    var state = C.state;

    function open(name) {
        var drawer = document.getElementById(name + 'Drawer');
        if (drawer) {
            drawer.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    function close(name) {
        var drawer = document.getElementById(name + 'Drawer');
        if (drawer) {
            drawer.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    function openReaction(commentId) {
        var comment = C.utils.findComment(commentId);
        if (!comment) return;
        var body = document.getElementById('reactionOptions');
        body.innerHTML = '';
        state.REACTION_TYPES.forEach(function (rt) {
            var count = comment.reactions[rt.key] || 0;
            var btn = document.createElement('button');
            btn.className = 'reaction-option';
            btn.dataset.reaction = rt.key;
            btn.innerHTML = rt.emoji + ' <span class="count">' + count + '</span>';
            if (comment.user_reaction === rt.key) btn.classList.add('active');
            btn.addEventListener('click', function () {
                var reaction = this.dataset.reaction;
                var finalReaction = comment.user_reaction === reaction ? null : reaction;
                C.actions.sendReaction(commentId, finalReaction);
            });
            body.appendChild(btn);
        });
        open('reaction');
    }

    function openAction(commentId) {
        var comment = C.utils.findComment(commentId);
        if (!comment) return;
        var body = document.getElementById('actionOptions');
        body.innerHTML = '';

        function item(text, icon, onClick, cls) {
            cls = cls || '';
            var btn = document.createElement('button');
            btn.className = 'action-item ' + cls;
            btn.innerHTML = '<i class="fas ' + icon + '"></i> ' + text;
            btn.addEventListener('click', function (e) { e.stopPropagation(); onClick(); });
            return btn;
        }

        body.appendChild(item('回复', 'fa-reply', function () {
            close('action');
            openThread(commentId);
            setTimeout(function () {
                var input = document.getElementById('threadReplyInput');
                if (input) { input.value = ''; input.focus(); }
            }, 300);
        }));

        if (state.IS_LOGGED_IN && comment.user_id !== state.CURRENT_USER_ID) {
            body.appendChild(item('举报', 'fa-flag', function () {
                close('action');
                openReport(commentId);
            }, 'danger'));
        }

        if (comment.can_delete) {
            body.appendChild(item('删除', 'fa-trash', function () {
                close('action');
                if (confirm('确定要删除该评论吗？')) C.actions.deleteComment(commentId);
            }, 'danger'));
        }

        if (comment.can_pin && !comment.parent_id) {
            body.appendChild(item(comment.is_pinned ? '取消置顶' : '置顶', 'fa-thumbtack', function () {
                close('action');
                C.actions.pinComment(commentId, C.utils.getCurrentPath());
            }));
        }

        open('action');
    }

    function openReport(commentId) {
        state.reportTargetId = Number(commentId);
        var reason = document.getElementById('reportReasonMobile');
        var submitBtn = document.getElementById('reportSubmitBtnMobile');
        if (reason) reason.value = '';
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = '提交举报';

            submitBtn.onclick = function () {
                var text = reason.value.trim();
                if (!text) { alert('请填写举报理由'); return; }
                var targetComment = C.utils.findComment(commentId);
                if (!targetComment) { alert('评论不存在'); return; }
                this.disabled = true;
                this.textContent = '提交中…';
                var self = this;
                C.data.postJSON('/comments/report', {
                    author_id: targetComment.user_id,
                    reason: text,
                    content: targetComment.content
                })
                .then(function (data) {
                    if (data.success) {
                        alert('举报已提交');
                        close('report');
                    } else {
                        alert(data.message || '提交失败');
                    }
                })
                .catch(function (err) {
                    alert('举报失败：' + err.message);
                    console.error(err);
                })
                .finally(function () {
                    self.disabled = false;
                    self.textContent = '提交举报';
                });
            };
        }

        open('report');
    }

    // ---------- 楼中楼抽屉 ----------
    function openThread(parentId) {
        var list = document.getElementById('threadList');
        var title = document.getElementById('threadDrawerTitle');
        var input = document.getElementById('threadReplyInput');
        var sendBtn = document.getElementById('threadReplyBtn');

        list.innerHTML = '<div style="text-align:center;padding:20px;color:rgba(255,255,255,0.3);">加载中...</div>';
        title.textContent = '会话';

        var children = state.comments.filter(function (c) { return c.parent_id === Number(parentId); });
        renderThreadChildren(children, list);

        input.dataset.parentId = parentId;
        input.value = '';
        sendBtn.disabled = true;
        input.focus();

        sendBtn.onclick = function () {
            var content = input.value.trim();
            if (!content) return;
            var replyMatch = content.match(/^@(\S+)\s/);
            var replyTo = replyMatch ? replyMatch[1] : '';
            var cleanContent = replyMatch ? content.replace(/^@\S+\s/, '') : content;
            C.actions.submitChildComment(parentId, replyTo, cleanContent, null);
            input.value = '';
            sendBtn.disabled = true;
        };
        input.addEventListener('input', function () {
            sendBtn.disabled = this.value.trim().length === 0;
        });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!sendBtn.disabled) sendBtn.click();
            }
        });

        open('thread');
    }

    function renderThreadChildren(children, container) {
        container.innerHTML = '';
        if (children.length === 0) {
            container.innerHTML = '<div style="text-align:center;padding:20px;color:rgba(255,255,255,0.3);">暂无回复</div>';
            return;
        }
        children.sort(function (a, b) {
            return (a.created_at || '').localeCompare(b.created_at || '');
        });
        var esc = C.utils.escapeHtml;
        children.forEach(function (child) {
            var div = document.createElement('div');
            div.className = 'thread-comment';
            var avatar = child.avatar || '/images/avatar/default.jpg';
            var nickname = child.nickname || '匿名用户';
            var time = child.created_at || '';
            var content = child.content || '';
            // ★ 优先用后端渲染好的 HTML
            var contentHtml = child.content_html || esc(content);
            var profileUrl = '/profile/' + child.user_id;
            var canDelete = child.can_delete === true;
            var canReport = state.IS_LOGGED_IN && child.user_id !== state.CURRENT_USER_ID;

            div.innerHTML = '<div class="thread-row">' +
                '<div class="thread-avatar"><a href="' + profileUrl + '" target="_blank">' +
                '<img src="' + avatar + '" alt="' + nickname + '" loading="lazy" /></a></div>' +
                '<div class="thread-body">' +
                '<div class="thread-author">' + esc(nickname) + '</div>' +
                // ★ 用 contentHtml
                '<div class="thread-content">' + contentHtml + '</div>' +
                '<div class="thread-meta">' +
                '<span class="thread-time">' + esc(time) + '</span>' +
                '<div class="thread-actions">' +
                '<button class="btn-reply-thread" data-id="' + child.id + '" data-nickname="' + esc(nickname) + '"><i class="fas fa-reply"></i></button>' +
                '<button class="btn-more-thread" data-id="' + child.id + '">⋯</button>' +
                (canReport ? '<button class="btn-report-thread" data-id="' + child.id + '"><i class="fas fa-flag"></i></button>' : '') +
                (canDelete ? '<button class="btn-delete-thread" data-id="' + child.id + '"><i class="fas fa-trash"></i></button>' : '') +
                '</div></div></div></div>';
            container.appendChild(div);
        });

        container.querySelectorAll('.btn-reply-thread').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = this.dataset.id;
                var input = document.getElementById('threadReplyInput');
                input.value = '';
                input.focus();
                var parentComment = C.utils.findComment(id);
                if (parentComment && parentComment.parent_id) {
                    input.dataset.parentId = parentComment.parent_id;
                } else {
                    input.dataset.parentId = id;
                }
            });
        });
        container.querySelectorAll('.btn-more-thread').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = this.dataset.id;
                close('thread');
                openAction(id);
            });
        });
        container.querySelectorAll('.btn-report-thread').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = this.dataset.id;
                close('thread');
                openReport(id);
            });
        });
        container.querySelectorAll('.btn-delete-thread').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = this.dataset.id;
                if (confirm('确定删除此回复？')) {
                    C.actions.deleteComment(id);
                    var input = document.getElementById('threadReplyInput');
                    var parentId = input && input.dataset.parentId;
                    if (parentId) openThread(parentId);
                }
            });
        });
    }

    C.drawer = {
        open: open,
        close: close,
        openReaction: openReaction,
        openAction: openAction,
        openReport: openReport,
        openThread: openThread
    };
})();