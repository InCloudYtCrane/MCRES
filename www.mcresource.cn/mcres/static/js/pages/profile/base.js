(function() {
    'use strict';

    var navBtns = document.querySelectorAll('.sidebar-nav-btn');
    var panels = {
        home: document.getElementById('tab-home'),
        works: document.getElementById('tab-works'),
        likes: document.getElementById('tab-likes'),
        favorites: document.getElementById('tab-favorites'),
        calendar: document.getElementById('tab-calendar'),
        achievements: document.getElementById('tab-achievements'),
        board: document.getElementById('tab-board')
    };

    // 过滤掉不存在的面板
    var validPanels = {};
    Object.keys(panels).forEach(function(key) {
        if (panels[key]) validPanels[key] = panels[key];
    });

    function switchTab(tabId) {
        // 隐藏所有面板
        Object.values(validPanels).forEach(function(el) {
            if (el) el.classList.remove('active');
        });

        // 显示目标面板
        if (validPanels[tabId]) {
            validPanels[tabId].classList.add('active');
        }

        // 更新按钮状态
        navBtns.forEach(function(btn) {
            btn.classList.remove('active');
            if (btn.dataset.tab === tabId) {
                btn.classList.add('active');
            }
        });

        // 触发对应页面的加载函数
        if (tabId === 'works' && typeof window.loadWorks === 'function') {
            window.loadWorks();
        } else if (tabId === 'likes' && typeof window.loadLikes === 'function') {
            window.loadLikes();
        } else if (tabId === 'favorites' && typeof window.loadFavorites === 'function') {
            window.loadFavorites();
        } else if (tabId === 'achievements' && typeof window.loadTasks === 'function') {
            window.loadTasks();
        } else if (tabId === 'calendar' && typeof window.initContributionGraph === 'function') {
            setTimeout(window.initContributionGraph, 50);
        }
        // board 无需加载，评论组件自行初始化
    }

    // 绑定点击事件
    navBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            var tab = this.dataset.tab;
            if (tab) {
                switchTab(tab);
                // 更新 URL 参数（保留其他参数）
                var url = new URL(window.location);
                url.searchParams.set('tab', tab);
                url.hash = ''; // 移除锚点
                window.history.replaceState({}, '', url);
            }
        });
    });

    // 暴露切换函数
    window.switchProfileTab = switchTab;

    // ========== 页面加载时根据 URL 参数/锚点自动跳转 ==========
    function initTabFromUrl() {
        var hash = window.location.hash;
        // 1. 优先处理 #comment=xxx
        if (hash && hash.startsWith('#comment-')) {
            if (validPanels['board']) {
                switchTab('board');
                // 可选：滚动到评论区域，由评论组件自行处理
                return;
            }
        }

        // 2. 处理 ?tab=xxx
        var params = new URLSearchParams(window.location.search);
        var tab = params.get('tab');
        if (tab && validPanels[tab]) {
            switchTab(tab);
            // 确保按钮高亮
            navBtns.forEach(function(btn) {
                btn.classList.toggle('active', btn.dataset.tab === tab);
            });
        }
        // 否则保持默认（首页）
    }

    // 页面加载完成后执行，若 DOM 已就绪则立即执行
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTabFromUrl);
    } else {
        initTabFromUrl();
    }
})();