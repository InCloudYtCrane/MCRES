// static/js/components/comment/data.js
(function () {
    'use strict';

    var C = window.Comments;
    var state = C.state;

    function loadComments(targetPage, options) {
        options = options || {};
        var preserveScroll = options.preserveScroll !== false;
        var onComplete = options.onComplete || null;

        var scrollAnchor = preserveScroll ? C.scroll.captureAnchor() : null;
        var path = C.utils.getCurrentPath();
        state.currentPath = path;

        var cpage = targetPage || 1;
        if (cpage < 1) cpage = 1;

        state.dom.loadingEl.style.display = 'flex';
        state.dom.emptyEl.style.display = 'none';
        state.dom.errorEl.style.display = 'none';
        state.dom.listEl.innerHTML = '';
        state.dom.paginationTop.style.display = 'none';
        state.dom.paginationBottom.style.display = 'none';

        fetch('/comments?path=' + encodeURIComponent(path) + '&cpage=' + cpage)
            .then(function (res) {
                if (!res.ok) {
                    return res.json().then(function (err) {
                        throw new Error(err.message || 'HTTP ' + res.status);
                    }).catch(function () {
                        throw new Error('HTTP ' + res.status);
                    });
                }
                return res.json();
            })
            .then(function (data) {
                state.dom.loadingEl.style.display = 'none';
                if (data.success && Array.isArray(data.data)) {
                    // ★ 归一化 id 类型，避免 dataset 字符串与 JSON 数字不等
                    data.data.forEach(function (c) {
                        c.id = Number(c.id);
                        if (c.parent_id != null) c.parent_id = Number(c.parent_id);
                        if (c.user_id != null) c.user_id = Number(c.user_id);
                        if (c.reply_to_id != null) c.reply_to_id = Number(c.reply_to_id);
                    });
                    state.comments = data.data;
                    var pg = data.pagination || {};
                    state.currentPage = pg.page || 1;
                    state.totalPages = pg.total_pages || 1;
                    state.totalNormalTop = pg.total || 0;
                    state.totalCount = data.total_count || data.data.length;
                    state.childPageMap = {};
                    C.render.renderComments();
                } else {
                    state.comments = [];
                    state.currentPage = 1;
                    state.totalPages = 1;
                    state.totalNormalTop = 0;
                    state.totalCount = 0;
                    C.render.renderComments();
                }
                if (scrollAnchor) C.scroll.restoreAnchor(scrollAnchor);
                if (typeof onComplete === 'function') onComplete();
            })
            .catch(function (err) {
                state.dom.loadingEl.style.display = 'none';
                state.dom.errorEl.style.display = 'block';
                console.error('加载评论失败:', err);
                if (scrollAnchor) C.scroll.restoreAnchor(scrollAnchor);
                if (typeof onComplete === 'function') onComplete();
            });
    }

    function postJSON(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
        .then(function (res) {
            var ct = res.headers.get('content-type') || '';
            if (ct.includes('text/html')) {
                return res.text().then(function (html) {
                    document.open();
                    document.write(html);
                    document.close();
                    throw new Error('HTML_REDIRECT');
                });
            }
            if (!res.ok) {
                return res.json().then(function (err) {
                    throw new Error(err.message || 'HTTP ' + res.status);
                }).catch(function () {
                    throw new Error('HTTP ' + res.status);
                });
            }
            return res.json();
        });
    }

    function deleteRequest(url) {
        return fetch(url, { method: 'DELETE' })
            .then(function (res) {
                if (!res.ok) {
                    return res.json().then(function (err) {
                        throw new Error(err.message || 'HTTP ' + res.status);
                    }).catch(function () {
                        throw new Error('HTTP ' + res.status);
                    });
                }
                return res.json();
            });
    }

    C.data = {
        loadComments: loadComments,
        postJSON: postJSON,
        deleteRequest: deleteRequest
    };
})();