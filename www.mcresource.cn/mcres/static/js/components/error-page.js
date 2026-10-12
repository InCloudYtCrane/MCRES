// mcres/static/js/pages/error.js
// 403 / 404 页面共用的搜索跳转逻辑。
(function () {
  "use strict";

  function performSearch() {
    var input = document.getElementById("searchInput");
    if (!input) return;
    var query = input.value.trim();
    if (!query) return;
    window.location.href = "/search?q=" + encodeURIComponent(query);
  }

  window.performSearch = performSearch;

  var input = document.getElementById("searchInput");
  if (input) {
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        performSearch();
      }
    });
  }
})();
