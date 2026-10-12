// mcres/static/js/pages/messages.js
// 消息中心：分类 Tab 切换 + 各 Tab 独立分页加载。
(function () {
  "use strict";

  // ============================================================
  // 分页状态（totalPages 由模板注入到 window.MESSAGES_PAGER）
  // ============================================================
  var injected = window.MESSAGES_PAGER || {};
  var pagerState = {
    replies: { page: 1, totalPages: injected.replies || 1 },
    system: { page: 1, totalPages: injected.system || 1 },
    guestbook: { page: 1, totalPages: injected.guestbook || 1 },
    tea: { page: 1, totalPages: injected.tea || 1 },
  };
  var pagerLoading = {
    replies: false,
    system: false,
    guestbook: false,
    tea: false,
  };

  // ============================================================
  // Tab 切换
  // ============================================================
  var navItems = document.querySelectorAll(".category-nav .cat-item");
  var panels = document.querySelectorAll(".tab-panel");
  var listTitle = document.getElementById("listTitle");

  // tabMeta 的 count 值由模板通过 data 属性挂在 DOM 上，避免模板里再塞 Jinja。
  // 每个 tab-panel 上会带 data-total-count，见模板改动。
  function getTabMeta(tabId) {
    var panel = document.querySelector('.tab-panel[data-tab="' + tabId + '"]');
    if (!panel) return null;
    return {
      title: panel.dataset.tabTitle || tabId,
      count: panel.dataset.tabCount || "0",
    };
  }

  var currentTab = "replies";

  function switchTab(tabId) {
    currentTab = tabId;
    navItems.forEach(function (item) {
      item.classList.toggle("active", item.dataset.tab === tabId);
    });
    panels.forEach(function (panel) {
      panel.classList.toggle("hidden", panel.dataset.tab !== tabId);
    });
    var meta = getTabMeta(tabId);
    if (meta && listTitle) {
      listTitle.innerHTML =
        meta.title + ' <span class="count">· ' + meta.count + " 条</span>";
    }
    if (history.pushState) {
      history.pushState(null, "", "#tab=" + tabId);
    }
    // 切换后手动触发一次 sentinel 可见性检查（应对列表短的情况）
    setTimeout(checkSentinelVisibility, 60);
  }

  navItems.forEach(function (item) {
    item.addEventListener("click", function () {
      var tabId = this.dataset.tab;
      if (tabId) switchTab(tabId);
    });
  });

  function getTabFromHash() {
    var hash = window.location.hash;
    if (hash.startsWith("#tab=")) return hash.replace("#tab=", "");
    return null;
  }
  var initialTab = getTabFromHash() || "replies";
  if (
    initialTab &&
    document.querySelector(
      '.category-nav .cat-item[data-tab="' + initialTab + '"]',
    )
  ) {
    switchTab(initialTab);
  }
  window.addEventListener("hashchange", function () {
    var tab = getTabFromHash();
    if (
      tab &&
      document.querySelector('.category-nav .cat-item[data-tab="' + tab + '"]')
    ) {
      switchTab(tab);
    }
  });

  // ============================================================
  // HTML 转义
  // ============================================================
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
  // 各类型消息的渲染函数
  // ============================================================
  function renderReplyItem(item) {
    var c = item.content || {};
    var avatar = c.avatar
      ? '<img src="' + escapeHtml(c.avatar) + '" alt="avatar">'
      : escapeHtml((c.nickname || "?")[0].toUpperCase());
    var unreadDot = item.is_unread ? '<span class="unread-dot"></span>' : "";
    var quote = item.parent_content
      ? '<span class="quote"><span class="parent-author">@' +
        escapeHtml(item.parent_nickname || "") +
        " 的评论：</span>" +
        escapeHtml(item.parent_content) +
        "</span>"
      : "";

    return (
      '<div class="message-item">' +
      '<div class="avatar-wrapper">' +
      '<a href="' +
      escapeHtml(c.profile_url || "#") +
      '" class="avatar-link" target="_blank" rel="noopener noreferrer">' +
      '<div class="avatar">' +
      avatar +
      "</div>" +
      "</a>" +
      unreadDot +
      "</div>" +
      '<div class="body">' +
      '<div class="top">' +
      '<a href="' +
      escapeHtml(c.profile_url || "#") +
      '" class="username-link" target="_blank" rel="noopener noreferrer">' +
      '<span class="username">' +
      escapeHtml(c.nickname || "") +
      ' <span class="tag">回复了你</span></span>' +
      "</a>" +
      '<span class="time">' +
      escapeHtml(c.created_at || "") +
      "(" +
      escapeHtml(item.time_since || "") +
      ")</span>" +
      '<a href="' +
      escapeHtml(item.target_url || "#") +
      '" class="view-link" target="_blank" rel="noopener noreferrer">查看</a>' +
      "</div>" +
      '<div class="content">' +
      '<span class="highlight">回复内容：</span>' +
      "<span>" +
      escapeHtml(c.content || "") +
      "</span>" +
      quote +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function renderSystemItem(item) {
    var avatar = item.sender_avatar
      ? '<img src="' + escapeHtml(item.sender_avatar) + '" alt="avatar">'
      : escapeHtml((item.sender_nick || "?")[0].toUpperCase());
    var unreadDot = item.is_unread ? '<span class="unread-dot"></span>' : "";
    var hasProfile = item.profile_url && item.profile_url !== "#";

    var contentHtml = "";
    if (item.status_tag) {
      (item.content_parts || []).forEach(function (part) {
        if (part === "#已通过#" || part === "#已退回#") {
          contentHtml +=
            '<span class="status-badge status-' +
            escapeHtml(item.status_color || "") +
            '">' +
            escapeHtml(item.status_tag) +
            "</span>";
        } else {
          contentHtml += escapeHtml(part);
        }
      });
    } else {
      contentHtml = escapeHtml(item.content || "");
    }

    var nickHtml = hasProfile
      ? '<a href="' +
        escapeHtml(item.profile_url) +
        '" class="username-link" target="_blank" rel="noopener noreferrer"><span class="username">' +
        escapeHtml(item.sender_nick || "") +
        "</span></a>"
      : '<span class="username">' +
        escapeHtml(item.sender_nick || "") +
        "</span>";

    return (
      '<div class="message-item">' +
      '<div class="avatar-wrapper">' +
      '<a href="' +
      escapeHtml(item.profile_url || "#") +
      '" class="avatar-link" target="_blank" rel="noopener noreferrer">' +
      '<div class="avatar">' +
      avatar +
      "</div>" +
      "</a>" +
      unreadDot +
      "</div>" +
      '<div class="body">' +
      '<div class="top">' +
      nickHtml +
      '<span class="time">' +
      escapeHtml(item.time || "") +
      "(" +
      escapeHtml(item.time_since || "") +
      ")</span>" +
      "</div>" +
      '<div class="content">' +
      contentHtml +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function renderBoardItem(item) {
    var c = item.content || {};
    var avatar = c.avatar
      ? '<img src="' + escapeHtml(c.avatar) + '" alt="avatar">'
      : escapeHtml((c.nickname || "?")[0].toUpperCase());
    var unreadDot = item.is_unread ? '<span class="unread-dot"></span>' : "";

    return (
      '<div class="message-item">' +
      '<div class="avatar-wrapper">' +
      '<a href="' +
      escapeHtml(c.profile_url || "#") +
      '" class="avatar-link" target="_blank" rel="noopener noreferrer">' +
      '<div class="avatar">' +
      avatar +
      "</div>" +
      "</a>" +
      unreadDot +
      "</div>" +
      '<div class="body">' +
      '<div class="top">' +
      '<a href="' +
      escapeHtml(c.profile_url || "#") +
      '" class="username-link" target="_blank" rel="noopener noreferrer">' +
      '<span class="username">' +
      escapeHtml(c.nickname || "") +
      "</span>" +
      "</a>" +
      '<span class="time">' +
      escapeHtml(c.created_at || "") +
      "(" +
      escapeHtml(item.time_since || "") +
      ")</span>" +
      '<a href="' +
      escapeHtml(item.target_url || "#") +
      '" class="view-link" target="_blank" rel="noopener noreferrer">查看</a>' +
      "</div>" +
      '<div class="content">' +
      escapeHtml(c.content || "") +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function renderTeaItem(item) {
    var iconMap = {
      reply: '<i class="fas fa-reply"></i>',
      like: '<i class="fas fa-thumbs-up"></i>',
      punish: '<i class="fas fa-gavel"></i>',
      manager: '<i class="fas fa-shield-halved"></i>',
      topic: '<i class="fas fa-fire"></i>',
    };
    var icon = iconMap[item.type] || "";
    var unreadDot = item.is_unread ? '<span class="unread-dot"></span>' : "";

    var avatarBlock = "";
    if (item.user_id) {
      var inner = item.avatar
        ? '<img src="' + escapeHtml(item.avatar) + '" alt="avatar">'
        : escapeHtml((item.nickname || "?")[0].toUpperCase());
      avatarBlock =
        '<a href="/profile/' +
        item.user_id +
        '" class="avatar-link" target="_blank" rel="noopener noreferrer"><div class="avatar">' +
        inner +
        "</div></a>";
    } else {
      avatarBlock =
        '<div class="avatar"><i class="fas fa-mug-hot" style="font-size:18px;color:#e8a437;"></i></div>';
    }

    var viewLink =
      item.url && item.url !== "#"
        ? '<a href="' +
          escapeHtml(item.url) +
          '" class="view-link" target="_blank" rel="noopener noreferrer">去茶室</a>'
        : "";

    var topicChip = item.topic
      ? '<span class="tea-topic-chip">#' + escapeHtml(item.topic) + "</span>"
      : "";

    var titleBlock = "";
    if (
      item.type === "reply" ||
      item.type === "like" ||
      item.type === "topic"
    ) {
      titleBlock =
        '<div class="tea-msg-title"><i class="fas fa-file-lines"></i>《' +
        escapeHtml(item.title || "") +
        "》</div>";
    }

    return (
      '<div class="message-item">' +
      '<div class="avatar-wrapper">' +
      avatarBlock +
      unreadDot +
      "</div>" +
      '<div class="body">' +
      '<div class="top">' +
      '<span class="username">' +
      '<span class="tea-type-badge tea-type-' +
      escapeHtml(item.type) +
      '">' +
      icon +
      "</span>" +
      escapeHtml(item.nickname || "") +
      "</span>" +
      '<span class="time">' +
      escapeHtml(item.time || "") +
      "(" +
      escapeHtml(item.time_since || "") +
      ")</span>" +
      viewLink +
      "</div>" +
      '<div class="content">' +
      topicChip +
      "<span>" +
      escapeHtml(item.content || "") +
      "</span>" +
      titleBlock +
      "</div>" +
      "</div>" +
      "</div>"
    );
  }

  function renderItem(tab, item) {
    if (tab === "replies") return renderReplyItem(item);
    if (tab === "system") return renderSystemItem(item);
    if (tab === "guestbook") return renderBoardItem(item);
    if (tab === "tea") return renderTeaItem(item);
    return "";
  }

  // ============================================================
  // 追加一页数据
  // ============================================================
  function appendItems(tab, items) {
    var list = document.querySelector('.message-list[data-list="' + tab + '"]');
    if (!list) return;
    var html = items
      .map(function (it) {
        return renderItem(tab, it);
      })
      .join("");
    list.insertAdjacentHTML("beforeend", html);
  }

  // ============================================================
  // 加载下一页
  // ============================================================
  async function loadNextPage(tab) {
    var state = pagerState[tab];
    if (!state || pagerLoading[tab]) return;
    if (state.page >= state.totalPages) return;

    pagerLoading[tab] = true;
    var sentinel = document.querySelector(
      '.load-more-sentinel[data-sentinel="' + tab + '"]',
    );
    if (sentinel) {
      sentinel.hidden = false;
      sentinel.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 加载中…';
    }

    try {
      var next = state.page + 1;
      var res = await fetch(
        "/message/page?tab=" + encodeURIComponent(tab) + "&page=" + next,
        { credentials: "same-origin" },
      );
      var data = await res.json();

      if (data.success && data.items && data.items.length) {
        appendItems(tab, data.items);
        state.page = data.pagination.page;
        state.totalPages = data.pagination.total_pages;

        if (sentinel) {
          if (state.page >= state.totalPages) {
            sentinel.innerHTML = '<span class="end-text">—— 到底了 ——</span>';
          } else {
            sentinel.innerHTML = "";
          }
        }
      } else {
        if (sentinel) {
          sentinel.innerHTML = '<span class="end-text">—— 到底了 ——</span>';
        }
        state.page = state.totalPages;
      }
    } catch (err) {
      console.error("加载消息失败:", err);
      if (sentinel) {
        sentinel.innerHTML =
          '<span style="color:#c0392b;">加载失败，请重试</span>';
      }
    } finally {
      pagerLoading[tab] = false;
    }
  }

  // ============================================================
  // 检查当前 tab 的 sentinel 是否可见（应对列表短的情况）
  // ============================================================
  function checkSentinelVisibility() {
    var sentinel = document.querySelector(
      '.load-more-sentinel[data-sentinel="' + currentTab + '"]',
    );
    if (!sentinel || sentinel.hidden) return;
    var rect = sentinel.getBoundingClientRect();
    if (rect.top < window.innerHeight + 200) {
      loadNextPage(currentTab);
    }
  }

  // ============================================================
  // IntersectionObserver：只有当前可见 tab 的 sentinel 触发加载
  // ============================================================
  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        var tab = entry.target.dataset.sentinel;
        if (tab !== currentTab) return;
        loadNextPage(tab);
      });
    },
    {
      root: null,
      rootMargin: "200px 0px",
      threshold: 0,
    },
  );

  document.querySelectorAll(".load-more-sentinel").forEach(function (el) {
    observer.observe(el);
  });

  // 兜底：窗口 resize / 内容高度变化时再检查一次
  window.addEventListener("resize", checkSentinelVisibility);

  // 页面加载完毕后检查一次（应对首屏就能看到 sentinel 的情况）
  setTimeout(checkSentinelVisibility, 200);
})();
