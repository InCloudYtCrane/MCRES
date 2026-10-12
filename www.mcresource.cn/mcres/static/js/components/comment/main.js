// static/js/components/comment/main.js
(function () {
  'use strict';

  var C = window.Comments;
  var state = C.state;

  function initDom() {
    state.dom = {
      listEl: document.getElementById('commentsList'),
      countEl: document.getElementById('commentsCount'),
      inputEl: document.getElementById('commentInput'),
      submitBtn: document.getElementById('submitCommentBtn'),
      charCounter: document.getElementById('charCounter'),
      loadingEl: document.getElementById('commentsLoading'),
      emptyEl: document.getElementById('commentsEmpty'),
      errorEl: document.getElementById('commentsError'),
      loginPrompt: document.getElementById('loginPrompt'),
      paginationTop: document.getElementById('paginationTop'),
      paginationBottom: document.getElementById('paginationBottom')
    };
  }

  // ============================================================
  // ★ 把所有 fixed 定位的弹层从评论组件里移到 body
  // ============================================================
  function moveDrawersToBody() {
    var ids = [
      'reactionDrawer',
      'actionDrawer',
      'threadDrawer',
      'reportDrawer',
      'reportModal'
    ];
    ids.forEach(function (id) {
      var drawer = document.getElementById(id);
      if (drawer && drawer.parentNode !== document.body) {
        document.body.appendChild(drawer);
      }
    });
  }

  function applyPageSpecificText() {
    var path = window.location.pathname;
    var isProfilePage = /^\/profile\/\d+$/.test(path);
    var titleEl = document.querySelector('.comments-title');
    var emptyTextEl = document.querySelector('.comments-empty span:last-child');
    var inputEl = state.dom.inputEl;
    var submitBtn = state.dom.submitBtn;

    if (isProfilePage) {
      if (titleEl) titleEl.innerHTML = '<i class="fas fa-pen"></i> 留言板';
      if (emptyTextEl) emptyTextEl.textContent = '还没有留言，来写下第一条吧！';
      if (submitBtn) submitBtn.textContent = '发表留言';
      if (inputEl) inputEl.placeholder = '写下你的留言...';
    } else {
      if (titleEl) titleEl.innerHTML = '<i class="fas fa-comment"></i> 看法';
      if (emptyTextEl) emptyTextEl.textContent = '还没有看法，来发表第一条吧！';
      if (submitBtn) submitBtn.textContent = '发表看法';
      if (inputEl) inputEl.placeholder = '写下你的看法...';
    }
  }

  function applyLoginState() {
    var loginPrompt = state.dom.loginPrompt;
    var inputEl = state.dom.inputEl;
    var submitBtn = state.dom.submitBtn;
    var emojiBtn = document.getElementById('emojiToggleBtn');
    if (loginPrompt) {
      if (state.IS_LOGGED_IN) {
        loginPrompt.style.display = 'none';
        if (inputEl) inputEl.disabled = false;
        if (submitBtn) submitBtn.disabled = true;
        if (emojiBtn) emojiBtn.disabled = false;
      } else {
        loginPrompt.style.display = 'block';
        if (inputEl) inputEl.disabled = true;
        if (submitBtn) submitBtn.disabled = true;
        if (emojiBtn) emojiBtn.disabled = true;
      }
    } else if (emojiBtn) {
      emojiBtn.disabled = !state.IS_LOGGED_IN;
    }
  }

  function bindTopForm() {
    var inputEl = state.dom.inputEl;
    var submitBtn = state.dom.submitBtn;
    if (inputEl) {
      inputEl.addEventListener('input', function () {
        if (this.value.length > C.cfg.MAX_LENGTH) {
          this.value = this.value.slice(0, C.cfg.MAX_LENGTH);
        }
        C.actions.updateCharCounter();
      });
      inputEl.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          if (!submitBtn.disabled) C.actions.submitTopComment();
        }
      });
    }
    if (submitBtn) {
      submitBtn.addEventListener('click', C.actions.submitTopComment);
    }
  }

  function bindDrawerClosers() {
    document.addEventListener('click', function (e) {
      var mask = e.target.closest('.drawer-mask');
      var closeBtn = e.target.closest('.drawer-close');
      var cancelBtn = e.target.closest('.drawer-btn-cancel');
      if (mask || closeBtn) {
        var drawerId = mask ? mask.dataset.drawer : closeBtn.dataset.drawer;
        if (drawerId) C.drawer.close(drawerId);
      }
      if (cancelBtn) {
        var did = cancelBtn.dataset.drawer;
        if (did) C.drawer.close(did);
      }
    });
  }

  // ============================================================
  // ★ 站内表情选择器
  // ------------------------------------------------------------
  // 面板里显示的是**图片**（<img src="url">），不是键名
  // 键名 [smile] 只用于 title / alt / 点击后插入到输入框
  // ============================================================
  function initEmojiPicker() {
    var toggle = document.getElementById('emojiToggleBtn');
    var panel = document.getElementById('emojiPanel');
    var grid = document.getElementById('emojiPanelGrid');
    if (!toggle || !panel || !grid) return;

    function renderGrid() {
      var list = state.EMOJI_LIST || [];
      if (!list.length) {
        grid.innerHTML = '<div class="emoji-panel-empty">暂无可用表情</div>';
        return;
      }
      var html = '';
      list.forEach(function (e) {
        var key = (e && e.key) || '';
        var url = (e && e.url) || '';
        if (!key || !url) return;
        var safeKey = C.utils.escapeHtml(key);
        var safeUrl = C.utils.escapeHtml(url);
        // 显示图片，键名只做提示与 alt
        html +=
          '<button type="button" class="emoji-panel-item" ' +
          'data-key="' + safeKey + '" ' +
          'title="[' + safeKey + ']">' +
            '<img src="' + safeUrl + '" alt="' + safeKey + '" loading="lazy">' +
          '</button>';
      });
      grid.innerHTML = html || '<div class="emoji-panel-empty">暂无可用表情</div>';
    }
    renderGrid();

    // 打开 / 关闭面板
    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      if (state.dom.inputEl && state.dom.inputEl.disabled) return;
      panel.hidden = !panel.hidden;
    });

    // 点击表情 → 插入到光标位置（面板保持打开，方便连续插入）
    grid.addEventListener('click', function (e) {
      var btn = e.target.closest('.emoji-panel-item');
      if (!btn) return;
      var key = btn.dataset.key;
      if (key) C.actions.insertEmoji(key);
    });

    // 点击面板外部关闭
    document.addEventListener('click', function (e) {
      if (panel.hidden) return;
      if (!panel.contains(e.target) &&
          e.target !== toggle &&
          !toggle.contains(e.target)) {
        panel.hidden = true;
      }
    });

    // Esc 关闭
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) panel.hidden = true;
    });
  }

  function init() {
    initDom();
    moveDrawersToBody();
    applyPageSpecificText();
    applyLoginState();
    state.currentPath = C.utils.getCurrentPath();
    C.actions.updateCharCounter();
    bindTopForm();
    bindDrawerClosers();

    // 表态类型加载完后再加载评论
    C.loadReactionTypes().finally(function () {
      C.data.loadComments(1, {
        preserveScroll: false,
        onComplete: function () {
          if (window.location.hash) {
            setTimeout(C.scroll.scrollToCommentFromHash, 100);
          }
        }
      });
    });

    // ★ 加载表情列表并初始化表情选择器
    C.loadEmojiList().finally(function () {
      initEmojiPicker();
    });

    // 顶部 reportModal 关闭
    var reportModal = document.getElementById('reportModal');
    if (reportModal) {
      reportModal.addEventListener('click', function (e) {
        if (e.target === this) C.actions.closeReportModal();
      });
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') C.actions.closeReportModal();
    });

    // hash 变化重新定位
    window.addEventListener('hashchange', function () {
      C.scroll.scrollToCommentFromHash();
    });

    // 点击外部关闭表态选择器
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.comment-reactions')) {
        document.querySelectorAll('.reaction-picker.active').forEach(function (p) {
          p.classList.remove('active');
        });
      }
    });

    console.log('评论组件已加载（模块化版本 + 站内表情）');
  }

  // 暴露 API
  window.reloadComments = function () {
    C.data.loadComments(state.currentPage);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

// ---------- 内联 onclick 替代（重试 / 举报模态框） ----------
(function () {
  function bind() {
    var reload = document.getElementById("reloadCommentsLink");
    if (reload) reload.addEventListener("click", function (e) { e.preventDefault(); window.reloadComments(); });
    var closeBtn = document.getElementById("reportModalCloseBtn");
    if (closeBtn) closeBtn.addEventListener("click", window.closeReportModal);
    var cancelBtn = document.getElementById("reportCancelBtn");
    if (cancelBtn) cancelBtn.addEventListener("click", window.closeReportModal);
    var submitBtn = document.getElementById("reportSubmitBtn");
    if (submitBtn) submitBtn.addEventListener("click", window.submitReport);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
