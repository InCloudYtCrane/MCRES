// mcres/static/js/components/search-suggest.js
(function() {
    'use strict';

    function highlightText(text, keyword) {
        if (!text || !keyword) return text;
        const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp('(' + escaped + ')', 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function initSearchSuggest(selector) {
        let input;
        if (typeof selector === 'string') {
            input = document.querySelector(selector);
        } else if (selector && selector.nodeType === 1) {
            input = selector;
        } else {
            console.warn('[搜索补全] 无效参数:', selector);
            return;
        }

        if (!input) {
            console.warn('[搜索补全] 未找到输入框');
            return;
        }

        if (input.dataset.suggestInitialized === 'true') return;
        input.dataset.suggestInitialized = 'true';

        const wrapper = document.createElement('div');
        wrapper.className = 'search-suggest-wrapper';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const dropdown = document.createElement('div');
        dropdown.className = 'suggest-dropdown';
        wrapper.appendChild(dropdown);

        let currentFocus = -1;

        function renderItems(list, isHistory = false) {
            dropdown.innerHTML = '';
            if (!list || list.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'suggest-empty';
                empty.textContent = isHistory ? '暂无搜索历史' : '无匹配结果';
                dropdown.appendChild(empty);
                dropdown.style.display = 'block';
                return;
            }

            if (isHistory) {
                const header = document.createElement('div');
                header.className = 'suggest-history-header';
                const title = document.createElement('span');
                title.textContent = '搜索历史';
                const clearBtn = document.createElement('span');
                clearBtn.className = 'clear-history';
                clearBtn.textContent = '清空';
                clearBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    fetch('/clear_search_history', { method: 'POST' })
                        .then(() => {
                            hideDropdown();
                            fetchSuggestions('');
                        })
                        .catch(() => {});
                });
                header.appendChild(title);
                header.appendChild(clearBtn);
                dropdown.appendChild(header);
            }

            const currentKeyword = input.value.trim();

            list.forEach((item, index) => {
                const div = document.createElement('div');
                div.className = 'suggest-item';

                // --- 统一处理：无论历史还是补全，item 都是对象 { label: "xxx" } ---
                const displayText = item.label;
                // 历史项不高亮，补全项高亮
                const highlighted = isHistory ? escapeHtml(displayText) : highlightText(escapeHtml(displayText), currentKeyword);
                div.innerHTML = `<span class="label">${highlighted}</span>`;

                div.addEventListener('click', function() {
                    const value = item.label;
                    input.value = value;
                    const form = input.closest('form');
                    if (form) {
                        const newWindow = input.dataset.suggestNewWindow === 'true';
                        if (newWindow) {
                            const originalTarget = form.target;
                            form.target = '_blank';
                            form.submit();
                            form.target = originalTarget;
                        } else {
                            form.submit();
                        }
                    } else {
                        window.location.href = `/search?q=${encodeURIComponent(value)}`;
                    }
                    hideDropdown();
                });

                div.dataset.index = index;
                dropdown.appendChild(div);
            });

            dropdown.style.display = 'block';
            currentFocus = -1;
        }

        function hideDropdown() {
            dropdown.style.display = 'none';
            currentFocus = -1;
        }

        function fetchSuggestions(q) {
            fetch(`/suggest?q=${encodeURIComponent(q)}`)
                .then(res => res.json())
                .then(data => {
                    if (data && data.length > 0) {
                        const isHistory = q === '';
                        renderItems(data, isHistory);
                    } else {
                        hideDropdown();
                    }
                })
                .catch(function(err) {
                    console.warn('[搜索补全] 请求失败:', err);
                    hideDropdown();
                });
        }

        let timer = null;
        let isFocused = false;

        input.addEventListener('focus', function() {
            isFocused = true;
            const val = this.value.trim();
            fetchSuggestions(val);
        });

        input.addEventListener('blur', function() {
            isFocused = false;
            setTimeout(() => {
                if (!dropdown.contains(document.activeElement)) {
                    hideDropdown();
                }
            }, 150);
        });

        input.addEventListener('input', function() {
            const val = this.value.trim();
            clearTimeout(timer);
            timer = setTimeout(() => {
                fetchSuggestions(val);
            }, 200);
        });

        input.addEventListener('keydown', function(e) {
            const items = dropdown.querySelectorAll('.suggest-item');
            if (items.length === 0) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                currentFocus = (currentFocus + 1) % items.length;
                highlightItem(items);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                currentFocus = (currentFocus - 1 + items.length) % items.length;
                highlightItem(items);
            } else if (e.key === 'Enter') {
                if (currentFocus >= 0 && currentFocus < items.length) {
                    items[currentFocus].click();
                }
                hideDropdown();
            } else if (e.key === 'Escape') {
                hideDropdown();
                input.blur();
            }
        });

        function highlightItem(items) {
            items.forEach((el, idx) => {
                el.style.background = idx === currentFocus ? 'rgba(255,255,255,0.08)' : '';
            });
            if (currentFocus >= 0 && currentFocus < items.length) {
                items[currentFocus].scrollIntoView({ block: 'nearest' });
            }
        }

        document.addEventListener('click', function(e) {
            if (!wrapper.contains(e.target)) {
                hideDropdown();
            }
        });

        function adjustDropdownPosition() {
            const rect = wrapper.getBoundingClientRect();
            const spaceBottom = window.innerHeight - rect.bottom;
            if (spaceBottom < 200) {
                dropdown.style.top = 'auto';
                dropdown.style.bottom = 'calc(100% + 4px)';
            } else {
                dropdown.style.top = 'calc(100% + 4px)';
                dropdown.style.bottom = 'auto';
            }
        }
        window.addEventListener('resize', adjustDropdownPosition);
        window.addEventListener('scroll', adjustDropdownPosition, true);
        input.addEventListener('focus', adjustDropdownPosition);
    }

    window.initSearchSuggest = initSearchSuggest;

    function autoInit() {
        document.querySelectorAll('input[data-search-suggest]').forEach(function(el) {
            if (!el.dataset.suggestInitialized) {
                initSearchSuggest(el);
            }
        });
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        autoInit();
    } else {
        document.addEventListener('DOMContentLoaded', autoInit);
    }

})();
