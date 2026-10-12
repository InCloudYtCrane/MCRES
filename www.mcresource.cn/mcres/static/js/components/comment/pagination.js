// static/js/components/comment/pagination.js
(function () {
    'use strict';

    var C = window.Comments;
    var state = C.state;

    function generateHtml(current, total, baseClass) {
        baseClass = baseClass || 'page-btn';
        if (total <= 1) return '';
        var html = '';
        var prevDisabled = current <= 1;
        html += '<button class="' + baseClass + (prevDisabled ? ' disabled' : '') + '" data-page="prev">‹</button>';

        var pages = [];
        if (total <= 5) {
            for (var i = 1; i <= total; i++) pages.push(i);
        } else {
            var around = 1;
            var start = Math.max(2, current - around);
            var end = Math.min(total - 1, current + around);
            if (current - around > 2) {
                pages.push(1); pages.push('...');
            } else {
                pages.push(1);
            }
            for (var j = start; j <= end; j++) pages.push(j);
            if (current + around < total - 1) {
                pages.push('...'); pages.push(total);
            } else {
                if (pages[pages.length - 1] !== total) pages.push(total);
            }
        }

        pages.forEach(function (p) {
            if (p === '...') {
                html += '<span class="page-ellipsis">…</span>';
            } else {
                var active = p === current ? ' active' : '';
                html += '<button class="' + baseClass + active + '" data-page="' + p + '">' + p + '</button>';
            }
        });

        var nextDisabled = current >= total;
        html += '<button class="' + baseClass + (nextDisabled ? ' disabled' : '') + '" data-page="next">›</button>';
        html += '<span class="page-jump">' +
            '<span style="color:rgba(255,255,255,0.3);font-size:13px;">跳至</span>' +
            '<input type="number" class="page-jump-input" min="1" max="' + total + '" value="' + current + '" />' +
            '<button class="page-jump-btn">跳转</button>' +
            '</span>';
        return html;
    }

    function handleMainClick(e) {
        var target = e.target.closest('.page-btn, .page-jump-btn');
        if (!target) return;
        var container = target.closest('.comments-pagination');
        if (!container) return;

        if (target.classList.contains('page-jump-btn')) {
            var input = container.querySelector('.page-jump-input');
            if (!input) return;
            var page = parseInt(input.value);
            if (isNaN(page) || page < 1) page = 1;
            if (page > state.totalPages) page = state.totalPages;
            C.pagination.goToPage(page);
            return;
        }

        var pageData = target.dataset.page;
        if (!pageData) return;
        if (pageData === 'prev') {
            if (state.currentPage > 1) C.pagination.goToPage(state.currentPage - 1);
        } else if (pageData === 'next') {
            if (state.currentPage < state.totalPages) C.pagination.goToPage(state.currentPage + 1);
        } else {
            var p = parseInt(pageData);
            if (!isNaN(p) && p !== state.currentPage) C.pagination.goToPage(p);
        }
    }

    function handleChildClick(e) {
        var target = e.target.closest('.page-btn, .page-jump-btn');
        if (!target) return;
        var container = target.closest('.children-pagination');
        if (!container) return;
        var parentId = container.dataset.parent;
        if (!parentId) return;

        if (target.classList.contains('page-jump-btn')) {
            var input = container.querySelector('.page-jump-input');
            if (!input) return;
            var page = parseInt(input.value);
            if (isNaN(page) || page < 1) page = 1;
            var total = parseInt(input.max) || 1;
            if (page > total) page = total;
            state.childPageMap[parentId] = page;
            C.render.renderComments();
            return;
        }

        var pageData = target.dataset.page;
        if (!pageData) return;
        var currentChildPage = state.childPageMap[parentId] || 1;
        var newPage = currentChildPage;
        if (pageData === 'prev') {
            if (currentChildPage > 1) newPage = currentChildPage - 1;
        } else if (pageData === 'next') {
            var inMax = container.querySelector('.page-jump-input');
            var t = inMax ? (parseInt(inMax.max) || 1) : 1;
            if (currentChildPage < t) newPage = currentChildPage + 1;
        } else {
            var p = parseInt(pageData);
            if (!isNaN(p)) newPage = p;
        }
        if (newPage !== currentChildPage) {
            state.childPageMap[parentId] = newPage;
            C.render.renderComments();
        }
    }

    function bindEvents() {
        [state.dom.paginationTop, state.dom.paginationBottom].forEach(function (c) {
            if (!c) return;
            c.removeEventListener('click', handleMainClick);
            c.addEventListener('click', handleMainClick);
        });
        if (state.dom.listEl) {
            state.dom.listEl.removeEventListener('click', handleChildClick);
            state.dom.listEl.addEventListener('click', handleChildClick);
        }
    }

    function goToPage(page) {
        if (page < 1) page = 1;
        if (page > state.totalPages) page = state.totalPages;
        if (page === state.currentPage) return;
        state.currentPage = page;
        C.data.loadComments(page, { preserveScroll: false });
        var section = document.querySelector('.comments-section');
        if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    C.pagination = {
        generateHtml: generateHtml,
        bindEvents: bindEvents,
        goToPage: goToPage
    };
})();