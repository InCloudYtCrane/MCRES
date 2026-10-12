// mcres/static/js/pages/index/review_list.js
document.addEventListener('DOMContentLoaded', function() {
        // ====== 模式切换逻辑 ======
        const modeRadios = document.querySelectorAll('input[name="filterMode"]');
        const countGroup = document.getElementById('countModeGroup');
        const dateGroup = document.getElementById('dateModeGroup');

        function toggleMode() {
            const mode = document.querySelector('input[name="filterMode"]:checked').value;
            if (mode === 'count') {
                countGroup.classList.remove('hidden');
                dateGroup.classList.add('hidden');
            } else {
                countGroup.classList.add('hidden');
                dateGroup.classList.remove('hidden');
            }
        }
        modeRadios.forEach(radio => radio.addEventListener('change', toggleMode));
        toggleMode();

        // ====== 筛选逻辑 ======
        const applyBtn = document.getElementById('applyFilterBtn');
        const resetBtn = document.getElementById('resetFilterBtn');
        const limitSelect = document.getElementById('limitSelect');
        const statusCbs = document.querySelectorAll('.status-cb');
        const uidInput = document.getElementById('uidInput');
        const resourceNameInput = document.getElementById('resourceNameInput');
        const resourceIdInput = document.getElementById('resourceIdInput');
        const operationTypeSelect = document.getElementById('operationTypeSelect');
        const sortSelect = document.getElementById('sortSelect');
        const startDateInput = document.getElementById('startDateInput');
        const endDateInput = document.getElementById('endDateInput');

        function buildQuery(page) {
            const type = window.REVIEW_LIST.type;
            const mode = document.querySelector('input[name="filterMode"]:checked').value;
            const limit = limitSelect.value;
            const uid = uidInput.value.trim();
            const resource_name = resourceNameInput.value.trim();
            const resource_id = resourceIdInput.value.trim();
            const operation_type = operationTypeSelect.value;
            const sort = sortSelect.value;
            const start_date = startDateInput.value;
            const end_date = endDateInput.value;

            const selectedStatus = [];
            statusCbs.forEach(cb => {
                if (cb.checked) selectedStatus.push(cb.value);
            });
            const statusStr = selectedStatus.length ? selectedStatus.join(',') : 'pending';

            let url = `/review?type=${type}&mode=${mode}&limit=${limit}&status=${statusStr}`;
            if (uid) url += `&uid=${uid}`;
            if (resource_name) url += `&resource_name=${encodeURIComponent(resource_name)}`;
            if (resource_id) url += `&resource_id=${resource_id}`;
            if (operation_type !== 'all') url += `&operation_type=${operation_type}`;
            if (sort) url += `&sort=${sort}`;
            if (start_date) url += `&start_date=${start_date}`;
            if (end_date) url += `&end_date=${end_date}`;
            if (page) url += `&page=${page}`;
            return url;
        }

        function applyFilter() {
            window.location.href = buildQuery(1);
        }

        function resetFilter() {
            window.location.href = `/review?type=${type}&mode=count&limit=50&status=pending`;
        }

        applyBtn.addEventListener('click', applyFilter);
        resetBtn.addEventListener('click', resetFilter);

        document.querySelectorAll('#resourceNameInput, #resourceIdInput, #uidInput, #startDateInput, #endDateInput').forEach(el => {
            el.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') applyFilter();
            });
        });

        // ====== 分页跳转 ======
        const prevBtn = document.getElementById('prevPageBtn');
        const nextBtn = document.getElementById('nextPageBtn');
        const jumpBtn = document.getElementById('jumpPageBtn');
        const jumpInput = document.getElementById('jumpPageInput');
        const currentPage = window.REVIEW_LIST.page;
        const totalPages = window.REVIEW_LIST.totalPages;

        if (prevBtn) {
            prevBtn.addEventListener('click', function() {
                if (currentPage > 1) window.location.href = buildQuery(currentPage - 1);
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', function() {
                if (currentPage < totalPages) window.location.href = buildQuery(currentPage + 1);
            });
        }
        if (jumpBtn && jumpInput) {
            jumpBtn.addEventListener('click', function() {
                let page = parseInt(jumpInput.value);
                if (isNaN(page) || page < 1) page = 1;
                if (page > totalPages) page = totalPages;
                if (page !== currentPage) window.location.href = buildQuery(page);
            });
            jumpInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') jumpBtn.click();
            });
        }

        // ====== 展开/折叠时间线 ======
        document.querySelectorAll('.expand-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const targetId = this.dataset.target;
                const targetRow = document.querySelector(targetId);
                if (!targetRow) return;
                targetRow.classList.toggle('open');
                this.classList.toggle('open');
            });
        });

        // ====== 撤回按钮 ======
        document.querySelectorAll('.recall-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                if (!confirm('确定要撤回此审核条目吗？撤回后您可以在“已撤回”列表中重新提交。')) return;

                const table = this.dataset.table;
                const id = this.dataset.id;
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 撤回中...';
                this.disabled = true;

                fetch('/review/recall', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: `table=${encodeURIComponent(table)}&id=${encodeURIComponent(id)}`
                })
                .then(res => res.ok ? res.json() : Promise.reject('网络错误'))
                .then(data => {
                    if (data.success) {
                        window.location.reload();
                    } else {
                        alert(data.message || '撤回失败');
                        this.innerHTML = originalText;
                        this.disabled = false;
                    }
                })
                .catch(err => {
                    alert('请求失败：' + err);
                    this.innerHTML = originalText;
                    this.disabled = false;
                });
            });
        });
    });
