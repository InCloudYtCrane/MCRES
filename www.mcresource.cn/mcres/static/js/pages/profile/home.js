(function() {
    'use strict';

    function initContributionGraph() {
        var currentYear = new Date().getFullYear();
        var startYear = 2026;
        var yearSelect = document.getElementById('yearSelect');
        if (!yearSelect) return;

        // 生成年份选项
        yearSelect.innerHTML = '';
        for (var y = startYear; y <= currentYear; y++) {
            var opt = document.createElement('option');
            opt.value = y;
            opt.textContent = y + '年';
            if (y === currentYear) opt.selected = true;
            yearSelect.appendChild(opt);
        }

        // 创建提示框
        var tooltip = document.createElement('div');
        tooltip.className = 'custom-tooltip';
        tooltip.innerHTML = '<div class="tip-title"></div><div class="tip-detail"></div>';
        document.body.appendChild(tooltip);

        function showTooltip(event, titleText, detailText) {
            var rect = event.target.getBoundingClientRect();
            var tipTitle = tooltip.querySelector('.tip-title');
            var tipDetail = tooltip.querySelector('.tip-detail');
            tipTitle.textContent = titleText;
            tipDetail.textContent = detailText;
            var left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2;
            var top = rect.bottom + 8;
            if (left + tooltip.offsetWidth > window.innerWidth - 10) {
                left = window.innerWidth - tooltip.offsetWidth - 10;
            }
            if (left < 10) left = 10;
            if (top + tooltip.offsetHeight > window.innerHeight - 10) {
                top = rect.top - tooltip.offsetHeight - 8;
            }
            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
            tooltip.classList.add('visible');
        }

        function hideTooltip() {
            tooltip.classList.remove('visible');
        }

        function getTodayStr() {
            var now = new Date();
            var year = now.getFullYear();
            var month = String(now.getMonth() + 1).padStart(2, '0');
            var day = String(now.getDate()).padStart(2, '0');
            return year + '-' + month + '-' + day;
        }

        function getColor(count) {
            if (count === 0) return '#2a2a3a';
            var capped = Math.min(count, 365);
            var t = (capped - 1) / 364;
            var hue = 120 + t * 240;
            var sat = Math.round(60 + t * 25);
            var lig = Math.round(35 + t * 35);
            return 'hsl(' + hue + ', ' + sat + '%, ' + lig + '%)';
        }

        function renderGraph(year) {
            var container = document.getElementById('contributionGraph');
            if (!container) return;

            var todayStr = getTodayStr();
            var monthNames = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];
            var weekDays = ['日', '一', '二', '三', '四', '五', '六'];

            var html = '<div class="month-grid-container">';

            for (var m = 0; m < 12; m++) {
                var firstDay = new Date(year, m, 1);
                var lastDay = new Date(year, m + 1, 0);
                var daysInMonth = lastDay.getDate();
                var startWeekday = firstDay.getDay(); // 0=周日

                html += '<div class="month-grid-item">';
                html += '<div class="month-title">' + monthNames[m] + '</div>';

                // 星期行
                html += '<div class="weekday-row">';
                for (var wd = 0; wd < 7; wd++) {
                    html += '<span>' + weekDays[wd] + '</span>';
                }
                html += '</div>';

                // 日期格子
                html += '<div class="day-grid">';
                // 填充月初空白天
                for (var e = 0; e < startWeekday; e++) {
                    html += '<div class="day-cell empty"></div>';
                }
                // 日期
                for (var d = 1; d <= daysInMonth; d++) {
                    var dateStr = year + '-' + String(m + 1).padStart(2, '0') + '-' + String(d).padStart(2, '0');
                    var countData = (typeof editDailyData !== 'undefined' && editDailyData[dateStr]) ||
                        { edit: 0, submit_review: 0 };
                    var editCount = countData.edit || 0;
                    var submitCount = countData.submit_review || 0;
                    var totalCount = editCount + submitCount;
                    var color = getColor(totalCount);
                    var isToday = (dateStr === todayStr);
                    var borderStyle = isToday ? 'border:1px solid ' + roleColor + ';' : '';
                    var dataAttrs = 'data-date="' + dateStr + '" data-edit="' + editCount + '" data-submit="' + submitCount + '" data-total="' + totalCount + '"';
                    // 在格子内显示日期数字 d
                    html += '<div class="day-cell" ' + dataAttrs + ' style="background-color:' + color + '; ' + borderStyle + '">' + d + '</div>';
                }
                // 补全最后一行空白
                var totalCells = startWeekday + daysInMonth;
                var remainder = totalCells % 7;
                if (remainder > 0) {
                    for (var fill = 0; fill < 7 - remainder; fill++) {
                        html += '<div class="day-cell empty"></div>';
                    }
                }
                html += '</div>'; // .day-grid
                html += '</div>'; // .month-grid-item
            }

            html += '</div>'; // .month-grid-container
            container.innerHTML = html;

            // 绑定事件
            var cells = container.querySelectorAll('.day-cell:not(.empty)');
            cells.forEach(function(cell) {
                cell.addEventListener('mouseenter', function(e) {
                    var date = this.dataset.date;
                    var edit = parseInt(this.dataset.edit);
                    var submit = parseInt(this.dataset.submit);
                    var total = parseInt(this.dataset.total);
                    var titleText = date + ' 总操作 ' + total + ' 次';
                    var detailText = '编辑 ' + edit + ' 次，提交审核 ' + submit + ' 次';
                    showTooltip(e, titleText, detailText);
                });
                cell.addEventListener('mousemove', function(e) {
                    var rect = this.getBoundingClientRect();
                    var left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2;
                    var top = rect.bottom + 8;
                    if (left + tooltip.offsetWidth > window.innerWidth - 10) {
                        left = window.innerWidth - tooltip.offsetWidth - 10;
                    }
                    if (left < 10) left = 10;
                    if (top + tooltip.offsetHeight > window.innerHeight - 10) {
                        top = rect.top - tooltip.offsetHeight - 8;
                    }
                    tooltip.style.left = left + 'px';
                    tooltip.style.top = top + 'px';
                });
                cell.addEventListener('mouseleave', hideTooltip);
            });
        }

        var initialYear = parseInt(yearSelect.value);
        renderGraph(initialYear);
        yearSelect.addEventListener(' hange', function() {
            renderGraph(parseInt(this.value));
        });
    }

    // 暴露给全局，方便选项卡切换时调用
    window.initContributionGraph = initContributionGraph;

    // 自动初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initContributionGraph);
    } else {
        setTimeout(initContributionGraph, 100);
    }
})();
// ---------- 编辑动态分页跳转 ----------
(function () {
    'use strict';
    var input = document.getElementById('page-input');
    if (!input) return;
    function goToPage() {
        var total = (typeof profileTotalPages !== 'undefined' && profileTotalPages) ? profileTotalPages : 1;
        var page = parseInt(input.value, 10);
        if (page >= 1 && page <= total) {
            window.location.href = '?page=' + page;
        } else {
            alert('请输入 1 到 ' + total + ' 之间的页码');
        }
    }
    var btn = document.getElementById('page-jump-btn');
    if (btn) btn.addEventListener('click', goToPage);
    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') goToPage();
    });
})();
