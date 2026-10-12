// mcres/static/js/pages/auth-register.js
// 注册页脚本：三步注册流程（邮箱+图形验证码 → 邮箱验证码 → 昵称/密码/协议）。
(function () {
  "use strict";

  const step1 = document.getElementById("step1");
  const step2 = document.getElementById("step2");
  const step3 = document.getElementById("step3");
  const dot1 = document.getElementById("stepDot1");
  const dot2 = document.getElementById("stepDot2");
  const dot3 = document.getElementById("stepDot3");
  const emailInput = document.getElementById("emailInput");
  const captchaInput = document.getElementById("captchaInput");
  const captchaImg = document.getElementById("captchaImg");
  const nextBtn = document.getElementById("nextStep1Btn");
  const emailCodeInput = document.getElementById("emailCodeInput");
  const verifyBtn = document.getElementById("verifyCodeBtn");
  const resendLink = document.getElementById("resendCodeLink");
  const resendTimer = document.getElementById("resendTimer");
  const hiddenEmail = document.getElementById("hiddenEmail");
  const registerForm = document.getElementById("registerForm");
  const pwd = document.getElementById("pwd");
  const confirmPwd = document.getElementById("confirmPwd");
  const agreeCheck = document.getElementById("agreeCheck");
  const generalError = document.getElementById("generalError");
  const nicknameInput = document.getElementById("nicknameInput");

  let currentStep = 1;
  let email = "";
  let captcha = "";

  function showError(msg) {
    generalError.innerText = msg;
    generalError.style.display = "block";
    generalError.style.color = "#ff6b6b";
  }

  function hideError() {
    generalError.style.display = "none";
  }

  function goToStep(step) {
    currentStep = step;
    step1.style.display = step === 1 ? "block" : "none";
    step2.style.display = step === 2 ? "block" : "none";
    step3.style.display = step === 3 ? "block" : "none";
    [dot1, dot2, dot3].forEach((dot, idx) => {
      dot.className = "";
      if (idx + 1 === step) dot.classList.add("active");
      else if (idx + 1 < step) dot.classList.add("done");
    });
    hideError();
  }

  function refreshCaptcha() {
    captchaImg.src = "/captcha?" + Date.now();
  }

  nextBtn.addEventListener("click", function () {
    email = emailInput.value.trim();
    captcha = captchaInput.value.trim();

    if (!email) {
      showError("请填写邮箱");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showError("邮箱格式不正确");
      return;
    }
    if (!captcha) {
      showError("请输入图形验证码");
      return;
    }

    nextBtn.disabled = true;
    nextBtn.innerText = "发送中...";
    hideError();

    fetch("/send_email_code", {
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
          hiddenEmail.value = email;
          goToStep(2);
          emailCodeInput.value = "";
          startResendCountdown(60);
        } else {
          showError(data.message || "发送失败，请重试");
          refreshCaptcha();
        }
      })
      .catch((err) => {
        showError("网络错误，请检查连接");
        refreshCaptcha();
      })
      .finally(() => {
        nextBtn.disabled = false;
        nextBtn.innerText = "下一步";
      });
  });

  verifyBtn.addEventListener("click", function () {
    const code = emailCodeInput.value.trim();
    if (!code) {
      showError("请输入邮箱验证码");
      return;
    }

    verifyBtn.disabled = true;
    verifyBtn.innerText = "验证中...";
    hideError();

    fetch("/verify_email_code", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body:
        "email=" +
        encodeURIComponent(email) +
        "&email_code=" +
        encodeURIComponent(code),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          goToStep(3);
        } else {
          showError(data.message || "验证失败，请重试");
        }
      })
      .catch((err) => {
        showError("网络错误，请重试");
      })
      .finally(() => {
        verifyBtn.disabled = false;
        verifyBtn.innerText = "验证";
      });
  });

  let countdownInterval = null;

  function startResendCountdown(seconds) {
    resendLink.style.pointerEvents = "none";
    resendLink.style.color = "#9ba5af";
    resendTimer.innerText = seconds + "s";

    if (countdownInterval) clearInterval(countdownInterval);

    countdownInterval = setInterval(() => {
      seconds--;
      if (seconds <= 0) {
        clearInterval(countdownInterval);
        countdownInterval = null;
        resendLink.style.pointerEvents = "auto";
        resendLink.style.color = "#55d88b";
        resendTimer.innerText = "";
      } else {
        resendTimer.innerText = seconds + "s";
      }
    }, 1000);
  }

  resendLink.addEventListener("click", function () {
    if (countdownInterval) {
      showError("请等待倒计时结束再重新发送");
      return;
    }

    hideError();
    resendLink.style.pointerEvents = "none";
    resendLink.innerText = "发送中...";

    fetch("/send_email_code", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "email=" + encodeURIComponent(email),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          startResendCountdown(60);
          emailCodeInput.value = "";
          generalError.style.color = "#55d88b";
          generalError.innerText = "验证码已重新发送至您的邮箱";
          generalError.style.display = "block";
          setTimeout(() => {
            generalError.style.color = "#ff6b6b";
            generalError.style.display = "none";
          }, 3000);
        } else {
          showError(data.message || "重新发送失败，请重试");
          if (data.message && data.message.includes("图形验证码")) {
            showError("验证码已过期，请返回第一步重新获取图形验证码");
          }
        }
      })
      .catch((err) => {
        showError("网络错误，请重试");
      })
      .finally(() => {
        resendLink.style.pointerEvents = "auto";
        resendLink.innerText = "重新发送验证码";
      });
  });

  registerForm.addEventListener("submit", function (e) {
    hideError();

    const nick = nicknameInput.value.trim();
    if (nick.length < 2 || nick.length > 20) {
      e.preventDefault();
      showError("昵称长度应在 2 到 20 个字符之间");
      return;
    }
    if (!/^[\u4e00-\u9fa5a-zA-Z0-9_]+$/.test(nick)) {
      e.preventDefault();
      showError("昵称只能包含中文、英文、数字和下划线");
      return;
    }
    if (pwd.value.length < 8) {
      e.preventDefault();
      showError("密码长度不能少于 8 位。");
      return;
    }
    if (pwd.value !== confirmPwd.value) {
      e.preventDefault();
      showError("两次输入的密码不一致。");
      return;
    }
    if (!agreeCheck.checked) {
      e.preventDefault();
      showError("请先阅读并同意用户协议和隐私政策");
      return;
    }
  });

  goToStep(1);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && currentStep === 1) {
      e.preventDefault();
      nextBtn.click();
    }
  });
  // ---------- 验证码刷新（替代内联 onclick） ----------
  captchaImg.addEventListener("click", refreshCaptcha);
  var _captchaLink = document.querySelector(".captcha-refresh a");
  if (_captchaLink) _captchaLink.addEventListener("click", function (e) { e.preventDefault(); refreshCaptcha(); });
})();
