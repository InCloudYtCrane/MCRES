// mcres/static/js/pages/profile/settings/pwd.js
(function() {
      // ---------- Toast ----------
      function showToast(message, type) {
          type = type || 'info';
          var container = document.getElementById('toastContainer');
          var toast = document.createElement('div');
          toast.className = 'toast ' + type;
          var icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', info: 'fa-info-circle' };
          toast.innerHTML = '<i class="fas ' + (icons[type] || icons.info) + '"></i> ' + message;
          container.appendChild(toast);
          setTimeout(function() {
              toast.style.opacity = '0';
              toast.style.transition = 'opacity 0.3s';
              setTimeout(function() { toast.remove(); }, 300);
          }, 3000);
      }

      // ---------- 密码显示切换 ----------
      document.querySelectorAll('.toggle-password').forEach(function(btn) {
          btn.addEventListener('click', function() {
              var targetId = this.dataset.target;
              var input = document.getElementById(targetId);
              if (input) {
                  if (input.type === 'password') {
                      input.type = 'text';
                      this.innerHTML = '<i class="fas fa-eye-slash"></i>';
                  } else {
                      input.type = 'password';
                      this.innerHTML = '<i class="fas fa-eye"></i>';
                  }
              }
          });
      });

      // ---------- 元素引用 ----------
      var step1 = document.getElementById('step1');
      var step2 = document.getElementById('step2');
      var currentPwd = document.getElementById('currentPassword');
      var newPwd = document.getElementById('newPassword');
      var confirmPwd = document.getElementById('confirmPassword');
      var verifyBtn = document.getElementById('verifyBtn');
      var resetBtn = document.getElementById('resetBtn');
      var backBtn = document.getElementById('backBtn');
      var verifyError = document.getElementById('verifyError');
      var resetError = document.getElementById('resetError');
      var resetSuccess = document.getElementById('resetSuccess');
      var strengthBars = document.querySelectorAll('#strengthBars .bar');
      var strengthLabel = document.getElementById('strengthLabel');

      var verifyToken = null;

      // ---------- 密码强度检测 ----------
      function checkStrength(password) {
          if (!password) return { score: 0, label: '请输入新密码', level: '' };
          var score = 0;
          if (password.length >= 8) score++;
          if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
          if (/\d/.test(password)) score++;
          if (/[^a-zA-Z0-9]/.test(password)) score++;
          var levels = ['', '弱', '中', '强', '强'];
          var levelClasses = ['', 'weak', 'medium', 'strong', 'strong'];
          return { score: score, label: levels[score] || '强', level: levelClasses[score] || 'strong' };
      }

      newPwd.addEventListener('input', function() {
          var result = checkStrength(this.value);
          strengthBars.forEach(function(bar, index) {
              bar.className = 'bar';
              if (index < result.score) {
                  bar.classList.add(result.level);
              }
          });
          strengthLabel.textContent = result.label;
          strengthLabel.className = 'strength-label ' + result.level;
      });

      // ---------- 步骤切换 ----------
      function goToStep(step) {
          step1.classList.toggle('active', step === 1);
          step2.classList.toggle('active', step === 2);
      }

      // ---------- 验证当前密码 ----------
      verifyBtn.addEventListener('click', function() {
          var password = currentPwd.value.trim();
          if (!password) {
              verifyError.textContent = '请输入当前密码';
              verifyError.className = 'error-msg show';
              return;
          }

          verifyError.className = 'error-msg';
          verifyBtn.disabled = true;
          verifyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 验证中...';

          fetch('/profile/settings/pwd/verify', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ current_password: password })
          })
          .then(function(resp) { return resp.json(); })
          .then(function(data) {
              if (data.success) {
                  verifyToken = data.token;
                  goToStep(2);
                  newPwd.focus();
                  showToast('密码验证通过，请设置新密码', 'success');
              } else {
                  verifyError.textContent = data.message || '密码错误';
                  verifyError.className = 'error-msg show';
                  currentPwd.focus();
                  currentPwd.select();
              }
          })
          .catch(function(err) {
              verifyError.textContent = '网络错误，请重试';
              verifyError.className = 'error-msg show';
              showToast('网络错误，请重试', 'error');
          })
          .finally(function() {
              verifyBtn.disabled = false;
              verifyBtn.innerHTML = '<i class="fas fa-check"></i> 下一步';
          });
      });

      // 回车触发验证
      currentPwd.addEventListener('keydown', function(e) {
          if (e.key === 'Enter') {
              verifyBtn.click();
          }
      });

      // ---------- 返回上一步 ----------
      backBtn.addEventListener('click', function() {
          goToStep(1);
          currentPwd.focus();
          verifyToken = null;
          resetError.className = 'error-msg';
          resetSuccess.className = 'success-msg';
      });

      // ---------- 重置密码 ----------
      resetBtn.addEventListener('click', function() {
          var newPassword = newPwd.value.trim();
          var confirmPassword = confirmPwd.value.trim();

          resetError.className = 'error-msg';
          resetSuccess.className = 'success-msg';

          if (!newPassword || newPassword.length < 8) {
              resetError.textContent = '密码长度不能少于8位';
              resetError.className = 'error-msg show';
              newPwd.focus();
              return;
          }
          if (newPassword !== confirmPassword) {
              resetError.textContent = '两次输入的密码不一致';
              resetError.className = 'error-msg show';
              confirmPwd.focus();
              return;
          }
          if (!verifyToken) {
              resetError.textContent = '验证已过期，请重新验证当前密码';
              resetError.className = 'error-msg show';
              goToStep(1);
              return;
          }

          resetBtn.disabled = true;
          resetBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 提交中...';

          fetch('/profile/settings/pwd/reset', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                  token: verifyToken,
                  new_password: newPassword,
                  confirm_password: confirmPassword
              })
          })
          .then(function(resp) { return resp.json(); })
          .then(function(data) {
              if (data.success) {
                  resetSuccess.textContent = '✅ ' + data.message + '，请重新登录';
                  resetSuccess.className = 'success-msg show';
                  showToast('密码修改成功，请重新登录', 'success');
                  // 3秒后跳转到登录页
                  setTimeout(function() {
                      window.location.href = '/login';
                  }, 3000);
              } else {
                  resetError.textContent = data.message || '重置失败';
                  resetError.className = 'error-msg show';
                  if (data.message && data.message.includes('验证')) {
                      goToStep(1);
                      verifyToken = null;
                  }
              }
          })
          .catch(function(err) {
              resetError.textContent = '网络错误，请重试';
              resetError.className = 'error-msg show';
              showToast('网络错误，请重试', 'error');
          })
          .finally(function() {
              resetBtn.disabled = false;
              resetBtn.innerHTML = '<i class="fas fa-save"></i> 确认重置';
          });
      });

      // 回车触发重置
      confirmPwd.addEventListener('keydown', function(e) {
          if (e.key === 'Enter') {
              resetBtn.click();
          }
      });

      // ---------- flash 消息（后端注入，见模板） ----------
      (window.PWD_FLASH || []).forEach(function (f) {
          setTimeout(function () { showToast(f.message, f.category); }, 500);
      });
  })();
