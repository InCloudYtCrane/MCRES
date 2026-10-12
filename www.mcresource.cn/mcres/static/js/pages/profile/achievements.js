// mcres/static/js/pages/profile/achievements.js
(function () {
    var menu = document.getElementById('ach-category-menu');
    if (!menu) return;

    menu.addEventListener('click', function (e) {
        var btn = e.target.closest('.works-sub-btn');
        if (!btn) return;

        menu.querySelectorAll('.works-sub-btn').forEach(function (b) {
            b.classList.remove('active');
        });
        btn.classList.add('active');

        var type = btn.dataset.type;
        document.querySelectorAll('.works-sub-content').forEach(function (el) {
            if (el.id && el.id.indexOf('ach-') === 0) {
                el.classList.remove('active');
            }
        });
        var target = document.getElementById('ach-' + type);
        if (target) target.classList.add('active');
    });
})();
