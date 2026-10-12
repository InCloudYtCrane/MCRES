// static/js/pages/profile/works.js
(function() {
    'use strict';

    // 渲染网格函数（添加 target="_blank"）
    function renderGrid(containerId, items, emptyMessage) {
        var container = document.getElementById(containerId);
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-folder-open" style="color: var(--role-color); opacity:0.3;"></i>
                    <p>${emptyMessage || '还没有作品'}</p>
                </div>
            `;
            return;
        }

        var html = '';
        items.forEach(function(item) {
            var detailUrl = '/' + item.type + '/' + item.id;
            html += `
                <div class="resource-card">
                    <a href="${detailUrl}" target="_blank" style="text-decoration:none; color:inherit;">
                        <div class="thumb">
                            <img src="${item.cover}" alt="${item.title}" loading="lazy">
                        </div>
                        <div class="info">
                            <div class="title">${item.title}</div>
                            <div class="meta">
                                <span>${item.views || 0} 浏览</span>
                                <span>${item.type === 'resourcepack' ? '资源包' : item.type === 'shaderpack' ? '光影包' : '地图'}</span>
                            </div>
                        </div>
                    </a>
                </div>
            `;
        });
        container.innerHTML = html;
    }

    // 加载作品数据（使用全局变量 worksData）
    function loadWorks() {
        if (typeof worksData === 'undefined') {
            console.warn('worksData 未定义，请确保后端已传递数据');
            return;
        }

        var groups = worksData;
        var total = 0;

        renderGrid('works-list-resourcepack', groups.resourcepack, '还没有发布过资源包，去创作吧！');
        renderGrid('works-list-shaderpack', groups.shaderpack, '还没有发布过光影包，去创作吧！');
        renderGrid('works-list-map', groups.map, '还没有发布过地图，去创作吧！');

        document.getElementById('count-resourcepack').textContent = groups.resourcepack.length;
        document.getElementById('count-shaderpack').textContent = groups.shaderpack.length;
        document.getElementById('count-map').textContent = groups.map.length;
        total = groups.resourcepack.length + groups.shaderpack.length + groups.map.length;
        document.getElementById('works-total').textContent = total;
    }

    // 子菜单切换
    function initSubMenu() {
        var btns = document.querySelectorAll('.works-sub-btn');
        var contents = {
            resourcepack: document.getElementById('works-resourcepack'),
            shaderpack: document.getElementById('works-shaderpack'),
            map: document.getElementById('works-map')
        };

        btns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                var type = this.dataset.type;
                btns.forEach(function(b) { b.classList.remove('active'); });
                this.classList.add('active');
                Object.keys(contents).forEach(function(key) {
                    contents[key].classList.toggle('active', key === type);
                });
            });
        });

        var firstBtn = document.querySelector('.works-sub-btn[data-type="resourcepack"]');
        if (firstBtn) firstBtn.click();
    }

    function init() {
        loadWorks();
        initSubMenu();
    }

    window.loadWorks = loadWorks;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();