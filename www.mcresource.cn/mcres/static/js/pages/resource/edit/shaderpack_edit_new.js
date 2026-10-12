// mcres/static/js/pages/resource/edit/shaderpack_edit_new.js
(function() {
        'use strict';

        const mode = window._mode;
        const reviewId = window._reviewId;
        const resourceId = window._resourceId;
        const isNewCreate = (mode === 'new' && !reviewId);

        window.initAuthorAndDownload(
            window._authors,
            window._downloadLinks
        );

        // ===== 初始化富文本编辑器（光影包） =====
        const editorContainer = document.getElementById('shaderEditor');
        if (editorContainer) {
            const initialData = `window._description`;
            window._shaderEditor = new McresEditor(
                editorContainer,
                initialData,
                '在这里编写光影包介绍……'
            );
            console.log('光影包编辑器已初始化');
        }

        // ===== 加载站内规则 =====
        if (typeof window.loadRulesToSidebar === 'function') {
            window.loadRulesToSidebar('rulesSidebarList');
        }

        // ============================================================
        // 防撞车检测（仅全新创建时启用）
        // ============================================================
        let performDuplicateCheck = null;
        if (isNewCreate) {
            const _dupCtx = window.EditPage.initDuplicateCheck({
                type: 'shaderpack',
                resourceName: '光影包',
                urlPrefix: '/shaderpack'
            });
            performDuplicateCheck = _dupCtx.performDuplicateCheck;
            window._checkDuplicate = _dupCtx.checkDuplicate;
        }

        // ============================================================
        // 提交逻辑
        // ============================================================
        document.getElementById('submitBtn').addEventListener('click', function() {
            if (mode === 'edit' && document.getElementById('publishForm').classList.contains('locked')) {
                Toast.warning('该光影包已被锁定，无法提交修改。');
                return;
            }

            const edit_resource_id = document.getElementById('edit_resource_id').value;
            const review_id = document.getElementById('review_id').value;
            const change_summary = document.getElementById('changeSummary').value.trim();
            const messenger = document.getElementById('messenger') ? document.getElementById('messenger').value.trim() : '';
            const main_name = document.getElementById('main_name').value.trim();
            const sub_name = document.getElementById('sub_name').value.trim();
            const abbr = document.getElementById('abbr').value.trim();
            const summary = document.getElementById('summary').value.trim();

            let style = '';
            document.querySelectorAll('input[name="style"]').forEach(r => { if (r.checked) style = r.value; });
            let performance = '';
            document.querySelectorAll('input[name="performance"]').forEach(r => { if (r.checked) performance = r.value; });

            const cover = window._coverBase64 || document.getElementById('coverPreview').src || '';
            const screenshots = window._screenshotsBase64 || [];
            const description = window._shaderEditor ? window._shaderEditor.getData() : '';

            const platforms = [];
            document.querySelectorAll('input[name="platforms"]:checked').forEach(cb => platforms.push(cb.value));
            const versions = [];
            document.querySelectorAll('input[name="versions"]:checked').forEach(cb => versions.push(cb.value));
            const engines = [];
            document.querySelectorAll('input[name="engines"]:checked').forEach(cb => engines.push(cb.value));
            const features = [];
            document.querySelectorAll('input[name="features"]:checked').forEach(cb => features.push(cb.value));

            const authors = [];
            document.querySelectorAll('#authorList .author-item input').forEach(inp => {
                const val = inp.value.trim();
                if (val) authors.push(val);
            });
            const status = document.getElementById('status').value;
            const download_links = [];
            document.querySelectorAll('#downloadList .link-item').forEach(item => {
                const inputs = item.querySelectorAll('input');
                const name = inputs[0].value.trim();
                const url = inputs[1].value.trim();
                if (name && url) download_links.push({ name, url });
            });

            const keywords = document.getElementById('keywords').value.trim();
            const license = document.getElementById('license').value.trim();
            const mcmod_id = document.getElementById('mcmod_id').value.trim();
            const curseforge_id = document.getElementById('curseforge_id').value.trim();
            const modrinth_id = document.getElementById('modrinth_id').value.trim();
            const bilibili_video = document.getElementById('bilibili_video').value.trim();

            let errors = [];
            if (!main_name) errors.push('请填写「主要名称」');
            if (!summary) errors.push('请填写「一句话简介」');
            if (!cover) errors.push('请上传「光影包封面」');
            if (screenshots.length < 2) errors.push(`「光影截图」至少需要 2 张 (当前 ${screenshots.length} 张)`);
            if (!style) errors.push('请选择「光影包风格」');
            if (!performance) errors.push('请选择「性能等级」');
            if (platforms.length === 0) errors.push('请选择「支持平台」');
            if (versions.length === 0) errors.push('请选择「支持 MC 版本」');
            if (engines.length === 0) errors.push('请选择「光影引擎」');
            if (authors.length === 0) errors.push('请至少添加一位「作者」');
            if (download_links.length === 0) errors.push('请至少添加一个有效的「下载链接」');

            if (errors.length > 0) {
                Toast.warning('请完善以下必填项：\n\n• ' + errors.join('\n• '));
                document.querySelector('.tab-btn[data-tab="basic"]').click();
                return;
            }

            const payload = {
                main_name, sub_name, abbr, summary,
                style,
                performance,
                cover, screenshots, description,
                platforms, versions,
                engines, features,
                authors, status, download_links,
                keywords, license, mcmod_id,
                curseforge_id, modrinth_id,
                bilibili_video,
                change_summary: change_summary || '',
                messenger: messenger || ''
            };

            let submitUrl;
            if (mode === 'edit') {
                submitUrl = '/shaderpack/edit/' + edit_resource_id;
                if (review_id) payload.review_id = parseInt(review_id, 10);
            } else {
                submitUrl = '/shaderpack/new';
                if (review_id) payload.id = parseInt(review_id, 10);
            }

            const submitBtn = document.getElementById('submitBtn');
            submitBtn.disabled = true;
            submitBtn.textContent = mode === 'edit' ? '更新中…' : '提交中…';

            (async function() {
                let duplicateResult = null;
                if (isNewCreate && typeof performDuplicateCheck === 'function') {
                    duplicateResult = await performDuplicateCheck(main_name, curseforge_id, modrinth_id, mcmod_id);
                }

                window.showSubmitModal({
                    title: mode === 'edit' ? '确认更新' : '确认提交',
                    message: mode === 'edit' ? '确定要更新此光影包吗？' : '确定要提交此光影包吗？',
                    duplicateWarning: duplicateResult,
                    onConfirm: async (updateProgress) => {
                        updateProgress('正在提交数据…');
                        const response = await fetch(submitUrl, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload),
                        });
                        if (!response.ok) {
                            let errMsg = `HTTP ${response.status}`;
                            try {
                                const errData = await response.json();
                                errMsg = errData.message || errMsg;
                            } catch (_) {}
                            throw new Error(errMsg);
                        }
                        const data = await response.json();
                        updateProgress('处理响应…');
                        return data;
                    },
                    onSuccess: (data) => {
                        if (data.id) {
                            window.location.href = '/shaderpack/' + data.id;
                        } else {
                            window.location.href = '/review?type=shaderpack';
                        }
                    }
                }).catch(err => {
                    if (err.message !== '用户取消') {
                        console.error(err);
                    }
                }).finally(() => {
                    submitBtn.disabled = false;
                    submitBtn.textContent = mode === 'edit' ? '更新光影包' : '提交光影包';
                });
            })();
        });

        console.log('光影包编辑/发布页面已加载，mode=' + mode);
    })();

// ---------- 内联 onclick 替代 ----------
(function () {
    'use strict';
    var addAuthorBtn = document.getElementById('addAuthorBtn');
    if (addAuthorBtn) addAuthorBtn.addEventListener('click', addAuthor);
    var addDownloadLinkBtn = document.getElementById('addDownloadLinkBtn');
    if (addDownloadLinkBtn) addDownloadLinkBtn.addEventListener('click', addDownloadLink);
})();
