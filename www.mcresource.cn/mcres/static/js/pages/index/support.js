// mcres/static/js/pages/index/support.js
(function () {
    'use strict';
    var picker = document.getElementById('supMonthPicker');
    if (!picker) return;
    picker.addEventListener('change', function () {
        var month = this.value;
        if (!/^\d{4}-\d{2}$/.test(month)) return;
        var url = new URL(window.location.href);
        url.searchParams.set('month', month);
        url.searchParams.delete('income_page');
        url.searchParams.delete('expense_page');
        window.location.href = url.toString();
    });
})();
