// mcres/static/js/components/toast.js
// 全站统一的 Toast 通知组件。
// API：
//   Toast.show('消息', 'success' | 'error' | 'warning' | 'info')
//   Toast.success('消息')
//   Toast.error('消息')
//   Toast.warning('消息')
//   Toast.info('消息')
// 兼容旧 API：
//   window.showToast('消息')  → Toast.info('消息')
//   window.posterToast('消息') → Toast.info('消息')
(function (global) {
  "use strict";

  var ICON_MAP = {
    success: "fa-check-circle",
    error: "fa-circle-exclamation",
    warning: "fa-triangle-exclamation",
    info: "fa-circle-info",
  };

  var DEFAULT_DURATION = 3000;

  var container = null;

  function ensureContainer() {
    if (container && document.body.contains(container)) return container;
    container = document.createElement("div");
    container.className = "toast-container";
    container.id = "mcres-toast-container";
    document.body.appendChild(container);
    return container;
  }

  function show(message, type, duration) {
    if (message == null) return null;
    type = type || "info";
    duration = typeof duration === "number" ? duration : DEFAULT_DURATION;

    var box = ensureContainer();
    var item = document.createElement("div");
    item.className = "toast-item toast-" + type;

    var iconCls = ICON_MAP[type] || ICON_MAP.info;
    item.innerHTML =
      '<i class="fas ' +
      iconCls +
      ' toast-icon"></i>' +
      '<span class="toast-msg"></span>';

    // 用 textContent 防止 XSS
    item.querySelector(".toast-msg").textContent = String(message);

    box.appendChild(item);

    // 触发进入动画
    requestAnimationFrame(function () {
      item.classList.add("toast-show");
    });

    // 定时移除
    var timer = setTimeout(function () {
      item.classList.remove("toast-show");
      item.classList.add("toast-hide");
      setTimeout(function () {
        if (item.parentNode) item.parentNode.removeChild(item);
      }, 260);
    }, duration);

    // 点击立即关闭
    item.addEventListener("click", function () {
      clearTimeout(timer);
      item.classList.remove("toast-show");
      item.classList.add("toast-hide");
      setTimeout(function () {
        if (item.parentNode) item.parentNode.removeChild(item);
      }, 260);
    });

    return item;
  }

  var Toast = {
    show: show,
    success: function (m, d) {
      return show(m, "success", d);
    },
    error: function (m, d) {
      return show(m, "error", d);
    },
    warning: function (m, d) {
      return show(m, "warning", d);
    },
    info: function (m, d) {
      return show(m, "info", d);
    },
  };

  global.Toast = Toast;

  // 兼容旧 API
  if (typeof global.showToast !== "function") {
    global.showToast = function (m) {
      return Toast.show(m, "info");
    };
  }
  if (typeof global.posterToast !== "function") {
    global.posterToast = function (m) {
      return Toast.show(m, "info");
    };
  }
})(window);
