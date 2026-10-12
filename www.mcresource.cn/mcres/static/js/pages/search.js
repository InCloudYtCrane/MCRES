// mcres/static/js/pages/search.js
// 搜索结果页脚本：高亮关键词、滑块实时显示 + 自动提交、高级面板折叠。
(function () {
  "use strict";

  var data = window.SEARCH_DATA || {};
  var keyword = (data.q || "").trim();

  // ============================================================
  // 高亮搜索结果
  // ============================================================
  function highlightText(text, kw) {
    if (!text) return text;
    var escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    var regex = new RegExp("(" + escaped + ")", "gi");
    return text.replace(regex, '<mark class="highlight-match">$1</mark>');
  }

  if (keyword) {
    document.querySelectorAll(".result-item").forEach(function (item) {
      var nameEl = item.querySelector(".main-name");
      if (nameEl) {
        nameEl.innerHTML = highlightText(nameEl.textContent, keyword);
      }
      var summaryEl = item.querySelector(".summary");
      if (summaryEl) {
        summaryEl.innerHTML = highlightText(summaryEl.textContent, keyword);
      }
      var descEl = item.querySelector(".description-preview");
      if (descEl) {
        descEl.innerHTML = highlightText(descEl.textContent, keyword);
      }
      var keywordsEl = item.querySelector(".keywords");
      if (keywordsEl) {
        keywordsEl.innerHTML = highlightText(keywordsEl.textContent, keyword);
      }
    });

    var searchInput = document.querySelector('input[name="q"]');
    if (searchInput) {
      searchInput.value = keyword;
    }
  }

  // ============================================================
  // 滑块实时显示 + 自动提交
  // ============================================================
  var form = document.getElementById("searchForm");
  var thresholdSlider = document.getElementById("thresholdSlider");
  var thresholdDisplay = document.getElementById("thresholdDisplay");
  var fuzzySlider = document.getElementById("fuzzyWeightSlider");
  var fuzzyDisplay = document.getElementById("fuzzyWeightDisplay");

  function updateDisplay(slider, display) {
    if (!slider || !display) return;
    display.textContent = parseFloat(slider.value).toFixed(2);
  }

  updateDisplay(thresholdSlider, thresholdDisplay);
  updateDisplay(fuzzySlider, fuzzyDisplay);

  if (thresholdSlider) {
    thresholdSlider.addEventListener("input", function () {
      updateDisplay(this, thresholdDisplay);
    });
  }
  if (fuzzySlider) {
    fuzzySlider.addEventListener("input", function () {
      updateDisplay(this, fuzzyDisplay);
    });
  }

  function submitForm() {
    if (form) form.submit();
  }
  if (thresholdSlider) thresholdSlider.addEventListener("change", submitForm);
  if (fuzzySlider) fuzzySlider.addEventListener("change", submitForm);

  // ============================================================
  // 高级面板折叠切换
  // ============================================================
  var panel = document.getElementById("advancedPanel");
  var toggle = document.getElementById("advancedToggle");
  if (panel && toggle) {
    toggle.addEventListener("click", function () {
      panel.classList.toggle("open");
    });

    // 如果参数偏离默认值（阈值 0.8 / 模糊权重 0.5），自动展开面板
    var threshold = parseFloat(data.threshold);
    var fuzzy = parseFloat(data.fuzzy_weight);
    var defaultThreshold = 0.8;
    var defaultFuzzy = 0.5;
    if (
      Math.abs(threshold - defaultThreshold) > 0.001 ||
      Math.abs(fuzzy - defaultFuzzy) > 0.001
    ) {
      panel.classList.add("open");
    }
  }
})();
