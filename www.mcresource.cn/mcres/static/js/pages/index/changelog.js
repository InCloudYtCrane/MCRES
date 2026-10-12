// mcres/static/js/pages/changelog.js
// 更新日志页：顶部信息条、里程碑滚动、日历、更新流、弹出框、折叠、返回顶部。
(function () {
  "use strict";

  var PROJECT_START = new Date(2026, 5, 28);
  var MONTH_NAMES_CN = [
    "一月",
    "二月",
    "三月",
    "四月",
    "五月",
    "六月",
    "七月",
    "八月",
    "九月",
    "十月",
    "十一月",
    "十二月",
  ];
  var WEEKDAYS_CN = ["日", "一", "二", "三", "四", "五", "六"];
  var WEEKDAYS_FULL = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  var COLOR_MAX = 14;

  // ========== 读取数据 ==========
  var rawData = {};
  try {
    var jsonEl = document.getElementById("changelogData");
    rawData = JSON.parse(jsonEl.textContent) || {};
  } catch (e) {
    console.error("changelogData 解析失败:", e);
  }
  var config = rawData.config || [];
  var content = rawData.content || [];

  // ========== 顶部信息条 ==========
  (function initTopInfo() {
    var now = new Date();
    var todayStr =
      now.getFullYear() +
      "年" +
      String(now.getMonth() + 1).padStart(2, "0") +
      "月" +
      String(now.getDate()).padStart(2, "0") +
      "日";
    var el = document.getElementById("todayDate");
    if (el) el.textContent = todayStr;

    var t = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var diff = Math.floor((t - PROJECT_START) / (24 * 60 * 60 * 1000));
    if (diff < 0) diff = 0;
    var daysEl = document.getElementById("daysSince");
    if (daysEl) daysEl.textContent = diff;
  })();

  // ========== 里程碑滚动 ==========
  (function initMilestoneMarquee() {
    var track = document.getElementById("milestoneTrack");
    var scroller = document.getElementById("milestoneScroller");
    if (!track || !scroller) return;
    requestAnimationFrame(function () {
      if (track.scrollWidth > scroller.clientWidth) {
        track.innerHTML += track.innerHTML;
        track.classList.add("scrolling");
        var duration = track.scrollWidth / 2 / 60;
        if (duration < 15) duration = 15;
        track.style.animationDuration = duration.toFixed(2) + "s";
      }
    });
  })();

  // ========== 数据解析 ==========
  function parseDateCN(str) {
    if (!str) return null;
    var m = String(str).match(/(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日/);
    if (!m) return null;
    return (
      m[1] +
      "-" +
      String(m[2]).padStart(2, "0") +
      "-" +
      String(m[3]).padStart(2, "0")
    );
  }

  var dateMap = {};
  var yearSet = {};
  var allDates = [];

  content.forEach(function (entry) {
    var dateKey = parseDateCN(entry.date);
    if (!dateKey) return;
    var items = [];
    var total = 0;
    config.forEach(function (cat) {
      var lines = (entry.detail || {})[cat.key];
      if (lines && lines.length) {
        items.push({
          key: cat.key,
          name: cat.name,
          color: cat.color,
          lines: lines,
        });
        total += lines.length;
      }
    });
    if (items.length) {
      dateMap[dateKey] = { items: items, total: total };
      yearSet[dateKey.slice(0, 4)] = true;
      allDates.push(dateKey);
    }
  });

  allDates.sort(function (a, b) {
    return b.localeCompare(a);
  });

  // ========== 颜色计算 ==========
  function getCellColor(count) {
    if (!count || count <= 0) return null;
    var capped = Math.min(count, COLOR_MAX);
    var t = (capped - 1) / (COLOR_MAX - 1);
    var hue = 120 + t * 240;
    var sat = Math.round(60 + t * 25);
    var lig = Math.round(35 + t * 35);
    return {
      bg: "hsl(" + hue + ", " + sat + "%, " + lig + "%)",
      fg: lig > 55 ? "rgba(15,20,26,0.9)" : "rgba(255,255,255,0.9)",
    };
  }

  // ========== 工具 ==========
  function escapeHtml(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ============================================================
  //  日历渲染
  // ============================================================
  function renderCalendar() {
    var container = document.getElementById("calendarContainer");
    var badge = document.getElementById("calendarBadge");
    if (!container) return;

    var nowYear = new Date().getFullYear();
    var years = Object.keys(yearSet).map(Number);
    if (years.indexOf(nowYear) === -1) years.push(nowYear);
    if (years.length === 0) years = [nowYear];
    years.sort(function (a, b) {
      return b - a;
    });

    var todayKey = (function () {
      var n = new Date();
      return (
        n.getFullYear() +
        "-" +
        String(n.getMonth() + 1).padStart(2, "0") +
        "-" +
        String(n.getDate()).padStart(2, "0")
      );
    })();

    var html = "";
    years.forEach(function (year) {
      var yearTotal = 0;
      Object.keys(dateMap).forEach(function (k) {
        if (k.slice(0, 4) === String(year)) yearTotal++;
      });
      html +=
        '<h2 class="calendar-year-title">' +
        year +
        " 年" +
        '<span class="year-badge">' +
        yearTotal +
        " 天有更新</span>" +
        "</h2>";
      html += '<div class="months-grid">';
      for (var m = 0; m < 12; m++) {
        html += renderMonthCard(year, m, todayKey);
      }
      html += "</div>";
    });
    container.innerHTML = html;

    if (badge) {
      badge.textContent = Object.keys(dateMap).length + " 天有更新";
    }

    container.querySelectorAll(".day-cell[data-date]").forEach(function (cell) {
      var key = cell.dataset.date;
      if (!dateMap[key]) return;

      cell.addEventListener("mouseenter", function (e) {
        if (isPinned) return;
        showPopup(e, key);
      });
      cell.addEventListener("mousemove", function (e) {
        if (isPinned) return;
        positionPopup(e);
      });
      cell.addEventListener("mouseleave", function () {
        hidePopup();
      });
      cell.addEventListener("click", function (e) {
        e.stopPropagation();
        if (isPinned && pinnedDate === key) {
          unpinPopup();
        } else if (isPinned) {
          fillPopupContent(key);
          pinPopup(key, cell);
        } else {
          fillPopupContent(key);
          popupEl.classList.add("visible");
          pinPopup(key, cell);
        }
      });
    });
  }

  function renderMonthCard(year, monthIdx, todayKey) {
    var firstDay = new Date(year, monthIdx, 1);
    var daysInMonth = new Date(year, monthIdx + 1, 0).getDate();
    var startWeekday = firstDay.getDay();

    var monthPrefix = year + "-" + String(monthIdx + 1).padStart(2, "0");
    var monthUpdateDays = 0;
    Object.keys(dateMap).forEach(function (k) {
      if (k.slice(0, 7) === monthPrefix) monthUpdateDays++;
    });

    var html = '<div class="month-card">';
    html +=
      '<div class="month-title">' +
      MONTH_NAMES_CN[monthIdx] +
      '<span class="m-count' +
      (monthUpdateDays === 0 ? " empty" : "") +
      '">' +
      (monthUpdateDays === 0 ? "—" : monthUpdateDays + "天") +
      "</span>" +
      "</div>";

    html += '<div class="month-weekdays">';
    WEEKDAYS_CN.forEach(function (w) {
      html += "<span>" + w + "</span>";
    });
    html += "</div>";

    html += '<div class="month-days">';
    for (var e = 0; e < startWeekday; e++) {
      html += '<div class="day-cell empty"></div>';
    }
    for (var d = 1; d <= daysInMonth; d++) {
      var dateKey =
        year +
        "-" +
        String(monthIdx + 1).padStart(2, "0") +
        "-" +
        String(d).padStart(2, "0");
      var entry = dateMap[dateKey];
      var cls = "day-cell";
      var styleStr = "";

      if (entry) {
        cls += " has-data";
        var c = getCellColor(entry.total);
        if (c) styleStr = "background:" + c.bg + ";color:" + c.fg + ";";
      }
      if (dateKey === todayKey) cls += " today";

      html +=
        '<div class="' +
        cls +
        '" ' +
        (styleStr ? 'style="' + styleStr + '" ' : "") +
        'data-date="' +
        dateKey +
        '">' +
        d +
        "</div>";
    }
    var remainder = (startWeekday + daysInMonth) % 7;
    if (remainder > 0) {
      for (var f = 0; f < 7 - remainder; f++) {
        html += '<div class="day-cell empty"></div>';
      }
    }
    html += "</div></div>";
    return html;
  }

  // ============================================================
  //  更新流渲染（★ 显示全部，不再限制天数）
  // ============================================================
  function renderStream() {
    var container = document.getElementById("streamList");
    var badge = document.getElementById("streamBadge");
    if (!container) return;

    if (allDates.length === 0) {
      container.innerHTML =
        '<div style="padding:40px;text-align:center;color:var(--text-muted);">暂无更新记录</div>';
      if (badge) badge.textContent = "0 天";
      return;
    }

    // 直接渲染全部日期，不做 slice
    var html = "";

    allDates.forEach(function (dateKey) {
      var entry = dateMap[dateKey];
      var parts = dateKey.split("-");
      var dt = new Date(
        parseInt(parts[0]),
        parseInt(parts[1]) - 1,
        parseInt(parts[2]),
      );

      html += '<div class="stream-item">';
      html += '  <div class="stream-date">';
      html += '    <span class="d-day">' + parts[2] + "</span>";
      html += '    <span class="d-ym">' + parts[0] + "." + parts[1] + "</span>";
      html +=
        '    <span class="d-week">' + WEEKDAYS_FULL[dt.getDay()] + "</span>";
      html += "  </div>";
      html += '  <div class="stream-content">';
      entry.items.forEach(function (cat) {
        var color = cat.color || "#6a8a9a";
        html +=
          '<div class="stream-cat" style="--cat-color:' +
          escapeHtml(color) +
          ";--cat-color-15:" +
          escapeHtml(color) +
          "26;" +
          ";--cat-color-30:" +
          escapeHtml(color) +
          '30;">';
        html +=
          '<span class="stream-cat-name">' + escapeHtml(cat.name) + "</span>";
        html += "<ul>";
        cat.lines.forEach(function (line) {
          html += "<li>" + escapeHtml(line) + "</li>";
        });
        html += "</ul></div>";
      });
      html += "  </div>";
      html += "</div>";
    });

    container.innerHTML = html;

    if (badge) {
      badge.textContent = "共 " + allDates.length + " 天";
    }
  }

  // ============================================================
  //  弹出框
  // ============================================================
  var popupEl = document.getElementById("detailPopup");
  var popupDateEl = document.getElementById("popupDate");
  var popupCountEl = document.getElementById("popupCount");
  var popupBodyEl = document.getElementById("popupBody");
  var popupCloseBtn = document.getElementById("popupClose");

  var isPinned = false;
  var pinnedDate = null;
  var pinnedAnchorEl = null;

  function buildPopupHTML(entry) {
    var html = "";
    entry.items.forEach(function (cat) {
      var color = cat.color || "#6a8a9a";
      html +=
        '<div class="popup-cat" style="--cat-color:' +
        escapeHtml(color) +
        ";--cat-color-15:" +
        escapeHtml(color) +
        "26;" +
        "--cat-color-30:" +
        escapeHtml(color) +
        '30;">';
      html +=
        '<span class="popup-cat-name">' + escapeHtml(cat.name) + "</span>";
      html += "<ul>";
      cat.lines.forEach(function (line) {
        html += "<li>" + escapeHtml(line) + "</li>";
      });
      html += "</ul></div>";
    });
    return html;
  }

  function fillPopupContent(dateKey) {
    var entry = dateMap[dateKey];
    if (!entry) return;
    var parts = dateKey.split("-");
    popupDateEl.textContent =
      parts[0] + "年" + parts[1] + "月" + parts[2] + "日";
    popupCountEl.textContent = entry.total + " 项更新";
    popupBodyEl.innerHTML = buildPopupHTML(entry);
    popupBodyEl.scrollTop = 0;
  }

  function showPopup(e, dateKey) {
    fillPopupContent(dateKey);
    popupEl.classList.add("visible");
    positionPopup(e);
  }

  function pinPopup(dateKey, anchorEl) {
    isPinned = true;
    pinnedDate = dateKey;
    pinnedAnchorEl = anchorEl;
    popupEl.classList.add("pinned");
    var rect = anchorEl.getBoundingClientRect();
    positionPopup({ clientX: rect.right, clientY: rect.top });
    document.querySelectorAll(".day-cell.pinned-day").forEach(function (el) {
      el.classList.remove("pinned-day");
    });
    anchorEl.classList.add("pinned-day");
  }

  function unpinPopup() {
    isPinned = false;
    pinnedDate = null;
    pinnedAnchorEl = null;
    popupEl.classList.remove("pinned");
    popupEl.classList.remove("visible");
    document.querySelectorAll(".day-cell.pinned-day").forEach(function (el) {
      el.classList.remove("pinned-day");
    });
  }

  function hidePopup() {
    if (isPinned) return;
    popupEl.classList.remove("visible");
  }

  function positionPopup(e) {
    if (!popupEl) return;
    var pw = popupEl.offsetWidth;
    var ph = popupEl.offsetHeight;
    var x = e.clientX + 16;
    var y = e.clientY + 16;
    if (x + pw > window.innerWidth - 10) x = e.clientX - pw - 16;
    if (y + ph > window.innerHeight - 10) y = window.innerHeight - ph - 10;
    if (x < 10) x = 10;
    if (y < 10) y = 10;
    popupEl.style.left = x + "px";
    popupEl.style.top = y + "px";
  }

  if (popupCloseBtn) {
    popupCloseBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      unpinPopup();
    });
  }

  document.addEventListener("click", function (e) {
    if (!isPinned) return;
    if (popupEl.contains(e.target)) return;
    if (pinnedAnchorEl && pinnedAnchorEl.contains(e.target)) return;
    var cell = e.target.closest && e.target.closest(".day-cell[data-date]");
    if (cell && dateMap[cell.dataset.date]) return;
    unpinPopup();
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && isPinned) unpinPopup();
  });

  // ============================================================
  //  日历折叠
  // ============================================================
  (function initCalendarToggle() {
    var section = document.getElementById("calendarSection");
    var toggle = document.getElementById("calendarToggle");
    if (!section || !toggle) return;
    toggle.addEventListener("click", function () {
      section.classList.toggle("open");
    });
  })();

  // ============================================================
  //  返回顶部
  // ============================================================
  (function initBackToTop() {
    var btn = document.getElementById("backToTop");
    if (!btn) return;
    window.addEventListener("scroll", function () {
      var y = window.scrollY || document.documentElement.scrollTop;
      btn.classList.toggle("visible", y > 300);
    });
    btn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  })();

  // ============================================================
  //  启动
  // ============================================================
  renderCalendar();
  renderStream();
})();
