// static/js/components/comment/utils.js
(function () {
    'use strict';

    var C = window.Comments;

    C.utils = {
        escapeHtml: function (text) {
            if (!text) return '';
            var div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        isMobile: function () {
            return window.innerWidth < 768;
        },
        getCurrentPath: function () {
            if (window._commentsPath) return window._commentsPath;
            return window.location.pathname;
        },
        findComment: function (id) {
            var numId = Number(id);
            return C.state.comments.find(function (c) { return c.id === numId; });
        },
        findTopCommentId: function (commentId) {
            var listEl = C.state.dom.listEl;
            if (!listEl) return null;
            var topEl = listEl.querySelector('.comment-top[data-id="' + commentId + '"]');
            if (topEl) return Number(commentId);
            var childEl = listEl.querySelector('.comment-child[data-id="' + commentId + '"]');
            if (childEl) {
                var parentTop = childEl.closest('.comment-top');
                if (parentTop && parentTop.dataset.id) return Number(parentTop.dataset.id);
            }
            return null;
        }
    };
})();