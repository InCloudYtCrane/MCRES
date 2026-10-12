// static/js/components/comment/scroll.js
(function () {
    'use strict';

    var C = window.Comments;
    var state = C.state;

    function captureAnchor() {
        var anchor = { scrollY: window.scrollY, anchorId: null, anchorOffset: 0 };
        if (!state.dom.listEl) return anchor;
        var all = state.dom.listEl.querySelectorAll('.comment-top, .comment-child');
        for (var i = 0; i < all.length; i++) {
            var rect = all[i].getBoundingClientRect();
            if (rect.bottom > 0) {
                anchor.anchorId = all[i].id;
                anchor.anchorOffset = rect.top;
                break;
            }
        }
        return anchor;
    }

    function restoreAnchor(anchor) {
        if (!anchor) return;
        requestAnimationFrame(function () {
            if (anchor.anchorId) {
                var el = document.getElementById(anchor.anchorId);
                if (el) {
                    var newTop = el.getBoundingClientRect().top;
                    var delta = newTop - anchor.anchorOffset;
                    window.scrollTo(0, window.scrollY + delta);
                    return;
                }
            }
            window.scrollTo(0, anchor.scrollY);
        });
    }

    function scrollToCommentFromHash() {
        var hash = window.location.hash;
        if (!hash || hash.indexOf('#comment-') !== 0) return;
        var id = hash.replace('#comment-', '');
        if (!id) return;

        if (document.getElementById('comment-' + id)) {
            scrollAndHighlight(id);
            return;
        }

        fetch('/comments/locate?path=' + encodeURIComponent(state.currentPath)
              + '&comment_id=' + encodeURIComponent(id))
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (!data.success) {
                    console.log('[定位] 未找到评论:', data.message || 'unknown');
                    return;
                }
                var targetId = data.target_id;
                var targetPage = data.page || 1;
                if (targetPage !== state.currentPage) {
                    state.currentPage = targetPage;
                    C.data.loadComments(targetPage, {
                        preserveScroll: false,
                        onComplete: function () {
                            setTimeout(function () { scrollAndHighlight(targetId); }, 100);
                        }
                    });
                } else {
                    setTimeout(function () { scrollAndHighlight(targetId); }, 100);
                }
            })
            .catch(function (err) { console.error('[定位] 请求失败:', err); });
    }

    function scrollAndHighlight(id) {
        var el = document.getElementById('comment-' + id);
        if (!el) return;

        if (el.classList.contains('comment-child')) {
            var parentTop = el.closest('.comment-top');
            if (parentTop) {
                var topId = parentTop.dataset.id;
                state.expandedThreads[topId] = true;
                var childrenContainer = parentTop.querySelector('.comment-children');
                if (childrenContainer && !childrenContainer.classList.contains('visible')) {
                    childrenContainer.classList.add('visible');
                    var viewBtn = parentTop.querySelector('.btn-view-thread');
                    if (viewBtn) {
                        var count = childrenContainer.querySelectorAll('.comment-child').length;
                        viewBtn.innerHTML = '';
                        var arrow = document.createElement('span');
                        arrow.className = 'arrow open';
                        arrow.textContent = '▲';
                        viewBtn.appendChild(arrow);
                        viewBtn.appendChild(document.createTextNode(' 收起会话 (' + count + ')'));
                    }
                }
            }
        }

        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('comment-highlight');
        setTimeout(function () { el.classList.remove('comment-highlight'); }, 2500);
    }

    C.scroll = {
        captureAnchor: captureAnchor,
        restoreAnchor: restoreAnchor,
        scrollToCommentFromHash: scrollToCommentFromHash,
        scrollAndHighlight: scrollAndHighlight
    };
})();