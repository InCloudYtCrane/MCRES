// mcres/static/js/pages/profile/settings.js
// 账号设置页脚本。
// Toast 由 /static/js/components/toast.js 提供（base.html 已全局加载）。
(function () {
  "use strict";

  // ============================================================
  // 侧边栏切换
  // ============================================================
  var navLinks = document.querySelectorAll(".settings-nav a");
  var panels = {
    account: document.getElementById("panel-account"),
    notifications: document.getElementById("panel-notifications"),
    privacy: document.getElementById("panel-privacy"),
  };

  navLinks.forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      navLinks.forEach(function (l) {
        l.classList.remove("active");
      });
      this.classList.add("active");
      Object.values(panels).forEach(function (p) {
        if (p) p.classList.remove("active");
      });
      var tab = this.dataset.tab;
      if (panels[tab]) panels[tab].classList.add("active");
    });
  });

  // ============================================================
  // 开关点击切换
  // ============================================================
  document.querySelectorAll(".toggle-switch").forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      this.classList.toggle("active");
    });
  });

  // ============================================================
  // 通知设置
  // ============================================================
  var saveNotificationsBtn = document.getElementById("saveNotifications");
  if (saveNotificationsBtn) {
    saveNotificationsBtn.addEventListener("click", function (e) {
      e.preventDefault();
      var switches = document.querySelectorAll(
        "#panel-notifications .toggle-switch",
      );
      var settings = {};
      switches.forEach(function (toggle) {
        var key = toggle.dataset.setting;
        if (key) settings[key] = toggle.classList.contains("active");
      });

      fetch("/profile/settings/notifications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      })
        .then(function (resp) {
          return resp.json();
        })
        .then(function (data) {
          if (data.success) {
            Toast.show("通知设置已保存", "success");
          } else {
            Toast.show(data.message || "保存失败", "error");
          }
        })
        .catch(function () {
          Toast.show("网络错误，请重试", "error");
        });
    });
  }

  function loadNotificationSettings() {
    fetch("/profile/settings/notifications")
      .then(function (resp) {
        return resp.json();
      })
      .then(function (data) {
        if (data.success) {
          var settings = data.data;
          document
            .querySelectorAll("#panel-notifications .toggle-switch")
            .forEach(function (toggle) {
              var key = toggle.dataset.setting;
              if (key && settings.hasOwnProperty(key)) {
                toggle.classList.toggle("active", settings[key] !== false);
              }
            });
        }
      })
      .catch(function () {});
  }

  // ============================================================
  // 隐私设置
  // ============================================================
  var savePrivacyBtn = document.getElementById("savePrivacy");
  if (savePrivacyBtn) {
    savePrivacyBtn.addEventListener("click", function (e) {
      e.preventDefault();
      var switches = document.querySelectorAll("#panel-privacy .toggle-switch");
      var settings = {};
      switches.forEach(function (toggle) {
        var key = toggle.dataset.setting;
        if (key) settings[key] = toggle.classList.contains("active");
      });

      // 额外收集账号面板里的"允许多设备登录"开关
      var multiToggle = document.getElementById("multiDeviceToggle");
      if (multiToggle) {
        settings["allow_multi_device"] =
          multiToggle.classList.contains("active");
      }

      fetch("/profile/settings/privacy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      })
        .then(function (resp) {
          return resp.json();
        })
        .then(function (data) {
          if (data.success) {
            Toast.show("隐私设置已保存", "success");
          } else {
            Toast.show(data.message || "保存失败", "error");
          }
        })
        .catch(function () {
          Toast.show("网络错误，请重试", "error");
        });
    });
  }

  function loadPrivacySettings() {
    fetch("/profile/settings/privacy")
      .then(function (resp) {
        return resp.json();
      })
      .then(function (data) {
        if (data.success) {
          var settings = data.data;
          document
            .querySelectorAll("#panel-privacy .toggle-switch")
            .forEach(function (toggle) {
              var key = toggle.dataset.setting;
              if (key && settings.hasOwnProperty(key)) {
                toggle.classList.toggle("active", settings[key] !== false);
              }
            });

          // 同步账号面板里的"允许多设备登录"开关
          var multiToggle = document.getElementById("multiDeviceToggle");
          if (multiToggle && settings.hasOwnProperty("allow_multi_device")) {
            multiToggle.classList.toggle(
              "active",
              settings["allow_multi_device"] !== false,
            );
          }
        }
      })
      .catch(function () {});
  }

  // ============================================================
  // 页面加载时初始化
  // ============================================================
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      loadNotificationSettings();
      loadPrivacySettings();
    });
  } else {
    loadNotificationSettings();
    loadPrivacySettings();
  }

  // ============================================================
  // 账号设置：自动保存逻辑
  // ============================================================
  (function () {
    // ---- 头像上传 ----
    var avatarInput = document.getElementById("avatarFileInput");
    var avatarPreview = document.getElementById("previewAvatar");

    if (avatarInput) {
      avatarInput.addEventListener("change", function () {
        var file = this.files[0];
        if (!file) return;

        if (file.size > 5 * 1024 * 1024) {
          Toast.show("文件大小不能超过 5MB", "error");
          this.value = "";
          return;
        }
        var validTypes = ["image/jpeg", "image/png", "image/webp"];
        if (!validTypes.includes(file.type)) {
          Toast.show("仅支持 JPG、PNG、WebP 格式", "error");
          this.value = "";
          return;
        }

        var reader = new FileReader();
        reader.onload = function (ev) {
          avatarPreview.src = ev.target.result;
        };
        reader.readAsDataURL(file);

        var formData = new FormData();
        formData.append("avatar", file);

        var statusEl = document.getElementById("avatarStatus");
        if (statusEl) {
          statusEl.textContent = "上传中...";
          statusEl.className = "field-status saving";
        }

        fetch("/profile/settings/avatar", {
          method: "POST",
          body: formData,
        })
          .then(function (resp) {
            return resp.json();
          })
          .then(function (data) {
            if (data.success) {
              avatarPreview.src = data.avatar_url + "?t=" + Date.now();
              if (statusEl) {
                statusEl.textContent = "✅ 头像已更新";
                statusEl.className = "field-status saved";
              }
              Toast.show("头像更新成功", "success");
            } else {
              if (statusEl) {
                statusEl.textContent = "❌ " + data.message;
                statusEl.className = "field-status error";
              }
              Toast.show(data.message || "头像上传失败", "error");
            }
          })
          .catch(function () {
            if (statusEl) {
              statusEl.textContent = "❌ 网络错误，请重试";
              statusEl.className = "field-status error";
            }
            Toast.show("网络错误，请重试", "error");
          });
      });
    }

    // ---- 通用：失焦保存 ----
    function setupAutoSave(inputId, url, fieldName, validateFn) {
      var input = document.getElementById(inputId);
      if (!input) return;

      var statusEl = document.getElementById(inputId + "Status");

      input.addEventListener("blur", function () {
        var value = this.value.trim();
        if (fieldName === "signature") {
          // 允许空
        } else if (!value) {
          if (statusEl) {
            statusEl.textContent = "⚠️ 不能为空";
            statusEl.className = "field-status error";
          }
          return;
        }

        if (validateFn) {
          var valid = validateFn(value);
          if (valid !== true) {
            if (statusEl) {
              statusEl.textContent = "⚠️ " + valid;
              statusEl.className = "field-status error";
            }
            return;
          }
        }

        if (statusEl) {
          statusEl.textContent = "保存中...";
          statusEl.className = "field-status saving";
        }

        var body = {};
        body[fieldName] = value;

        fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        })
          .then(function (resp) {
            return resp.json();
          })
          .then(function (data) {
            if (data.success) {
              if (statusEl) {
                statusEl.textContent = "✅ 已保存";
                statusEl.className = "field-status saved";
              }
              setTimeout(function () {
                if (statusEl) {
                  statusEl.textContent = "";
                  statusEl.className = "field-status";
                }
              }, 2000);
            } else {
              if (statusEl) {
                statusEl.textContent = "❌ " + data.message;
                statusEl.className = "field-status error";
              }
              Toast.show(data.message || "保存失败", "error");
            }
          })
          .catch(function () {
            if (statusEl) {
              statusEl.textContent = "❌ 网络错误";
              statusEl.className = "field-status error";
            }
            Toast.show("网络错误，请重试", "error");
          });
      });

      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          this.blur();
        }
      });
    }

    // ---- 昵称 ----
    setupAutoSave(
      "nicknameInput",
      "/profile/settings/nickname",
      "nickname",
      function (value) {
        if (value.length < 2 || value.length > 20) {
          return "长度应在2-20个字符之间";
        }
        if (!/^[\u4e00-\u9fa5a-zA-Z0-9_]+$/.test(value)) {
          return "只能包含中文、英文、数字和下划线";
        }
        return true;
      },
    );

    // ---- 签名 ----
    setupAutoSave(
      "signatureInput",
      "/profile/settings/signature",
      "signature",
      function (value) {
        if (value.length > 80) {
          return "不能超过80个字符";
        }
        return true;
      },
    );

    // ---- 签名计数 ----
    var sigInput = document.getElementById("signatureInput");
    var sigHint = document.getElementById("signatureHint");
    if (sigInput && sigHint) {
      sigInput.addEventListener("input", function () {
        var len = this.value.length;
        sigHint.textContent = len + " / 80 字符";
      });
      sigInput.dispatchEvent(new Event("input"));
    }
  })();

  // ============================================================
  // 头衔管理
  // ============================================================
  (function () {
    var titleSelect = document.getElementById("titleSelect");
    var saveTitleBtn = document.getElementById("saveTitleBtn");
    var titleStatus = document.getElementById("titleStatus");
    var currentTitlePreview = document.getElementById("currentTitlePreview");

    if (!titleSelect) return;

    function loadTitles() {
      fetch("/profile/settings/titles")
        .then(function (resp) {
          return resp.json();
        })
        .then(function (data) {
          if (data.success) {
            var titles = data.data.list || [];
            var selected =
              data.data.selected !== undefined && data.data.selected !== null
                ? data.data.selected
                : -1;

            titleSelect.innerHTML = '<option value="-1">不佩戴</option>';
            titles.forEach(function (item, idx) {
              var opt = document.createElement("option");
              opt.value = idx;
              opt.textContent = item.text + " (" + item.color + ")";
              if (idx === selected) {
                opt.selected = true;
              }
              titleSelect.appendChild(opt);
            });

            updateTitlePreview(selected, titles);
          }
        })
        .catch(function () {});
    }

    function updateTitlePreview(index, titles) {
      if (!titles) {
        var allOptions = titleSelect.querySelectorAll("option");
        var selectedVal = parseInt(titleSelect.value, 10);
        var list = [];
        allOptions.forEach(function (opt, idx) {
          if (idx > 0) {
            var text = opt.textContent;
            var colorMatch = text.match(/\(([^)]+)\)$/);
            if (colorMatch) {
              list.push({
                text: text.replace(/\s*\([^)]+\)$/, ""),
                color: colorMatch[1],
              });
            }
          }
        });
        if (selectedVal >= 0 && selectedVal < list.length) {
          currentTitlePreview.textContent = list[selectedVal].text;
          currentTitlePreview.style.color = list[selectedVal].color;
          return;
        }
        currentTitlePreview.textContent = "无";
        currentTitlePreview.style.color = "#8a929a";
        return;
      }

      if (index >= 0 && index < titles.length) {
        currentTitlePreview.textContent = titles[index].text;
        currentTitlePreview.style.color = titles[index].color;
      } else {
        currentTitlePreview.textContent = "无";
        currentTitlePreview.style.color = "#8a929a";
      }
    }

    titleSelect.addEventListener("change", function () {
      var val = parseInt(this.value, 10);
      var allOptions = this.querySelectorAll("option");
      var list = [];
      allOptions.forEach(function (opt, idx) {
        if (idx > 0) {
          var text = opt.textContent;
          var colorMatch = text.match(/\(([^)]+)\)$/);
          if (colorMatch) {
            list.push({
              text: text.replace(/\s*\([^)]+\)$/, ""),
              color: colorMatch[1],
            });
          }
        }
      });
      updateTitlePreview(val, list);
    });

    if (saveTitleBtn) {
      saveTitleBtn.addEventListener("click", function (e) {
        e.preventDefault();
        var index = parseInt(titleSelect.value, 10);

        titleStatus.textContent = "保存中...";
        titleStatus.className = "field-status saving";

        fetch("/profile/settings/titles/select", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ index: index }),
        })
          .then(function (resp) {
            return resp.json();
          })
          .then(function (data) {
            if (data.success) {
              titleStatus.textContent = "✅ 头衔已更新";
              titleStatus.className = "field-status saved";
              loadTitles();
              Toast.show("头衔佩戴已更新", "success");
            } else {
              titleStatus.textContent = "❌ " + data.message;
              titleStatus.className = "field-status error";
            }
          })
          .catch(function () {
            titleStatus.textContent = "❌ 网络错误，请重试";
            titleStatus.className = "field-status error";
          });
      });
    }

    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", loadTitles);
    } else {
      loadTitles();
    }
  })();

  // ============================================================
  // 登录设备管理
  // ============================================================
  (function () {
    var deviceList = document.getElementById("deviceList");
    var refreshBtn = document.getElementById("refreshSessionsBtn");
    var multiToggle = document.getElementById("multiDeviceToggle");

    function deviceIcon(type) {
      if (type === "mobile") return "fa-mobile-alt";
      if (type === "tablet") return "fa-tablet-alt";
      return "fa-desktop";
    }

    function renderSessions(items) {
      if (!deviceList) return;
      if (!items || items.length === 0) {
        deviceList.innerHTML =
          '<div style="text-align:center; color:#6a7a8a; padding:20px; font-size:14px;">' +
          "暂无登录设备记录</div>";
        return;
      }

      var html = "";
      items.forEach(function (d) {
        var badge = d.is_current
          ? '<span style="display:inline-block;margin-left:8px;padding:1px 10px;font-size:11px;border-radius:10px;background:rgba(85,216,139,0.15);color:#55d88b;border:1px solid rgba(85,216,139,0.3);">当前设备</span>'
          : "";

        html +=
          '<div class="device-item" data-id="' +
          d.id +
          '" ' +
          'style="display:flex;align-items:center;gap:14px;padding:14px 16px;' +
          "background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);" +
          'border-radius:12px;transition:border-color 0.2s;">' +
          '<div style="flex-shrink:0;width:42px;height:42px;border-radius:10px;' +
          "background:rgba(85,216,139,0.10);color:#55d88b;" +
          'display:flex;align-items:center;justify-content:center;font-size:20px;">' +
          '<i class="fas ' +
          deviceIcon(d.device_type) +
          '"></i>' +
          "</div>" +
          '<div style="flex:1;min-width:0;">' +
          '<div style="font-size:15px;font-weight:600;color:#e8ecf0;' +
          'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' +
          d.device_name +
          badge +
          "</div>" +
          '<div style="font-size:13px;color:#8a929a;margin-top:2px;">' +
          '<i class="fas fa-map-marker-alt" style="opacity:0.6;"></i> ' +
          d.ip +
          "（" +
          d.ip_region +
          "）" +
          "</div>" +
          '<div style="font-size:12px;color:#6a7a8a;margin-top:2px;">' +
          "登录：" +
          d.login_time +
          " &nbsp;·&nbsp; 活跃：" +
          d.last_active +
          "</div>" +
          "</div>" +
          (d.is_current
            ? '<span style="font-size:12px;color:#4d5663;">本机</span>'
            : '<button class="btn-remove-session" data-id="' +
              d.id +
              '" ' +
              'style="flex-shrink:0;padding:6px 14px;border-radius:8px;' +
              "background:rgba(249,117,131,0.10);color:#f97583;" +
              "border:1px solid rgba(249,117,131,0.25);font-size:13px;" +
              'cursor:pointer;transition:all 0.2s;">' +
              '<i class="fas fa-sign-out-alt"></i> 退出</button>') +
          "</div>";
      });
      deviceList.innerHTML = html;

      deviceList
        .querySelectorAll(".btn-remove-session")
        .forEach(function (btn) {
          btn.addEventListener("click", function () {
            var sid = this.dataset.id;
            if (!confirm("确定要退出该设备的登录吗？")) return;

            var self = this;
            self.disabled = true;
            self.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

            fetch("/profile/settings/sessions/" + sid, {
              method: "DELETE",
            })
              .then(function (r) {
                return r.json();
              })
              .then(function (res) {
                if (res.success) {
                  Toast.show("该设备已被退出登录", "success");
                  loadSessions();
                } else {
                  alert(res.message || "操作失败");
                  self.disabled = false;
                  self.innerHTML = '<i class="fas fa-sign-out-alt"></i> 退出';
                }
              })
              .catch(function () {
                alert("网络错误，请重试");
                self.disabled = false;
                self.innerHTML = '<i class="fas fa-sign-out-alt"></i> 退出';
              });
          });
        });
    }

    function loadSessions() {
      if (!deviceList) return;
      deviceList.innerHTML =
        '<div style="text-align:center; color:#6a7a8a; padding:20px; font-size:14px;">' +
        '<i class="fas fa-spinner fa-spin"></i> 加载中…</div>';

      fetch("/profile/settings/sessions")
        .then(function (r) {
          return r.json();
        })
        .then(function (res) {
          if (res.success) {
            renderSessions(res.data);
          } else {
            deviceList.innerHTML =
              '<div style="color:#f97583;text-align:center;padding:20px;">加载失败</div>';
          }
        })
        .catch(function () {
          deviceList.innerHTML =
            '<div style="color:#f97583;text-align:center;padding:20px;">网络错误</div>';
        });
    }

    if (refreshBtn) refreshBtn.addEventListener("click", loadSessions);

    if (
      document.getElementById("panel-account") &&
      document.getElementById("panel-account").classList.contains("active")
    ) {
      loadSessions();
    }

    document.querySelectorAll(".settings-nav a").forEach(function (a) {
      a.addEventListener("click", function () {
        if (this.dataset.tab === "account") {
          setTimeout(loadSessions, 50);
        }
      });
    });

    // "允许多设备登录"开关：独立保存，改动后立即生效
    if (multiToggle) {
      multiToggle.addEventListener("click", function () {
        var self = this;
        setTimeout(function () {
          var newState = self.classList.contains("active");

          var settings = {};
          document
            .querySelectorAll("#panel-privacy .toggle-switch")
            .forEach(function (t) {
              var k = t.dataset.setting;
              if (k) settings[k] = t.classList.contains("active");
            });
          settings["allow_multi_device"] = newState;

          fetch("/profile/settings/privacy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings),
          })
            .then(function (r) {
              return r.json();
            })
            .then(function (res) {
              if (res.success) {
                Toast.show(
                  newState
                    ? "已开启多设备登录"
                    : "已关闭多设备登录，其他设备已被强制退出",
                  "success",
                );
                if (!newState) {
                  setTimeout(loadSessions, 300);
                }
              } else {
                self.classList.toggle("active", !newState);
                Toast.show(res.message || "保存失败", "error");
              }
            })
            .catch(function () {
              self.classList.toggle("active", !newState);
              Toast.show("网络错误，请重试", "error");
            });
        }, 20);
      });
    }
  })();
})();
