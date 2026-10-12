// mcres/static/js/pages/auth/maintenance_login.js
// 主管维护登录：验证码刷新
(function () {
    'use strict';
    document.addEventListener('DOMContentLoaded', function () {
        var captchaImg = document.getElementById('captchaImg');
        function refresh() {
            if (captchaImg) captchaImg.src = '/captcha?' + Date.now();
        }
        if (window.MAINTENANCE_LOGIN && window.MAINTENANCE_LOGIN.hasError) refresh();
        if (captchaImg) captchaImg.addEventListener('click', refresh);
        var refreshLink = document.querySelector('.captcha-refresh a');
        if (refreshLink) {
            refreshLink.addEventListener('click', function (e) {
                e.preventDefault();
                refresh();
            });
        }
    });
})();
