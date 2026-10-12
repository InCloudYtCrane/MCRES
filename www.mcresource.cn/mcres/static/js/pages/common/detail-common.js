/**
 * MCRES 详情页公共脚本
 * 功能：图片灯箱、B站视频弹窗、分享（复制链接/生成海报）、PV趋势图
 *
 * Toast 由 /static/js/components/toast.js 提供（base.html 已全局加载）。
 * 本文件不再重复定义 showToast。
 */

// ============================================================
// 分享下拉菜单控制（点击切换）
// ============================================================
function toggleShareDropdown(event) {
  event.stopPropagation();
  const menu = document.getElementById("shareDropdownMenu");
  if (!menu) return;
  menu.classList.toggle("open");
}

// 点击页面其他地方关闭下拉菜单
document.addEventListener("click", function () {
  const menu = document.getElementById("shareDropdownMenu");
  if (menu) menu.classList.remove("open");
});

// 阻止下拉菜单内部点击冒泡到 document
document.addEventListener("DOMContentLoaded", function () {
  const menu = document.getElementById("shareDropdownMenu");
  if (menu) {
    menu.addEventListener("click", function (e) {
      e.stopPropagation();
    });
  }
});

// ============================================================
// 图片灯箱
// ============================================================
function openLightbox(src) {
  const overlay = document.createElement("div");
  overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.85); z-index: 10000;
        display: flex; align-items: center; justify-content: center;
        cursor: pointer; padding: 40px; backdrop-filter: blur(4px);
        animation: fadeIn 0.25s ease;
    `;
  overlay.onclick = function () {
    this.remove();
  };

  const img = document.createElement("img");
  img.src = src;
  img.style.cssText = `
        max-width: 90vw; max-height: 85vh; border-radius: 12px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.8); object-fit: contain;
        background: #0b0f14; user-select: none;
    `;
  img.onclick = function (e) {
    e.stopPropagation();
  };

  const hint = document.createElement("div");
  hint.style.cssText = `
        position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
        color: rgba(255,255,255,0.4); font-size: 14px;
        background: rgba(0,0,0,0.4); padding: 6px 20px; border-radius: 999px;
        pointer-events: none; backdrop-filter: blur(2px);
    `;
  hint.textContent = "点击任意处关闭";

  overlay.appendChild(img);
  overlay.appendChild(hint);
  document.body.appendChild(overlay);

  const style = document.createElement("style");
  style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.96); }
            to { opacity: 1; transform: scale(1); }
        }
    `;
  overlay.appendChild(style);

  const escHandler = function (e) {
    if (e.key === "Escape") {
      overlay.remove();
      document.removeEventListener("keydown", escHandler);
    }
  };
  document.addEventListener("keydown", escHandler);
  overlay._escHandler = escHandler;

  const origRemove = overlay.remove.bind(overlay);
  overlay.remove = function () {
    document.removeEventListener("keydown", escHandler);
    origRemove();
  };
}

// ============================================================
// B站视频弹窗
// ============================================================
function openVideoLightbox(url) {
  const match = url.match(/BV[a-zA-Z0-9]{10}/);
  if (!match) {
    showToast("❌ 无法识别B站视频链接，请检查格式");
    return;
  }
  const bvid = match[0];
  const embedSrc = `https://player.bilibili.com/player.html?bvid=${bvid}&page=1&isOutside=true&high_quality=1&danmaku=0&autoplay=1`;

  const overlay = document.createElement("div");
  overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.85); z-index: 10000;
        display: flex; align-items: center; justify-content: center;
        cursor: pointer; padding: 40px; backdrop-filter: blur(4px);
        animation: fadeIn 0.25s ease;
    `;
  overlay.onclick = function () {
    this.remove();
  };

  const wrapper = document.createElement("div");
  wrapper.style.cssText = `
        position: relative; width: 90%; max-width: 1000px; padding-bottom: 56.25%; height: 0;
        background: #000; border-radius: 12px; overflow: hidden;
        box-shadow: 0 20px 60px rgba(0,0,0,0.8);
    `;

  const iframe = document.createElement("iframe");
  iframe.src = embedSrc;
  iframe.style.cssText = `
        position: absolute; top: 0; left: 0; width: 100%; height: 100%;
        border: 0;
    `;
  iframe.allowFullscreen = true;
  iframe.loading = "lazy";

  wrapper.appendChild(iframe);
  overlay.appendChild(wrapper);

  const hint = document.createElement("div");
  hint.style.cssText = `
        position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
        color: rgba(255,255,255,0.4); font-size: 14px;
        background: rgba(0,0,0,0.4); padding: 6px 20px; border-radius: 999px;
        pointer-events: none; backdrop-filter: blur(2px);
    `;
  hint.textContent = "点击任意处关闭";
  overlay.appendChild(hint);

  const style = document.createElement("style");
  style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.96); }
            to { opacity: 1; transform: scale(1); }
        }
    `;
  overlay.appendChild(style);

  document.body.appendChild(overlay);

  const escHandler = function (e) {
    if (e.key === "Escape") {
      overlay.remove();
      document.removeEventListener("keydown", escHandler);
    }
  };
  document.addEventListener("keydown", escHandler);
  overlay._escHandler = escHandler;

  const origRemove = overlay.remove.bind(overlay);
  overlay.remove = function () {
    document.removeEventListener("keydown", escHandler);
    origRemove();
  };
}

// ============================================================
// 分享功能（复制链接）
// ============================================================
function shareCopyLink() {
  const url = window.location.href;
  const title = document.title || "MCRES 方块工坊";
  const metaDesc = document.querySelector('meta[name="description"]');
  const description = metaDesc ? metaDesc.getAttribute("content") : "";

  let shareText = `MCRES · 方块工坊 - ${title}`;
  if (description) {
    shareText += ` - ${description}`;
  }
  shareText += ` | ${url}`;

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard
      .writeText(shareText)
      .then(() => showToast("✅ 已复制分享内容到剪贴板！"))
      .catch(() => fallbackCopy(shareText));
  } else {
    fallbackCopy(shareText);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand("copy");
    showToast("✅ 已复制分享内容到剪贴板！");
  } catch (e) {
    alert("复制失败，请手动复制：" + text);
  }
  document.body.removeChild(ta);
}

// 保留原 sharePage 作为兼容
function sharePage() {
  shareCopyLink();
}

// ============================================================
// 分享 - 生成海报
// ============================================================
function shareGeneratePoster() {
  if (typeof generatePoster === "function") {
    generatePoster();
  } else {
    showToast("❌ 海报模块尚未加载");
  }
}

// ============================================================
// PV 趋势图（资源详情页 - 左侧面板）
// ============================================================
let pvChartInstance = null;

function initPvTrend() {
  const canvas = document.getElementById("pvTrendChart");
  if (!canvas) return;

  const resourceType = window.RESOURCE_TYPE;
  const resourceId = window.RESOURCE_ID;
  if (!resourceType || !resourceId) return;

  const rangeSelect = document.getElementById("pvTrendRange");
  if (!rangeSelect) return;

  fetch(`/pv_trend?type=${resourceType}&id=${resourceId}`)
    .then((res) =>
      res.ok
        ? res.json()
        : res.json().then((err) => {
            throw new Error(err.message || "请求失败");
          }),
    )
    .then((json) => {
      if (json.code !== 0 || !json.data) {
        canvas.parentElement.innerHTML =
          '<div class="empty-hint">暂无浏览数据</div>';
        return;
      }

      const resourceData = json.data.resource || [];
      const siteAvgData = json.data.site_avg || [];

      if (resourceData.length === 0) {
        canvas.parentElement.innerHTML =
          '<div class="empty-hint">暂无浏览数据</div>';
        return;
      }

      const allDates = resourceData.map((item) => item.date);
      const resourceMap = {};
      resourceData.forEach((item) => {
        resourceMap[item.date] = item.pv;
      });
      const siteAvgMap = {};
      siteAvgData.forEach((item) => {
        siteAvgMap[item.date] = item.avg;
      });

      allDates.sort();

      const resourceValues = allDates.map((d) => resourceMap[d] || 0);
      const siteAvgValues = allDates.map((d) =>
        siteAvgMap[d] !== undefined ? siteAvgMap[d] : null,
      );

      renderPvChart(allDates, resourceValues, siteAvgValues, rangeSelect.value);

      rangeSelect.addEventListener("change", function () {
        renderPvChart(allDates, resourceValues, siteAvgValues, this.value);
      });
    })
    .catch((err) => {
      console.error("加载PV趋势失败:", err);
      canvas.parentElement.innerHTML = '<div class="empty-hint">加载失败</div>';
    });
}

function renderPvChart(allDates, resourceValues, siteAvgValues, range) {
  const canvas = document.getElementById("pvTrendChart");
  if (!canvas) return;

  let filteredDates, filteredResource, filteredSiteAvg;
  if (range === "all") {
    filteredDates = allDates;
    filteredResource = resourceValues;
    filteredSiteAvg = siteAvgValues;
  } else {
    const days = parseInt(range, 10);
    const len = allDates.length;
    const start = Math.max(0, len - days);
    filteredDates = allDates.slice(start);
    filteredResource = resourceValues.slice(start);
    filteredSiteAvg = siteAvgValues.slice(start);
  }

  if (filteredDates.length === 0) {
    canvas.parentElement.innerHTML =
      '<div class="empty-hint">所选范围无数据</div>';
    return;
  }

  if (pvChartInstance) {
    pvChartInstance.destroy();
    pvChartInstance = null;
  }

  const ctx = canvas.getContext("2d");
  const primaryColor =
    getComputedStyle(document.documentElement)
      .getPropertyValue("--primary-color")
      .trim() || "#55d88b";
  const gradient = ctx.createLinearGradient(0, 0, 0, 150);
  gradient.addColorStop(0, primaryColor + "40");
  gradient.addColorStop(1, primaryColor + "05");

  const validVals = filteredResource.filter((v) => v > 0);
  const avg =
    validVals.length > 0
      ? validVals.reduce((a, b) => a + b, 0) / validVals.length
      : 0;

  const datasets = [
    {
      label: "本资源",
      data: filteredResource,
      borderColor: primaryColor,
      backgroundColor: gradient,
      borderWidth: 2.5,
      pointRadius: 1.5,
      pointHoverRadius: 5,
      pointBackgroundColor: primaryColor,
      tension: 0.3,
      fill: true,
      spanGaps: false,
    },
  ];

  const hasSiteAvg = filteredSiteAvg.some(
    (v) => v !== null && v !== undefined && v > 0,
  );
  if (hasSiteAvg) {
    datasets.push({
      label: "全站平均",
      data: filteredSiteAvg,
      borderColor: "rgba(255,255,255,0.35)",
      borderDash: [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      pointHoverRadius: 4,
      pointBackgroundColor: "rgba(255,255,255,0.2)",
      tension: 0.3,
      fill: false,
      spanGaps: false,
    });
  }

  pvChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: filteredDates,
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: {
            color: "rgba(255,255,255,0.6)",
            boxWidth: 12,
            padding: 8,
            font: { size: 10 },
            usePointStyle: true,
            pointStyle: "line",
          },
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              if (context.datasetIndex === 0) {
                return context.parsed.y + " 次浏览";
              } else {
                return "全站平均: " + context.parsed.y.toFixed(1) + " 次";
              }
            },
          },
        },
      },
      scales: {
        x: {
          grid: { color: "rgba(255,255,255,0.03)" },
          ticks: {
            color: "rgba(255,255,255,0.35)",
            maxTicksLimit: 10,
            font: { size: 9 },
          },
        },
        y: {
          grid: { color: "rgba(255,255,255,0.03)" },
          ticks: {
            color: "rgba(255,255,255,0.35)",
            font: { size: 9 },
            beginAtZero: true,
          },
        },
      },
      interaction: {
        intersect: false,
        mode: "index",
      },
    },
  });

  const avgLabel = document.getElementById("pvAvgLabel");
  if (avgLabel) {
    avgLabel.textContent = "日均 " + avg.toFixed(1) + " 次";
  }
}

// ============================================================
// DOM 初始化
// ============================================================
document.addEventListener("DOMContentLoaded", function () {
  if (document.getElementById("pvTrendChart")) {
    initPvTrend();
  }
});

console.log("✅ MCRES 详情页公共脚本已加载");

// ---------- 分享 / 灯箱绑定（替代内联 onclick） ----------
(function () {
  "use strict";
  function bind() {
    document.querySelectorAll("[data-share-toggle]").forEach(function (btn) {
      btn.addEventListener("click", toggleShareDropdown);
    });
    document.querySelectorAll('[data-share-action="copy"]').forEach(function (a) {
      a.addEventListener("click", function (e) { e.preventDefault(); shareCopyLink(); });
    });
    document.querySelectorAll('[data-share-action="poster"]').forEach(function (a) {
      a.addEventListener("click", function (e) { e.preventDefault(); shareGeneratePoster(); });
    });
    document.querySelectorAll(".screenshot-item").forEach(function (el) {
      el.addEventListener("click", function () {
        if (el.dataset.video) openVideoLightbox(el.dataset.video);
        else if (el.dataset.screenshot) openLightbox(el.dataset.screenshot);
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
