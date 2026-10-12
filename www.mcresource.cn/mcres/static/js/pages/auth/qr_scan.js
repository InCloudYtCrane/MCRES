// mcres/static/js/pages/auth/qr_scan.js
(function () {
    var qrId = new URLSearchParams(window.location.search).get("qr_id");
    if (!qrId) {
      document.getElementById("statusIcon").className = "error";
      document.getElementById("statusText").textContent = "❌ 无效的二维码";
      return;
    }
    fetch("/login/qrcode/confirm?qr_id=" + qrId, {
      method: "GET",
      headers: { Accept: "application/json" },
    })
      .then(function (res) {
        if (res.ok) {
          document.getElementById("statusIcon").className = "success";
          document.getElementById("statusText").textContent =
            "✅ 登录成功！请返回电脑端查看。";
        } else {
          throw new Error("请求失败");
        }
      })
      .catch(function () {
        document.getElementById("statusIcon").className = "error";
        document.getElementById("statusText").textContent =
          "❌ 登录失败，请重试";
      });
  })();
