(function() {
    'use strict';

    // ---------- 筛选相关 ----------
    window.applyFilters = function() {
        const params = new URLSearchParams(window.location.search);
        const keepParams = ['page', 'q', 'sort'];
        const allKeys = Array.from(params.keys());
        for (const key of allKeys) {
            if (!keepParams.includes(key)) {
                params.delete(key);
            }
        }
        const allChecks = document.querySelectorAll('input[type="checkbox"]:checked');
        const groups = {};
        allChecks.forEach(function(cb) {
            const name = cb.name;
            if (!groups[name]) groups[name] = [];
            groups[name].push(cb.value);
        });
        for (const [key, values] of Object.entries(groups)) {
            for (const val of values) {
                params.append(key, val);
            }
        }
        window.location.href = window.location.pathname + '?' + params.toString();
    };

    window.resetFilters = function() {
        const params = new URLSearchParams(window.location.search);
        const keepParams = ['page', 'q', 'sort'];
        const allKeys = Array.from(params.keys());
        for (const key of allKeys) {
            if (!keepParams.includes(key)) {
                params.delete(key);
            }
        }
        window.location.href = window.location.pathname + '?' + params.toString();
    };

    // ---------- 智能分页 ----------
    function buildPaginationHTML(current, total, baseUrl) {
        if (total <= 1) return '';

        // 构建基础 URL 对象，不含 page 参数
        const base = new URL(baseUrl, window.location.origin);

        let html = '';
        // 上一页
        const prevDisabled = current <= 1;
        if (!prevDisabled) {
            const prevUrl = new URL(base);
            prevUrl.searchParams.set('page', current - 1);
            html += `<a class="page-btn" href="${prevUrl.toString()}">‹</a>`;
        } else {
            html += `<a class="page-btn disabled" href="#">‹</a>`;
        }

        // 页码列表
        let pages = [];
        if (total <= 5) {
            for (let i = 1; i <= total; i++) pages.push(i);
        } else {
            const around = 1;
            let start = Math.max(2, current - around);
            let end = Math.min(total - 1, current + around);
            if (current - around > 2) {
                pages.push(1);
                pages.push('...');
            } else {
                pages.push(1);
            }
            for (let i = start; i <= end; i++) pages.push(i);
            if (current + around < total - 1) {
                pages.push('...');
                pages.push(total);
            } else {
                if (pages[pages.length - 1] !== total) pages.push(total);
            }
        }

        pages.forEach(function(p) {
            if (p === '...') {
                html += `<span class="page-ellipsis">…</span>`;
            } else {
                const pageUrl = new URL(base);
                pageUrl.searchParams.set('page', p);
                const active = p === current ? ' current' : '';
                html += `<a class="page-btn${active}" href="${pageUrl.toString()}">${p}</a>`;
            }
        });

        // 下一页
        const nextDisabled = current >= total;
        if (!nextDisabled) {
            const nextUrl = new URL(base);
            nextUrl.searchParams.set('page', current + 1);
            html += `<a class="page-btn" href="${nextUrl.toString()}">›</a>`;
        } else {
            html += `<a class="page-btn disabled" href="#">›</a>`;
        }

        // 跳转控件
        html += `<span class="page-jump">
            <span class="jump-label">跳至</span>
            <input type="number" class="page-jump-input" min="1" max="${total}" value="${current}" />
            <button class="page-jump-btn">跳转</button>
        </span>`;

        return html;
    }

    function getBaseUrl() {
        // 返回当前 URL 但不包含 page 参数的完整字符串
        const url = new URL(window.location.href);
        url.searchParams.delete('page');
        return url.toString();
    }

    function initPagination() {
        const containers = document.querySelectorAll('.pagination[data-total]');
        containers.forEach(function(container) {
            const total = parseInt(container.dataset.total);
            const current = parseInt(container.dataset.current);
            if (!total || total <= 1) {
                container.style.display = 'none';
                return;
            }
            const baseUrl = getBaseUrl();
            const html = buildPaginationHTML(current, total, baseUrl);
            container.innerHTML = html;
            container.style.display = 'flex';

            // 为跳转按钮绑定事件（事件委托）
            container.addEventListener('click', function(e) {
                const target = e.target.closest('.page-jump-btn');
                if (!target) return;
                const input = target.parentElement.querySelector('.page-jump-input');
                if (!input) return;
                let page = parseInt(input.value);
                if (isNaN(page) || page < 1) page = 1;
                if (page > total) page = total;
                const url = new URL(window.location.href);
                url.searchParams.set('page', page);
                window.location.href = url.toString();
            });
        });
    }

    // ---------- 初始化 ----------
    document.addEventListener('DOMContentLoaded', function() {
        initPagination();
        console.log('✅ 列表页公共脚本已加载（智能分页）');
    });

    window.initPagination = initPagination;
})();

// ---------- 筛选按钮绑定（替代内联 onclick） ----------
(function () {
  var a = document.getElementById("applyFilterBtn");
  if (a) a.addEventListener("click", window.applyFilters);
  var r = document.getElementById("resetFilterBtn");
  if (r) r.addEventListener("click", window.resetFilters);
})();
