// mcres/static/js/pages/resource/edit-page.js
// 三个资源编辑页（resourcepack / shaderpack / map）的公共逻辑。
// 目前包含：防撞车检测。
(function (global) {
  "use strict";

  var FIELD_LABEL_MAP = {
    main_name: "主要名称",
    curseforge_id: "CurseForge ID",
    modrinth_id: "Modrinth ID",
    mcmod_id: "MC百科 ID",
  };

  /**
   * 初始化防撞车检测。
   *
   * @param {Object} config
   * @param {string} config.type          - 'resourcepack' | 'shaderpack' | 'map'
   * @param {string} config.resourceName  - 提示文案里用的名词，如 '资源包' / '光影包' / '地图'
   * @param {string} config.urlPrefix     - 详情页 URL 前缀，如 '/resourcepack' / '/shaderpack' / '/map'
   * @returns {Object} { checkDuplicate, performDuplicateCheck, cache }
   */
  function initDuplicateCheck(config) {
    var type = config.type;
    var resourceName = config.resourceName;
    var urlPrefix = config.urlPrefix;

    var mainNameInput = document.getElementById("main_name");
    var curseforgeInput = document.getElementById("curseforge_id");
    var modrinthInput = document.getElementById("modrinth_id");
    var mcmodInput = document.getElementById("mcmod_id");

    var mainHint = document.getElementById("mainNameDuplicateHint");
    var curseHint = document.getElementById("curseforgeIdDuplicateHint");
    var modrinthHint = document.getElementById("modrinthIdDuplicateHint");
    var mcmodHint = document.getElementById("mcmodIdDuplicateHint");

    var cache = {};

    /**
     * 单个字段的防撞车检测。
     * 命中时给 hintElement 加上 warning/success 类名，并返回结果。
     */
    async function checkDuplicate(field, value, hintElement) {
      if (!hintElement) return null;

      if (!value || value.trim() === "") {
        hintElement.className = "duplicate-hint";
        hintElement.textContent = "";
        return null;
      }

      try {
        var resp = await fetch(
          "/api/check_duplicate?type=" +
            encodeURIComponent(type) +
            "&field=" +
            encodeURIComponent(field) +
            "&value=" +
            encodeURIComponent(value.trim()),
        );
        var data = await resp.json();
        var fieldLabel = FIELD_LABEL_MAP[field] || field;

        if (data.exists && data.ids && data.ids.length > 0) {
          var ids = data.ids
            .map(function (id) {
              return (
                '<a href="' +
                urlPrefix +
                "/" +
                id +
                '" target="_blank">#' +
                id +
                "</a>"
              );
            })
            .join("、");
          hintElement.className = "duplicate-hint warning";
          hintElement.innerHTML =
            "⚠️ 注意：相同" +
            fieldLabel +
            "的" +
            resourceName +
            "已被主站收录，" +
            resourceName +
            "id：" +
            ids +
            "，请您核实相关资源，以免重复提交。";
          return { exists: true, ids: data.ids };
        } else {
          hintElement.className = "duplicate-hint success";
          hintElement.textContent = "✅ 该" + fieldLabel + "未被使用";
          return { exists: false, ids: [] };
        }
      } catch (e) {
        hintElement.className = "duplicate-hint";
        hintElement.textContent = "";
        return null;
      }
    }

    function bindBlur(input, field, hint) {
      if (!input) return;
      input.addEventListener("blur", function () {
        checkDuplicate(field, this.value, hint).then(function (result) {
          if (result) cache[field] = result;
        });
      });
    }

    bindBlur(mainNameInput, "main_name", mainHint);
    bindBlur(curseforgeInput, "curseforge_id", curseHint);
    bindBlur(modrinthInput, "modrinth_id", modrinthHint);
    bindBlur(mcmodInput, "mcmod_id", mcmodHint);

    /**
     * 提交前批量检测，返回结果供提交模态框展示警告。
     * @returns {Promise<Object|null>} { hitCount, hitFields, lockSeconds } 或 null
     */
    async function performDuplicateCheck(
      mainName,
      curseforgeId,
      modrinthId,
      mcmodId,
    ) {
      var checks = await Promise.all([
        checkDuplicate("main_name", mainName, mainHint),
        checkDuplicate("curseforge_id", curseforgeId, curseHint),
        checkDuplicate("modrinth_id", modrinthId, modrinthHint),
        checkDuplicate("mcmod_id", mcmodId, mcmodHint),
      ]);

      var hitCount = checks.filter(function (c) {
        return c && c.exists;
      }).length;
      var hitFields = checks
        .map(function (c, i) {
          if (!c || !c.exists) return null;
          return ["主要名称", "CurseForge ID", "Modrinth ID", "MC百科 ID"][i];
        })
        .filter(Boolean);

      var lockSeconds = 0;
      if (hitCount === 2) lockSeconds = 3;
      else if (hitCount >= 3) lockSeconds = 10;

      return {
        hitCount: hitCount,
        hitFields: hitFields,
        lockSeconds: lockSeconds,
      };
    }

    return {
      checkDuplicate: checkDuplicate,
      performDuplicateCheck: performDuplicateCheck,
      cache: cache,
    };
  }

  global.EditPage = {
    initDuplicateCheck: initDuplicateCheck,
  };
})(window);
