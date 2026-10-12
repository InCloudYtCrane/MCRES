// mcres/static/js/pages/resource/diff/children/preset_diff_versions.js
function updateCompareButton() {
      var allCheckboxes = document.querySelectorAll('.version-checkbox');
      var checked = document.querySelectorAll('.version-checkbox:checked');
      var btn = document.getElementById('compareBtn');
      var hint = document.getElementById('selectionHint');
      var count = checked.length;
      if (count === 2) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-magnifying-glass"></i> 对比选中 (' + checked[0].value + ' ↔ ' + checked[1].value + ')';
          hint.innerHTML = '<i class="fas fa-check-circle"></i> 已选择两个版本，点击"对比选中"查看差异';
          allCheckboxes.forEach(function(cb) {
              if (!cb.checked) cb.disabled = true;
          });
      } else {
          btn.disabled = true;
          btn.innerHTML = '<i class="fas fa-magnifying-glass"></i> 对比选中 (已选 ' + count + '/2)';
          allCheckboxes.forEach(function(cb) { cb.disabled = false; });
          if (count === 0) {
              hint.innerHTML = '<i class="fas fa-lightbulb"></i> 请勾选两个版本进行对比（可选择任意两个版本）';
          } else {
              hint.innerHTML = '<i class="fas fa-lightbulb"></i> 请再勾选一个版本 (当前已选 ' + count + '/2)';
          }
      }
  }

  function compareSelected() {
      var checked = document.querySelectorAll('.version-checkbox:checked');
      if (checked.length !== 2) {
          Toast.warning('请选择两个版本进行对比');
          return;
      }
      var ids = [checked[0].value, checked[1].value];
      window.location.href = '/shaderpack/' + shaderpackId + '/preset/' + presetId + '/diff/compare?ids=' + ids[0] + ',' + ids[1];
  }

  document.addEventListener('DOMContentLoaded', function() {
      updateCompareButton();
      var total = document.querySelectorAll('.version-checkbox').length;
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
