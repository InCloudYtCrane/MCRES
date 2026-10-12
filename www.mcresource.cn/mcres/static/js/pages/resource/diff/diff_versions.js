// mcres/static/js/pages/resource/diff/diff_versions.js
function updateCompareButton() {
      const allCheckboxes = document.querySelectorAll('.version-checkbox');
      const checked = document.querySelectorAll('.version-checkbox:checked');
      const btn = document.getElementById('compareBtn');
      const hint = document.getElementById('selectionHint');
      const count = checked.length;
      if (count === 2) {
          btn.disabled = false;
          btn.innerHTML = `<i class="fas fa-magnifying-glass"></i> 对比选中 (${checked[0].value} ↔ ${checked[1].value})`;
          hint.innerHTML = '<i class="fas fa-check-circle"></i> 已选择两个版本，点击"对比选中"查看差异';
          allCheckboxes.forEach(cb => {
              if (!cb.checked) {
                  cb.disabled = true;
              }
          });
      } else {
          btn.disabled = true;
          btn.innerHTML = `<i class="fas fa-magnifying-glass"></i> 对比选中 (已选 ${count}/2)`;
          allCheckboxes.forEach(cb => {
              cb.disabled = false;
          });
          if (count === 0) {
              hint.innerHTML = '<i class="fas fa-lightbulb"></i> 请勾选两个版本进行对比（可选择任意两个版本）';
          } else {
              hint.innerHTML = `<i class="fas fa-lightbulb"></i> 请再勾选一个版本 (当前已选 ${count}/2)`;
          }
      }
  }

  function compareSelected() {
      const checked = document.querySelectorAll('.version-checkbox:checked');
      if (checked.length !== 2) {
          Toast.warning('请选择两个版本进行对比');
          return;
      }
      const ids = [checked[0].value, checked[1].value];
      window.location.href = `/${window._resourceType}/${window._resourceId}/diff/compare?ids=${ids[0]},${ids[1]}`;
  }

  document.addEventListener('DOMContentLoaded', function() {
      updateCompareButton();
      const total = document.querySelectorAll('.version-checkbox').length;
      if (total < 2) {
          document.getElementById('selectionHint').innerHTML = '<i class="fas fa-lightbulb"></i> 至少需要两个版本才能进行对比';
          document.getElementById('compareBtn').disabled = true;
          document.getElementById('compareBtn').innerHTML = '<i class="fas fa-magnifying-glass"></i> 对比选中 (需要 2 个版本)';
      }
  });

// ---------- 内联 onclick/onchange 替代 ----------
(function () {
    'use strict';
    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('compareBtn');
        if (btn) btn.addEventListener('click', compareSelected);
        document.addEventListener('change', function (e) {
            if (e.target && e.target.classList && e.target.classList.contains('version-checkbox')) {
                updateCompareButton();
            }
        });
    });
})();
