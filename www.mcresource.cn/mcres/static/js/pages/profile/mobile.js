// mcres/static/js/pages/profile/mobile.js
// 移动端个人主页：扫码登录确认。
(function () {
  "use strict";

  var scanBtn = document.getElementById("scanBtn");
  var confirmPage = document.getElementById("qr-confirm-page");
  var confirmAvatar = document
    .getElementById("confirmAvatar")
    .querySelector("img");
  var confirmNickname = document.getElementById("confirmNickname");
  var confirmBtn = document.getElementById("confirmBtn");
  var countdownNum = document.getElementById("countdownNum");
  var confirmClose = document.getElementById("confirmClose");
  var confirmSuccess = document.getElementById("confirmSuccess");

  if (!scanBtn) return;

  var countdownTimer = null;
  var countdownValue = 3;
  var isConfirming = false;
  var scannedQrId = null;

  function showConfirmPage(qrId, userInfo) {
    scannedQrId = qrId;
    confirmAvatar.src =
      userInfo.avatar || "https://img.mcresource.cn/user/avatar/default.jpg";
    confirmNickname.textContent = userInfo.nickname || "用户";
    confirmSuccess.style.display = "none";
    confirmBtn.style.display = "block";
    confirmBtn.className = "confirm-btn";
    confirmBtn.disabled = false;
    confirmPage.classList.add("active");
    document.body.style.overflow = "hidden";

    countdownValue = 3;
    confirmBtn.innerHTML = '确认登录(<span class="countdown">3</span>s)';
    confirmBtn.classList.remove("enabled");

    clearInterval(countdownTimer);
    countdownTimer = setInterval(function () {
      countdownValue--;
      if (countdownValue <= 0) {
        clearInterval(countdownTimer);
        confirmBtn.innerHTML = "确认登录";
        confirmBtn.classList.add("enabled");
      } else {
        confirmBtn.innerHTML =
          '确认登录(<span class="countdown">' + countdownValue + "</span>s)";
      }
    }, 1000);
  }

  function hideConfirmPage() {
    confirmPage.classList.remove("active");
    document.body.style.overflow = "";
    clearInterval(countdownTimer);
    scannedQrId = null;
    isConfirming = false;
  }

  confirmBtn.addEventListener("click", function () {
    if (isConfirming) return;
    if (!confirmBtn.classList.contains("enabled")) return;
    if (!scannedQrId) return;

    isConfirming = true;
    confirmBtn.textContent = "确认中...";
    confirmBtn.classList.remove("enabled");

    fetch("/login/qrcode/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_id: scannedQrId }),
    })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data.success) {
          confirmBtn.style.display = "none";
          confirmSuccess.style.display = "block";
          setTimeout(function () {
            hideConfirmPage();
          }, 2500);
        } else {
          Toast.error(data.message || "登录失败，请重试");
          hideConfirmPage();
        }
      })
      .catch(function (err) {
        Toast.error("网络错误，请重试");
        console.error(err);
        hideConfirmPage();
      })
      .finally(function () {
        isConfirming = false;
      });
  });

  confirmClose.addEventListener("click", hideConfirmPage);

  confirmPage.addEventListener("click", function (e) {
    if (e.target === this) {
      if (isConfirming) return;
      if (confirmSuccess.style.display === "block") {
        hideConfirmPage();
        return;
      }
      if (confirm("确定取消登录吗？")) {
        hideConfirmPage();
      }
    }
  });

  // ===== 启动扫码器 =====
  scanBtn.addEventListener("click", function () {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      Toast.warning("您的浏览器不支持摄像头，请使用最新版Chrome或Safari");
      return;
    }

    var userInfo = window.USER_INFO;
    if (!userInfo || !userInfo.id) {
      Toast.warning("请先登录后再使用扫码功能");
      return;
    }

    var existing = document.getElementById("qr-reader-container");
    if (existing) existing.remove();

    var container = document.createElement("div");
    container.id = "qr-reader-container";
    container.style.cssText =
      "position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:9999; display:flex; flex-direction:column; align-items:center; justify-content:center; padding:20px;";
    container.innerHTML = `
            <div style="background:#11161c; border-radius:20px; padding:20px; width:100%; max-width:400px; position:relative;">
                <button id="close-scanner" style="position:absolute; top:10px; right:10px; background:rgba(255,255,255,0.1); border:none; color:#fff; font-size:24px; cursor:pointer; padding:4px 12px; border-radius:12px; z-index:10;">×</button>
                <div id="qr-reader" style="width:100%;"></div>
                <p style="color:#b0b8c0; text-align:center; margin-top:12px; font-size:14px;">将二维码置于框中自动识别</p>
            </div>
        `;
    document.body.appendChild(container);

    var closeBtn = document.getElementById("close-scanner");
    var html5QrCode = null;

    function closeScanner() {
      if (html5QrCode) {
        html5QrCode
          .stop()
          .then(function () {
            container.remove();
          })
          .catch(function () {
            container.remove();
          });
      } else {
        container.remove();
      }
    }

    closeBtn.addEventListener("click", closeScanner);

    html5QrCode = new Html5Qrcode("qr-reader");
    var config = { fps: 10, qrbox: { width: 250, height: 250 } };

    html5QrCode
      .start(
        { facingMode: "environment" },
        config,
        function (decodedText, decodedResult) {
          // 扫描成功 - 停止扫码器
          html5QrCode
            .stop()
            .then(function () {
              container.remove();
            })
            .catch(function () {
              container.remove();
            });

          try {
            var url = new URL(decodedText);
            var qrId = url.searchParams.get("qr_id");
            if (!qrId) {
              Toast.error("二维码无效，请确保是 MCRES 登录二维码");
              return;
            }

            var currentUser = window.USER_INFO;
            if (!currentUser || !currentUser.id) {
              Toast.warning("请先登录");
              return;
            }

            // 1. 先调用 scanned 接口，告知后端已扫码
            fetch("/login/qrcode/scanned", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ qr_id: qrId }),
            })
              .then(function (res) {
                return res.json();
              })
              .then(function (scannedData) {
                if (scannedData.success) {
                  // 2. 弹出确认页面
                  fetch("/api/user/" + currentUser.id)
                    .then(function (res) {
                      return res.json();
                    })
                    .then(function (userData) {
                      showConfirmPage(qrId, userData);
                    })
                    .catch(function () {
                      showConfirmPage(qrId, {
                        nickname: currentUser.nickname || "用户",
                        avatar:
                          currentUser.avatar ||
                          "https://img.mcresource.cn/user/avatar/default.jpg",
                      });
                    });
                } else {
                  Toast.error("扫码失败：" + scannedData.message);
                }
              })
              .catch(function (err) {
                Toast.error("网络错误，请重试");
                console.error(err);
              });
          } catch (e) {
            Toast.error("二维码解析失败，请确保是 MCRES 登录二维码");
            console.error(e);
          }
        },
        function (errorMessage) {
          // 扫描错误，忽略
        },
      )
      .catch(function (err) {
        Toast.error("无法启动摄像头，请确认已授权摄像头权限");
        container.remove();
      });
  });
})();
