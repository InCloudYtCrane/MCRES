// mcres/static/js/pages/auth/login.js
// 登录页脚本：验证码刷新、协议校验（抖动复选框）、二维码登录。
(function () {
  "use strict";

  // ===== 全局刷新验证码 =====
  window.refreshCaptcha = function () {
    var img = document.getElementById("captchaImg");
    if (img) {
      img.src = "/captcha?_=" + Date.now();
    }
  };

  // ============================================================
  // 协议校验：未勾选则抖动复选框行，返回 false
  // ============================================================
  function checkAgreement() {
    var agreeCheckbox = document.getElementById("agreeLogin");
    var agreeRow = document.querySelector(".agree-row");
    if (!agreeCheckbox || !agreeRow) return true;

    if (agreeCheckbox.checked) return true;

    // 已勾选过就不要重复触发；未勾选则抖一下
    agreeRow.classList.remove("shake");
    void agreeRow.offsetWidth; // 强制重排，重置动画
    agreeRow.classList.add("shake");
    agreeRow.classList.add("error");

    // 动画结束后清除 shake 类（error 保留，直到用户勾选）
    setTimeout(function () {
      agreeRow.classList.remove("shake");
    }, 600);

    return false;
  }

  // 用户勾选后清除 error 状态
  (function () {
    var agreeCheckbox = document.getElementById("agreeLogin");
    var agreeRow = document.querySelector(".agree-row");
    if (agreeCheckbox && agreeRow) {
      agreeCheckbox.addEventListener("change", function () {
        if (this.checked) {
          agreeRow.classList.remove("error");
        }
      });
    }
  })();

  // ============================================================
  // 邮箱登录表单：提交前校验协议
  // ============================================================
  (function () {
    var loginForm = document.querySelector('.login-form form[action="/login"]');
    if (!loginForm) return;

    loginForm.addEventListener("submit", function (e) {
      if (!checkAgreement()) {
        e.preventDefault();
        return false;
      }
    });
  })();

  // ============================================================
  // 一键登录（QQ / GitHub）：点击前校验协议
  // ============================================================
  (function () {
    var socialIcons = document.querySelectorAll(".social-icon[data-href]");
    socialIcons.forEach(function (icon) {
      icon.addEventListener("click", function (e) {
        e.preventDefault();

        // 未勾协议 → 抖动 + 阻止跳转
        if (!checkAgreement()) {
          return false;
        }

        var url = this.getAttribute("data-href");
        if (url) {
          window.location.href = url;
        }
      });
    });
  })();

  // ============================================================
  // 二维码登录
  // ============================================================
  var qrId = null;
  var pollInterval = null;
  var qrOverlay = document.getElementById("qrOverlay");
  var qrStatusText = document.getElementById("qrStatusText");
  var qrSection = document.getElementById("qrLoginSection");

  var ua = navigator.userAgent || "";
  var isMobile =
    /Mobi|Android|iPhone|iPod|BlackBerry|Opera Mini|IEMobile/i.test(ua) &&
    !/iPad/i.test(ua);
  var isDesktop = !isMobile;

  if (isMobile) {
    qrSection.style.display = "none";
  } else {
    qrSection.style.display = "flex";
  }

  function showScannedOverlay() {
    qrOverlay.classList.add("active");
    qrStatusText.textContent = "📱 已扫码，请在手机上确认登录";
  }

  function resetQRCode() {
    qrOverlay.classList.remove("active");
  }

  function generateQR() {
    if (!isDesktop) return;
    var container = document.getElementById("qrCodeImg");
    container.innerHTML = "生成中...";

    fetch("/login/qrcode/generate")
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data.success) {
          qrId = data.qr_id;
          container.innerHTML = "";
          new QRCode(container, {
            text: data.qr_content,
            width: 200,
            height: 200,
            colorDark: "#000000",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.H,
          });
          resetQRCode();
          qrStatusText.textContent = "请用手机扫码";
          startPolling(qrId);
        } else {
          container.textContent = "生成失败，请刷新页面";
        }
      })
      .catch(function (err) {
        container.textContent = "网络错误，请刷新";
        console.error(err);
      });
  }

  function startPolling(id) {
    if (!isDesktop) return;
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(function () {
      fetch("/login/qrcode/status/" + id)
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (data.status === "scanned") {
            showScannedOverlay();
          } else if (data.status === "confirmed") {
            clearInterval(pollInterval);
            pollInterval = null;
            qrStatusText.textContent = "✅ 已确认，正在登录...";
            fetch("/login/qrcode/login", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              // 只回传 qr_id：user_id 由服务端从二维码会话里取，
              // 客户端传什么都不算数（安全修复 A1）
              body: JSON.stringify({ qr_id: id }),
            })
              .then(function (res) {
                return res.json();
              })
              .then(function (loginData) {
                if (loginData.success) {
                  window.location.href = "/profile/" + data.user.id;
                } else {
                  qrStatusText.textContent =
                    "❌ 登录失败：" + loginData.message;
                }
              })
              .catch(function (err) {
                qrStatusText.textContent = "❌ 登录请求失败";
                console.error(err);
              });
          } else if (data.status === "expired") {
            clearInterval(pollInterval);
            pollInterval = null;
            qrStatusText.textContent = "⏰ 二维码已过期，请刷新页面重新生成";
            document.getElementById("qrCodeImg").innerHTML = "已过期";
            qrOverlay.classList.remove("active");
          }
        })
        .catch(function (err) {});
    }, 1500);
  }

  window.addEventListener("load", function () {
    window.refreshCaptcha();

    if (isDesktop) {
      generateQR();
    } else {
      var container = document.getElementById("qrCodeImg");
      if (container) {
        container.textContent = "请在电脑或平板端打开";
      }
      var statusText = document.getElementById("qrStatusText");
      if (statusText) {
        statusText.textContent = "二维码仅支持电脑和平板";
      }
    }
  });
})();

// ---------- 验证码刷新（替代内联 onclick） ----------
(function () {
  var img = document.getElementById("captchaImg");
  if (img) img.addEventListener("click", window.refreshCaptcha);
  var link = document.querySelector(".captcha-refresh a");
  if (link) link.addEventListener("click", function (e) { e.preventDefault(); window.refreshCaptcha(); });
})();
