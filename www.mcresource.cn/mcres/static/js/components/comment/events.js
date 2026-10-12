// static/js/components/comment/events.js
(function () {
    'use strict';

    var C = window.Comments;
    var state = C.state;

    function bindCommentEvents() {
        var container = state.dom.listEl;
        if (!container) return;

        // ----- 桌面端 -----
        container.querySelectorAll('.btn-reply').forEach(function (btn) {
            btn.removeEventListener('click', handleReply);
            btn.addEventListener('click', handleReply);
        });
        function handleReply(e) {
            e.stopPropagation();
            C.actions.openInlineReply(this.dataset.id, this.dataset.nickname);
        }

        container.querySelectorAll('.btn-delete').forEach(function (btn) {
            btn.removeEventListener('click', handleDelete);
            btn.addEventListener('click', handleDelete);
        });
        function handleDelete(e) {
            e.stopPropagation();
            C.actions.deleteComment(this.dataset.id);
        }

        container.querySelectorAll('.btn-report').forEach(function (btn) {
            btn.removeEventListener('click', handleReport);
            btn.addEventListener('click', handleReport);
        });
        function handleReport(e) {
            e.stopPropagation();
            C.actions.openReportModal(this.dataset.id);
        }

        container.querySelectorAll('.btn-view-thread').forEach(function (btn) {
            btn.removeEventListener('click', handleViewThread);
            btn.addEventListener('click', handleViewThread);
        });
        function handleViewThread(e) {
            e.stopPropagation();
            var parentId = this.dataset.parent;
            var containerEl = state.dom.listEl.querySelector('.comment-children[data-parent="' + parentId + '"]');
            var arrow = this.querySelector('.arrow');
            if (containerEl) {
                var isVisible = containerEl.classList.toggle('visible');
                if (isVisible) state.expandedThreads[parentId] = true;
                else delete state.expandedThreads[parentId];
                if (arrow) arrow.classList.toggle('open', isVisible);
                var count = containerEl.querySelectorAll('.comment-child').length;
                this.innerHTML = '';
                var newArrow = document.createElement('span');
                newArrow.className = 'arrow' + (isVisible ? ' open' : '');
                newArrow.textContent = isVisible ? '▲' : '▼';
                this.appendChild(newArrow);
                this.appendChild(document.createTextNode(' ' + (isVisible ? '收起会话' : '查看会话 (' + count + ')')));
            }
        }

        container.querySelectorAll('.comment-reactions:not(.readonly) .reaction-trigger').forEach(function (btn) {
            btn.removeEventListener('click', handleReactionTrigger);
            btn.addEventListener('click', handleReactionTrigger);
        });
        function handleReactionTrigger(e) {
            e.stopPropagation();
            var picker = this.parentElement.querySelector('.reaction-picker');
            if (picker) {
                document.querySelectorAll('.reaction-picker.active').forEach(function (p) {
                    if (p !== picker) p.classList.remove('active');
                });
                picker.classList.toggle('active');
            }
        }

        container.querySelectorAll('.comment-reactions:not(.readonly) .reaction-option').forEach(function (btn) {
            btn.removeEventListener('click', handleReactionOption);
            btn.addEventListener('click', handleReactionOption);
        });
        function handleReactionOption(e) {
            e.stopPropagation();
            var reaction = this.dataset.reaction;
            var cEl = this.closest('.comment-reactions');
            var commentId = cEl.dataset.comment;
            var picker = this.closest('.reaction-picker');
            var finalReaction = this.classList.contains('active') ? null : reaction;
            C.actions.sendReaction(commentId, finalReaction);
            picker.classList.remove('active');
        }

        container.querySelectorAll('.comment-reactions:not(.readonly) .reaction-stat').forEach(function (btn) {
            btn.removeEventListener('click', handleReactionStat);
            btn.addEventListener('click', handleReactionStat);
        });
        function handleReactionStat(e) {
            e.stopPropagation();
            var reaction = this.dataset.reaction;
            var cEl = this.closest('.comment-reactions');
            var commentId = cEl.dataset.comment;
            var finalReaction = this.classList.contains('active') ? null : reaction;
            C.actions.sendReaction(commentId, finalReaction);
            document.querySelectorAll('.reaction-picker.active').forEach(function (p) { p.classList.remove('active'); });
        }

        container.querySelectorAll('.btn-pin').forEach(function (btn) {
            btn.removeEventListener('click', handlePin);
            btn.addEventListener('click', handlePin);
        });
        function handlePin(e) {
            e.stopPropagation();
            C.actions.pinComment(this.dataset.comment, C.utils.getCurrentPath());
        }

        // ----- 移动端 -----
        if (C.utils.isMobile()) {
            container.querySelectorAll('.btn-reply-mobile').forEach(function (btn) {
                btn.removeEventListener('click', handleReplyMobile);
                btn.addEventListener('click', handleReplyMobile);
            });
            function handleReplyMobile(e) {
                e.stopPropagation();
                C.drawer.openThread(this.dataset.id);
                setTimeout(function () {
                    var input = document.getElementById('threadReplyInput');
                    if (input) { input.value = ''; input.focus(); }
                }, 300);
            }

            container.querySelectorAll('.btn-reaction-mobile').forEach(function (btn) {
                btn.removeEventListener('click', handleReactionMobile);
                btn.addEventListener('click', handleReactionMobile);
            });
            function handleReactionMobile(e) {
                e.stopPropagation();
                if (!state.IS_LOGGED_IN) { alert('请先登录才能表态'); return; }
                var comment = C.utils.findComment(this.dataset.id);
                if (comment && comment.user_id === state.CURRENT_USER_ID) {
                    alert('不能对自己的评论表态');
                    return;
                }
                C.drawer.openReaction(this.dataset.id);
            }

            container.querySelectorAll('.btn-more-mobile').forEach(function (btn) {
                btn.removeEventListener('click', handleMoreMobile);
                btn.addEventListener('click', handleMoreMobile);
            });
            function handleMoreMobile(e) {
                e.stopPropagation();
                C.drawer.openAction(this.dataset.id);
            }

            container.querySelectorAll('.btn-view-thread-mobile').forEach(function (btn) {
                btn.removeEventListener('click', handleViewThreadMobile);
                btn.addEventListener('click', handleViewThreadMobile);
            });
            function handleViewThreadMobile(e) {
                e.stopPropagation();
                C.drawer.openThread(this.dataset.id);
            }
        }
    }

    C.events = {
        bindCommentEvents: bindCommentEvents
    };
})();