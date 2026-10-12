// mcres/static/js/pages/auth/github_sync.js
(function () {
    var nickCb = document.getElementById("syncNicknameCb");
    var nickInput = document.getElementById("nicknameInput");
    if (nickCb && nickInput) {
      var syncNickState = function () {
        nickInput.disabled = !nickCb.checked;
      };
      nickCb.addEventListener("change", syncNickState);
      syncNickState();
    }
    document.getElementById("skipBtn").addEventListener("click", function () {
      document.getElementById("skipForm").submit();
    });
  })();

// ---------- 头像加载失败兜底（替代内联 onerror） ----------
(function () {
  var img = document.querySelector(".thumb img");
  if (!img) return;
  function fallback() {
    if (img.parentElement) img.parentElement.innerHTML = '<i class="fas fa-user"></i>';
  }
  img.addEventListener("error", fallback);
  if (img.complete && img.naturalWidth === 0) fallback();
})();
