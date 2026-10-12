// static/js/pages/profile/likes.js
(function() {
    'use strict';

    function renderGrid(containerId, items, emptyMessage) {
        var container = document.getElementById(containerId);
        if (!container) return;

        if (!items || items.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-heart" style="color: var(--role-color); opacity:0.3;"></i>
                    <p>${emptyMessage || '还没有赞过的资源'}</p>
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

    function loadLikes() {
        if (typeof likesData === 'undefined') {
            console.warn('likesData 未定义，请确保后端已传递数据');
            return;
        }

        var groups = likesData;
        var allItems = [];
        Object.keys(groups).forEach(function(key) {
            allItems = allItems.concat(groups[key]);
        });

        var emptyMessage = document.querySelector('#likes-list .empty-state p') ?
            document.querySelector('#likes-list .empty-state p').textContent :
            '还没有赞过的资源';

        renderGrid('likes-list', allItems, emptyMessage);
        document.getElementById('likes-count').textContent = allItems.length;
    }

    // 暴露给 profile_tabs.js 调用
    window.loadLikes = loadLikes;

    // 如果页面加载时“赞过”选项卡已激活，自动加载
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            var likesTab = document.getElementById('tab-likes');
            if (likesTab && likesTab.classList.contains('active')) {
                loadLikes();
            }
        });
    } else {
        var likesTab = document.getElementById('tab-likes');
        if (likesTab && likesTab.classList.contains('active')) {
            loadLikes();
        }
    }
})();