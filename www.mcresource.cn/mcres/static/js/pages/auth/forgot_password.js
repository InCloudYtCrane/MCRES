// mcres/static/js/pages/auth/forgot_password.js
const form = document.getElementById("resetForm");
  const newPwd = document.getElementById("newPwd");
  const confirmPwd = document.getElementById("confirmPwd");
  const errorMsg = document.getElementById("errorMsg");
  const successMsg = document.getElementById("successMsg");
  const sendBtn = document.getElementById("sendCodeBtn");
  const emailInput = document.getElementById("emailInput");
  const captchaInput = document.getElementById("captchaInput");
  const emailCodeInput = document.getElementById("emailCodeInput");

  function refreshCaptcha() {
    document.getElementById("captchaImg").src = "/captcha?" + Date.now();
  }

  sendBtn.addEventListener("click", function () {
    const email = emailInput.value.trim();
    const captcha = captchaInput.value.trim();

    if (!email) {
      errorMsg.innerHTML =
        '<i class="fas fa-exclamation-circle"></i> 请先填写邮箱';
      errorMsg.style.display = "block";
      successMsg.style.display = "none";
      return;
    }
    if (!captcha) {
      errorMsg.innerHTML =
        '<i class="fas fa-exclamation-circle"></i> 请先输入图形验证码';
      errorMsg.style.display = "block";
      successMsg.style.display = "none";
      return;
    }

    sendBtn.disabled = true;
    let seconds = 60;
    sendBtn.innerHTML = '<i class="fas fa-clock"></i> ' + seconds + "s";

    fetch("/send_reset_code", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body:
        "email=" +
        encodeURIComponent(email) +
        "&captcha=" +
        encodeURIComponent(captcha),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          errorMsg.style.display = "none";
          successMsg.innerHTML =
            '<i class="fas fa-check-circle"></i> ' + data.message;
          successMsg.style.display = "block";
          const timer = setInterval(() => {
            seconds--;
            sendBtn.innerHTML = '<i class="fas fa-clock"></i> ' + seconds + "s";
            if (seconds <= 0) {
              clearInterval(timer);
              sendBtn.disabled = false;
              sendBtn.innerHTML =
                '<i class="fas fa-paper-plane"></i> 发送验证码';
            }
          }, 1000);
        } else {
          errorMsg.innerHTML =
            '<i class="fas fa-exclamation-circle"></i> ' +
            (data.message || "发送失败，请重试");
          errorMsg.style.display = "block";
          successMsg.style.display = "none";
          sendBtn.disabled = false;
          sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i> 发送验证码';
          refreshCaptcha();
        }
      })
      .catch((err) => {
        errorMsg.innerHTML =
          '<i class="fas fa-exclamation-circle"></i> 请求失败，请检查网络';
        errorMsg.style.display = "block";
        successMsg.style.display = "none";
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i> 发送验证码';
      });
  });

  form.addEventListener("submit", function (e) {
    errorMsg.style.display = "none";
    successMsg.style.display = "none";

    if (newPwd.value.length < 8) {
      e.preventDefault();
      errorMsg.innerHTML =
        '<i class="fas fa-exclamation-circle"></i> 密码长度不能少于 8 位。';
      errorMsg.style.display = "block";
      return;
    }
    if (newPwd.value !== confirmPwd.value) {
      e.preventDefault();
      errorMsg.innerHTML =
        '<i class="fas fa-exclamation-circle"></i> 两次输入的密码不一致。';
      errorMsg.style.display = "block";
      return;
    }
    if (!emailCodeInput.value.trim()) {
      e.preventDefault();
      errorMsg.innerHTML =
        '<i class="fas fa-exclamation-circle"></i> 请输入邮箱验证码';
      errorMsg.style.display = "block";
      return;
    }
    if (!captchaInput.value.trim()) {
      e.preventDefault();
      errorMsg.innerHTML =
        '<i class="fas fa-exclamation-circle"></i> 请输入图形验证码';
      errorMsg.style.display = "block";
      return;
    }
  });

// ---------- 验证码刷新（替代内联 onclick） ----------
(function () {
  var img = document.getElementById("captchaImg");
  if (img) img.addEventListener("click", refreshCaptcha);
  var link = document.querySelector(".captcha-refresh a");
  if (link) link.addEventListener("click", function (e) { e.preventDefault(); refreshCaptcha(); });
})();
