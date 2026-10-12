// mcres/static/js/pages/rule.js
// 站内规则页：加载版本列表 + 切换版本时 AJAX 更新内容。
(function () {
  "use strict";

  var ruleKey = window.RULE_KEY;
  if (!ruleKey) return; // 无当前规则时不初始化

  var versionSelect = document.getElementById("versionSelect");
  var versionInfo = document.getElementById("versionInfo");
  var ruleTitle = document.getElementById("ruleTitle");
  var ruleBody = document.getElementById("ruleBody");
  var updateTime = document.getElementById("updateTime");

  if (!versionSelect) return;

  var versionsData = [];
  var currentVersion = null;
  var activeVersion = null;

  function loadVersions() {
    fetch("/rule/" + ruleKey + "/versions")
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (!data.length) {
          versionSelect.innerHTML = '<option value="">无历史版本</option>';
          versionInfo.textContent = "";
          return;
        }
        versionsData = data;

        var html = "";
        var foundActive = false;
        data.forEach(function (v) {
          var isActive = v.is_active;
          var label =
            "v" +
            v.version +
            " " +
            (isActive ? "● 当前" : "") +
            " " +
            (v.updated_at || "");
          html +=
            '<option value="' +
            v.version +
            '"' +
            (isActive ? " selected" : "") +
            ">" +
            label +
            "</option>";
          if (isActive) {
            foundActive = true;
            activeVersion = v.version;
          }
        });
        versionSelect.innerHTML = html;
        versionInfo.textContent = "共 " + data.length + " 个版本";

        if (foundActive) {
          currentVersion = activeVersion;
        }
      })
      .catch(function () {
        versionSelect.innerHTML = '<option value="">加载失败</option>';
        versionInfo.textContent = "";
      });
  }

  function loadVersion(version) {
    fetch("/rule/" + ruleKey + "/version/" + version)
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data.error) {
          alert("加载版本失败：" + data.error);
          return;
        }
        if (ruleTitle) ruleTitle.textContent = data.title;
        if (ruleBody) ruleBody.innerHTML = data.content;
        var vInfo = versionsData.filter(function (v) {
          return v.version === version;
        })[0];
        if (vInfo && updateTime) {
          updateTime.textContent = vInfo.updated_at || "未知";
        }
        currentVersion = version;
        versionSelect.value = version;
      })
      .catch(function () {
        alert("网络错误，请重试");
      });
  }

  versionSelect.addEventListener("change", function () {
    var version = parseInt(this.value);
    if (isNaN(version) || version === currentVersion) return;
    loadVersion(version);
  });

  loadVersions();
})();
