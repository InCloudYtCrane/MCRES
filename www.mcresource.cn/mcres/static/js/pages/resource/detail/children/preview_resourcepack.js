// mcres/static/js/pages/resource/detail/children/preview_resourcepack.js
(function() {
    // ============ 元素引用 ============
    var resourceId = (window.PREVIEW_RESOURCEPACK || {}).resourceId;
    var container = document.getElementById('categoriesContainer');
    var searchInput = document.getElementById('searchInput');
    var searchStats = document.getElementById('searchStats');
    var clearBtn = document.getElementById('clearSearchBtn');
    var modeToggle = document.getElementById('modeToggle');
    var loadMoreIndicator = document.getElementById('loadMoreIndicator');
    var noMoreIndicator = document.getElementById('noMoreIndicator');

    // ============ 状态 ============
    var currentMode = (window.PREVIEW_RESOURCEPACK || {}).mode || 'first';
    var currentSearch = '';
    var pageSize = 50;
    var offset = 0;
    var totalItems = (window.PREVIEW_RESOURCEPACK || {}).totalItems;
    var hasMore = true;
    var isLoading = false;
    var searchTimer = null;
    // 有序分类列表 [{name, items:[...]}]
    var allCategories = [];

    // ============ 工具 ============
    function escapeHtml(str) {
        return String(str == null ? '' : str)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function getVanillaUrl(registry) {
        if (!registry) return '';
        var hash = SparkMD5.hash(registry).slice(0, 16);
        return 'https://img.mcresource.cn/resource/rppw/0/' + hash + '.png';
    }

    // ============ 从 SSR 首屏 DOM 恢复状态 ============
    function readStateFromDom() {
        allCategories = [];
        container.querySelectorAll('.category-section').forEach(function(section) {
            var name = section.dataset.category;
            var items = [];
            section.querySelectorAll('.item-list-card').forEach(function(card) {
                var img = card.querySelector('.item-icon img');
                var nameEl = card.querySelector('.item-name');
                items.push({
                    registry: card.dataset.registry || '',
                    name: nameEl ? nameEl.textContent : '',
                    texture_url: img ? (img.getAttribute('src') || '') : ''
                });
            });
            if (items.length) allCategories.push({ name: name, items: items });
        });
        offset = 0;
        allCategories.forEach(function(c) { offset += c.items.length; });
        hasMore = offset < totalItems;
    }

    // ============ 合并分页数据 ============
    // 若同名分类已存在则追加；否则按到达顺序新增
    function mergeCategories(newCats) {
        (newCats || []).forEach(function(cat) {
            var existing = null;
            for (var i = 0; i < allCategories.length; i++) {
                if (allCategories[i].name === cat.name) { existing = allCategories[i]; break; }
            }
            if (existing) {
                existing.items = existing.items.concat(cat.items || []);
            } else {
                allCategories.push({ name: cat.name, items: (cat.items || []).slice() });
            }
        });
    }

    // ============ HTML 构建 ============
    function buildItemsHtml(items, catName) {
        var s = '';
        items.forEach(function(item) {
            var reg = escapeHtml(item.registry);
            var nm = escapeHtml(item.name);
            var url = item.texture_url || '';
            var isImage = url.indexOf('https://img.mcresource.cn/') === 0;
            s += '<div class="item-list-card" data-registry="' + reg +
                 '" data-category="' + escapeHtml(catName) + '">' +
                '<div class="item-icon">' +
                (isImage
                    ? '<img src="' + escapeHtml(url) + '" alt="' + nm + '" loading="lazy" ' +
                      'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';" />'
                    : '') +
                '<div class="placeholder" style="' + (isImage ? 'display:none;' : '') +
                '"><i class="fas fa-image"></i></div>' +
                '<div class="loader"><i class="fas fa-circle-notch"></i></div>' +
                '</div>' +
                '<span class="item-name" title="' + reg + '">' + nm + '</span>' +
                '</div>';
        });
        return s;
    }

    function buildCategoryHtml(cat) {
        var catName = escapeHtml(cat.name);
        // 修复点：对比滑块两个 <img> 都不写 src，onerror 里用 removeAttribute('src')
        return '<div class="category-section" data-category="' + catName + '">' +
            '<div class="category-title">' + catName +
            '<span class="item-count">（' + cat.items.length + ' 个）</span></div>' +
            '<div class="item-list-grid">' + buildItemsHtml(cat.items, cat.name) + '</div>' +
            '<div class="detail-preview-container" data-category="' + catName + '">' +
            '<div class="comparison-slider">' +
            '<div class="comparison-wrapper">' +
            '<img class="vanilla-image" alt="原版" ' +
              'onerror="this.style.background=\'#2b313b\'; this.alt=\'原版不可用\'; ' +
              'this.style.display=\'block\'; this.style.objectFit=\'fill\'; ' +
              'this.removeAttribute(\'src\');" />' +
            '<img class="pack-image" alt="资源包" ' +
              'onerror="this.style.display=\'none\'; this.removeAttribute(\'src\');" />' +
            '<input type="range" class="slider-input" min="0" max="100" value="50" />' +
            '<div class="slider-handle"><div class="handle-arrow"><i class="fas fa-arrows-left-right"></i></div></div>' +
            '<div class="comparison-labels"><span class="label-pack">⚡ 资源包</span>' +
            '<span class="label-vanilla">📦 原版</span></div>' +
            '</div></div>' +
            '<div class="preview-info"><strong class="preview-name"></strong>' +
            '<span class="preview-registry"></span></div>' +
            '</div></div>';
    }

    // ============ 渲染 ============
    function renderAll() {
        if (allCategories.length === 0) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-search"></i> 未找到匹配的物品</div>';
            searchStats.textContent = '共 0 项';
            return;
        }
        var html = '';
        allCategories.forEach(function(cat) { html += buildCategoryHtml(cat); });
        container.innerHTML = html;

        searchStats.textContent = '共 ' + totalItems + ' 项';
        document.querySelectorAll('#modeToggle button').forEach(function(btn) {
            btn.classList.toggle('active', btn.dataset.mode === currentMode);
        });

        bindItemClick();
        bindSliderEvents();
    }

    // ============ 分页请求 ============
    function fetchPage(fromOffset, reset) {
        if (isLoading) return;
        if (!reset && !hasMore) return;

        isLoading = true;
        if (!reset) loadMoreIndicator.style.display = 'block';

        var url = '/preview/resourcepack/' + resourceId
                + '?search=' + encodeURIComponent(currentSearch)
                + '&mode='   + encodeURIComponent(currentMode)
                + '&offset=' + fromOffset
                + '&limit='  + pageSize;

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (reset) allCategories = [];
                mergeCategories(data.categories);
                totalItems = data.total;
                hasMore = !!data.has_more;

                // offset 按本页真实返回条数推进（末尾页可能不足 limit）
                var loadedThisPage = 0;
                (data.categories || []).forEach(function(c) {
                    loadedThisPage += (c.items || []).length;
                });
                offset = data.offset + loadedThisPage;

                renderAll();
                loadMoreIndicator.style.display = 'none';
                noMoreIndicator.style.display = hasMore ? 'none' : 'block';
                isLoading = false;
            })
            .catch(function(err) {
                console.error('加载失败：', err);
                loadMoreIndicator.style.display = 'none';
                isLoading = false;
            });
    }

    // ============ 滚动到底部自动加载 ============
    function onScroll() {
        if (isLoading || !hasMore) return;
        var scrollTop = window.pageYOffset ||
                        document.documentElement.scrollTop ||
                        document.body.scrollTop || 0;
        var windowHeight = window.innerHeight || document.documentElement.clientHeight;
        var docHeight = Math.max(
            document.body.scrollHeight, document.documentElement.scrollHeight,
            document.body.offsetHeight, document.documentElement.offsetHeight
        );
        // 距底部 500px 时开始预加载
        if (scrollTop + windowHeight >= docHeight - 500) {
            fetchPage(offset, false);
        }
    }

    // ============ 滑块对比逻辑 ============
    function updateSlider(previewEl) {
        var slider = previewEl.querySelector('.slider-input');
        var packImg = previewEl.querySelector('.pack-image');
        var handle = previewEl.querySelector('.slider-handle');
        if (!slider || !packImg) return;
        var val = parseInt(slider.value, 10);
        packImg.style.clipPath = 'inset(0 ' + (100 - val) + '% 0 0)';
        if (handle) handle.style.left = val + '%';
    }

    function itemClickHandler(e) {
        var card = e.currentTarget;
        var category = card.dataset.category;
        var previewEl = document.querySelector(
            '.detail-preview-container[data-category="' + category + '"]'
        );
        if (!previewEl || card.classList.contains('loading')) return;

        var registry = card.dataset.registry || '';
        var iconImg = card.querySelector('.item-icon img');
        var packUrl = iconImg ? iconImg.getAttribute('src') : '';
        var vanillaUrl = getVanillaUrl(registry);

        var vanillaImg = previewEl.querySelector('.vanilla-image');
        var packImg = previewEl.querySelector('.pack-image');

        // 修复点：清空旧图用 removeAttribute('src')，绝不用 src=''
        if (vanillaImg) {
            vanillaImg.removeAttribute('src');
            vanillaImg.style.display = 'block';
            vanillaImg.style.background = '#2b313b';
            vanillaImg.alt = '加载中...';
        }
        if (packImg) {
            packImg.removeAttribute('src');
            packImg.style.display = 'block';
            packImg.style.clipPath = 'inset(0 50% 0 0)';
        }

        previewEl.classList.add('show');
        document.querySelectorAll('.item-list-card.active').forEach(function(el) {
            el.classList.remove('active');
        });
        card.classList.add('active');

        var slider = previewEl.querySelector('.slider-input');
        if (slider) { slider.value = 50; updateSlider(previewEl); }

        var nameSpan = card.querySelector('.item-name');
        var previewName = previewEl.querySelector('.preview-name');
        var previewRegistry = previewEl.querySelector('.preview-registry');
        if (previewName) previewName.textContent = nameSpan ? nameSpan.textContent : '';
        if (previewRegistry) previewRegistry.textContent = registry ? ' (' + registry + ')' : '';

        card.classList.add('loading');
        var loadedCount = 0, totalImages = 0;
        function onImageLoad() {
            loadedCount++;
            if (loadedCount >= totalImages) {
                card.classList.remove('loading');
                var s = previewEl.querySelector('.slider-input');
                if (s) updateSlider(previewEl);
            }
        }

        if (packUrl) {
            totalImages++;
            var packLoad = new Image();
            packLoad.onload = function() {
                packImg.src = packLoad.src;
                packImg.style.display = 'block';
                onImageLoad();
            };
            packLoad.onerror = function() {
                if (packImg) packImg.style.display = 'none';
                onImageLoad();
            };
            packLoad.src = packUrl;
        } else if (packImg) {
            packImg.style.display = 'none';
        }

        if (vanillaUrl) {
            totalImages++;
            var vanillaLoad = new Image();
            vanillaLoad.onload = function() {
                vanillaImg.src = vanillaLoad.src;
                vanillaImg.style.background = 'none';
                vanillaImg.alt = '原版';
                vanillaImg.style.display = 'block';
                onImageLoad();
            };
            vanillaLoad.onerror = function() {
                vanillaImg.style.background = '#2b313b';
                vanillaImg.alt = '原版不可用';
                vanillaImg.style.objectFit = 'fill';
                vanillaImg.style.display = 'block';
                onImageLoad();
            };
            vanillaLoad.src = vanillaUrl;
        } else if (vanillaImg) {
            vanillaImg.style.display = 'none';
        }

        if (totalImages === 0) card.classList.remove('loading');
    }

    function bindItemClick() {
        document.querySelectorAll('.item-list-card').forEach(function(card) {
            card.removeEventListener('click', itemClickHandler);
            card.addEventListener('click', itemClickHandler);
        });
    }

    function sliderInputHandler(e) {
        var c = e.target.closest('.detail-preview-container');
        if (c) updateSlider(c);
    }

    function bindSliderEvents() {
        document.querySelectorAll('.detail-preview-container').forEach(function(c) {
            var s = c.querySelector('.slider-input');
            if (s) {
                s.removeEventListener('input', sliderInputHandler);
                s.addEventListener('input', sliderInputHandler);
            }
        });
    }

    // ============ 模式切换 / 搜索 ============
    function modeClickHandler(e) {
        var btn = e.currentTarget;
        var mode = btn.dataset.mode;
        if (mode && mode !== currentMode) {
            currentMode = mode;
            resetAndLoad();
        }
    }

    function bindModeButtons() {
        document.querySelectorAll('#modeToggle button').forEach(function(btn) {
            btn.removeEventListener('click', modeClickHandler);
            btn.addEventListener('click', modeClickHandler);
        });
    }

    function resetAndLoad() {
        allCategories = [];
        offset = 0;
        hasMore = true;
        isLoading = false;
        noMoreIndicator.style.display = 'none';
        container.innerHTML =
            '<div class="empty-state"><i class="fas fa-circle-notch fa-spin"></i> 加载中...</div>';
        fetchPage(0, true);
    }

    function performSearch() {
        currentSearch = searchInput.value.trim();
        resetAndLoad();
    }

    // ============ 初始化 ============
    function init() {
        bindModeButtons();

        // 首屏 SSR 已渲染一批：读取状态，只绑定事件
        if (container.querySelector('.category-section')) {
            readStateFromDom();
            renderAll();
            noMoreIndicator.style.display = hasMore ? 'none' : 'block';
        } else {
            // SSR 无内容（或空数据）：全量从 0 加载
            resetAndLoad();
        }

        window.addEventListener('scroll', onScroll, { passive: true });
    }

    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(performSearch, 300);
    });

    clearBtn.addEventListener('click', function() {
        searchInput.value = '';
        performSearch();
    });

    init();
    console.log('预览页面已加载（分页 + 无限滚动）');
})();
// ---------- 图片加载失败兜底（替代内联 onerror） ----------
(function () {
    'use strict';
    function itemIconFallback(img) {
        img.style.display = 'none';
        if (img.nextElementSibling) img.nextElementSibling.style.display = 'flex';
    }
    function vanillaFallback(img) {
        img.style.background = '#2b313b';
        img.alt = '原版不可用';
        img.style.display = 'block';
        img.style.objectFit = 'fill';
        img.removeAttribute('src');
    }
    function packFallback(img) {
        img.style.display = 'none';
        img.removeAttribute('src');
    }
    function bind(selector, handler) {
        document.querySelectorAll(selector).forEach(function (img) {
            img.addEventListener('error', function () { handler(img); });
            if (img.complete && img.naturalWidth === 0) handler(img);
        });
    }
    document.addEventListener('DOMContentLoaded', function () {
        bind('.item-icon img', itemIconFallback);
        bind('.vanilla-image', vanillaFallback);
        bind('.pack-image', packFallback);
    });
})();

