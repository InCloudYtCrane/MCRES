// mcres/static/js/pages/resource/detail/children/preset_detail.js
// ===== 复制 & 下载配置 =====
        function copyConfig() {
            const code = document.getElementById('configCode');
            const text = code.textContent;
            navigator.clipboard.writeText(text).then(() => {
                const btn = document.getElementById('copyBtn');
                btn.classList.add('copied');
                btn.innerHTML = '<i class="fas fa-check"></i> 已复制';
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.innerHTML = '<i class="fas fa-copy"></i> 复制';
                }, 2000);
            }).catch(() => {
                const range = document.createRange();
                range.selectNode(code);
                window.getSelection().removeAllRanges();
                window.getSelection().addRange(range);
                document.execCommand('copy');
                window.getSelection().removeAllRanges();
                const btn = document.getElementById('copyBtn');
                btn.classList.add('copied');
                btn.innerHTML = '<i class="fas fa-check"></i> 已复制';
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.innerHTML = '<i class="fas fa-copy"></i> 复制';
                }, 2000);
            });
        }

        function downloadConfig() {
            const code = document.getElementById('configCode');
            const text = code.textContent;
            const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = ((window.PRESET_DETAIL && window.PRESET_DETAIL.name) ? window.PRESET_DETAIL.name : 'preset') + '.txt';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        // ===== 灯箱 =====
        function openLightbox(src) {
            const lightbox = document.getElementById('lightbox');
            const img = document.getElementById('lightboxImg');
            img.src = src;
            lightbox.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

        function closeLightbox() {
            const lightbox = document.getElementById('lightbox');
            lightbox.classList.remove('active');
            document.body.style.overflow = '';
        }

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeLightbox();
        });

        // ===== 分享功能 =====
        function sharePage() {
            const url = window.location.href;
            const title = document.title || 'MCRES 方块工坊';
            const shareText = `MCRES · 方块工坊 - ${title} | ${url}`;
        
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(shareText)
                    .then(() => showToast('✅ 已复制分享内容到剪贴板！'))
                    .catch(() => fallbackCopy(shareText));
            } else {
                fallbackCopy(shareText);
            }
        }

        function fallbackCopy(text) {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            try {
                document.execCommand('copy');
                showToast('✅ 链接已复制到剪贴板！');
            } catch (e) {
                alert('复制失败，请手动复制链接：' + text);
            }
            document.body.removeChild(ta);
        }

        function showToast(msg) {
            // 移除已有提示（防止重叠）
            const old = document.querySelector('.mcrest-toast');
            if (old) old.remove();

            const toast = document.createElement('div');
            toast.className = 'mcrest-toast';
            toast.textContent = msg;
            Object.assign(toast.style, {
                position: 'fixed',
                bottom: '30px',
                left: '50%',
                transform: 'translateX(-50%)',
                background: 'rgba(0,0,0,0.8)',
                color: '#fff',
                padding: '12px 24px',
                borderRadius: '8px',
                fontSize: '14px',
                zIndex: '10001',
                backdropFilter: 'blur(4px)',
                transition: 'opacity 0.3s',
                opacity: '1',
                pointerEvents: 'none'
            });
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }

        console.log('✅ 预设详情页已加载');
// ---------- 事件绑定（替代内联 onclick） ----------
(function () {
    'use strict';
    document.addEventListener('DOMContentLoaded', function () {
        var shareBtn = document.getElementById('btn-share');
        if (shareBtn) shareBtn.addEventListener('click', sharePage);
        var copyBtn = document.getElementById('copyBtn');
        if (copyBtn) copyBtn.addEventListener('click', copyConfig);
        var dlBtn = document.getElementById('btn-download');
        if (dlBtn) dlBtn.addEventListener('click', downloadConfig);

        document.querySelectorAll('.screenshots img').forEach(function (img) {
            img.addEventListener('click', function () { openLightbox(this.getAttribute('src')); });
        });

        var lightbox = document.getElementById('lightbox');
        if (lightbox) lightbox.addEventListener('click', closeLightbox);
        var lightboxImg = document.getElementById('lightboxImg');
        if (lightboxImg) lightboxImg.addEventListener('click', function (e) { e.stopPropagation(); });
        var closeBtn = document.querySelector('.lightbox .close');
        if (closeBtn) closeBtn.addEventListener('click', function (e) { e.stopPropagation(); closeLightbox(); });
    });
})();

