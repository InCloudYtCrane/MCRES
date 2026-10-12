(function() {
    'use strict';

    // 1. 海报轮播
    const posterTrack = document.getElementById('posterTrack');
    const posterDots = document.getElementById('posterDots');
    const posterContainer = document.getElementById('posterCarousel');
    if (posterTrack) {
        const slides = posterTrack.querySelectorAll('.carousel-slide');
        const total = slides.length;
        let current = 0;
        let autoTimer = null;
        const interval = 5000;

        // 创建 dots
        if (posterDots && total > 1) {
            posterDots.innerHTML = '';
            for (let i = 0; i < total; i++) {
                const dot = document.createElement('button');
                dot.className = 'dot' + (i === 0 ? ' active' : '');
                dot.dataset.index = i;
                dot.addEventListener('click', function(e) {
                    e.stopPropagation();
                    goTo(parseInt(this.dataset.index));
                });
                posterDots.appendChild(dot);
            }
        }

        function goTo(index) {
            if (index < 0) index = total - 1;
            if (index >= total) index = 0;
            current = index;
            posterTrack.style.transform = 'translateX(-' + (current * 100) + '%)';
            // 更新dots
            if (posterDots) {
                const dots = posterDots.querySelectorAll('.dot');
                dots.forEach((d, i) => d.classList.toggle('active', i === current));
            }
            resetAutoPlay();
        }

        function next() { goTo(current + 1); }
        function prev() { goTo(current - 1); }

        function startAutoPlay() {
            if (autoTimer) clearInterval(autoTimer);
            if (total <= 1) return;
            autoTimer = setInterval(next, interval);
        }
        function stopAutoPlay() { if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } }
        function resetAutoPlay() { stopAutoPlay(); startAutoPlay(); }

        // 事件
        const leftBtn = posterContainer.querySelector('.carousel-arrow.left');
        const rightBtn = posterContainer.querySelector('.carousel-arrow.right');
        if (leftBtn) leftBtn.addEventListener('click', function(e) { e.stopPropagation(); prev(); });
        if (rightBtn) rightBtn.addEventListener('click', function(e) { e.stopPropagation(); next(); });

        // 点击幻灯片跳转
        slides.forEach(slide => {
            slide.addEventListener('click', function() {
                const url = this.dataset.url;
                if (url && url !== '#') window.open(url, '_blank');
            });
        });

        // 悬停/触摸暂停
        posterContainer.addEventListener('mouseenter', stopAutoPlay);
        posterContainer.addEventListener('mouseleave', startAutoPlay);
        posterContainer.addEventListener('touchstart', stopAutoPlay);
        posterContainer.addEventListener('touchend', startAutoPlay);

        // 初始化
        if (total > 0) {
            goTo(0);
            startAutoPlay();
        }
    }

    // 2. 公告轮播
    const announceTrack = document.getElementById('announceTrack');
    const announceDots = document.getElementById('announceDots');
    if (announceTrack) {
        const slides = announceTrack.querySelectorAll('.announce-slide');
        const total = slides.length;
        let current = 0;
        let autoTimer = null;
        const interval = 4000;

        if (announceDots && total > 1) {
            announceDots.innerHTML = '';
            for (let i = 0; i < total; i++) {
                const dot = document.createElement('button');
                dot.className = 'dot' + (i === 0 ? ' active' : '');
                dot.dataset.index = i;
                dot.addEventListener('click', function(e) {
                    e.stopPropagation();
                    goTo(parseInt(this.dataset.index));
                });
                announceDots.appendChild(dot);
            }
        }

        function goTo(index) {
            if (index < 0) index = total - 1;
            if (index >= total) index = 0;
            current = index;
            announceTrack.style.transform = 'translateX(-' + (current * 100) + '%)';
            if (announceDots) {
                const dots = announceDots.querySelectorAll('.dot');
                dots.forEach((d, i) => d.classList.toggle('active', i === current));
            }
            resetAutoPlay();
        }

        function next() { goTo(current + 1); }
        function prev() { goTo(current - 1); }

        function startAutoPlay() {
            if (autoTimer) clearInterval(autoTimer);
            if (total <= 1) return;
            autoTimer = setInterval(next, interval);
        }
        function stopAutoPlay() { if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } }
        function resetAutoPlay() { stopAutoPlay(); startAutoPlay(); }

        // 触摸暂停
        const container = document.getElementById('announceCarousel');
        container.addEventListener('mouseenter', stopAutoPlay);
        container.addEventListener('mouseleave', startAutoPlay);
        container.addEventListener('touchstart', stopAutoPlay);
        container.addEventListener('touchend', startAutoPlay);

        if (total > 0) {
            goTo(0);
            startAutoPlay();
        }
    }

    // 3. 搜索补全（如果全局函数存在）
    if (typeof window.initSearchSuggest === 'function') {
        document.querySelectorAll('input[data-search-suggest]').forEach(function(el) {
            if (!el.dataset.suggestInitialized) {
                window.initSearchSuggest(el);
            }
        });
    }

})();