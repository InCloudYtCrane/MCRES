// static/js/components/comment/actions.js
(function () {
  "use strict";

  var C = window.Comments;
  var state = C.state;

  // ---------- 表态 ----------
  function sendReaction(commentId, reaction) {
    if (!state.IS_LOGGED_IN) {
      Toast.warning("请先登录才能表态");
      return;
    }
    var comment = C.utils.findComment(commentId);
    if (comment && comment.user_id === state.CURRENT_USER_ID) {
      Toast.warning("不能对自己的评论表态");
      return;
    }
    C.data
      .postJSON("/comments/reaction", {
        comment_id: commentId,
        reaction: reaction,
      })
      .then(function (data) {
        if (data.success) {
          C.data.loadComments(state.currentPage);
          C.drawer.close("reaction");
        } else {
          Toast.error(data.message || "表态失败");
        }
      })
      .catch(function (err) {
        Toast.error("网络错误，请稍后重试");
        console.error(err);
      });
  }

  // ---------- 置顶 ----------
  function pinComment(commentId, path) {
    if (!state.IS_LOGGED_IN) {
      Toast.warning("请先登录");
      return;
    }
    C.data
      .postJSON("/comments/pin", { comment_id: commentId, path: path })
      .then(function (data) {
        if (data.success) {
          state.currentPage = 1;
          C.data.loadComments(1, { preserveScroll: false });
          var section = document.querySelector(".comments-section");
          if (section)
            section.scrollIntoView({ behavior: "smooth", block: "start" });
          C.drawer.close("action");
        } else {
          Toast.error(data.message || "操作失败");
        }
      })
      .catch(function (err) {
        Toast.error("网络错误，请稍后重试");
        console.error(err);
      });
  }

  // ---------- 发表顶层评论 ----------
  function submitTopComment() {
    if (state.isSubmitting) return;
    var inputEl = state.dom.inputEl;
    var submitBtn = state.dom.submitBtn;
    var content = inputEl.value.trim();
    if (!content) return;
    if (content.length > C.cfg.MAX_LENGTH) {
      Toast.warning("评论内容不能超过 " + C.cfg.MAX_LENGTH + " 个字符");
      return;
    }
    state.isSubmitting = true;
    submitBtn.disabled = true;
    submitBtn.textContent = "提交中…";
    submitBtn.style.opacity = "0.6";
    var path = C.utils.getCurrentPath();
    C.data
      .postJSON("/comments", { path: path, content: content })
      .then(function (data) {
        if (data.success) {
          inputEl.value = "";
          updateCharCounter();
          state.currentPage = 1;
          C.data.loadComments(1, { preserveScroll: false });
          var section = document.querySelector(".comments-section");
          if (section)
            section.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          throw new Error(data.message || "提交失败");
        }
      })
      .catch(function (err) {
        if (err.message === "HTML_REDIRECT") return;
        Toast.error("发表看法失败：" + err.message);
        console.error("提交评论失败:", err);
      })
      .finally(function () {
        if (document.getElementById("submitCommentBtn")) {
          state.isSubmitting = false;
          submitBtn.disabled = true;
          submitBtn.textContent = "发表看法";
          submitBtn.style.opacity = "1";
          updateSubmitButton();
        }
      });
  }

  // ---------- 发表子评论 ----------
  function submitChildComment(
    parentId,
    replyToNickname,
    content,
    formElement,
    replyToId,
  ) {
    if (state.isSubmitting) return;
    state.isSubmitting = true;
    var btn = formElement
      ? formElement.querySelector(".btn-submit-reply")
      : document.getElementById("threadReplyBtn");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "发送中…";
    }

    var path = C.utils.getCurrentPath();
    var payload = {
      path: path,
      content: content,
      parent_id: parentId,
      reply_to: replyToNickname || "",
      reply_to_id: replyToId || null,
    };
    C.data
      .postJSON("/comments", payload)
      .then(function (data) {
        if (data.success) {
          if (formElement) formElement.remove();
          state.expandedThreads[parentId] = true;
          C.data.loadComments(state.currentPage);
          var drawer = document.getElementById("threadDrawer");
          if (drawer && drawer.classList.contains("active")) {
            var input = document.getElementById("threadReplyInput");
            var pid = input && input.dataset.parentId;
            if (pid) C.drawer.openThread(pid);
          }
        } else {
          throw new Error(data.message || "提交失败");
        }
      })
      .catch(function (err) {
        if (err.message === "HTML_REDIRECT") return;
        Toast.error("回复失败：" + err.message);
        console.error("回复失败:", err);
      })
      .finally(function () {
        state.isSubmitting = false;
        if (btn) {
          btn.disabled = false;
          btn.textContent = "发送";
        }
      });
  }

  // ---------- 打开内联回复框 ----------
  function openInlineReply(targetId, targetNickname) {
    var existing = document.querySelector(".reply-form-inline.active");
    if (existing) existing.remove();
    var topId = C.utils.findTopCommentId(targetId);
    if (!topId) {
      Toast.error("无法定位评论所属楼层，请刷新后重试");
      return;
    }
    var targetContainer = state.dom.listEl.querySelector(
      '.comment-top[data-id="' + topId + '"]',
    );
    if (!targetContainer) return;
    var form = document.createElement("div");
    form.className = "reply-form-inline active";
    form.dataset.topId = topId;
    form.dataset.targetNickname = targetNickname;
    form.dataset.targetId = targetId;
    form.innerHTML =
      '<textarea rows="2" placeholder="回复 @' +
      C.utils.escapeHtml(targetNickname) +
      ' …" maxlength="500"></textarea>' +
      '<div class="reply-actions">' +
      '<button class="btn-cancel-reply">取消</button>' +
      '<button class="btn-submit-reply" disabled>发表回复</button>' +
      "</div>";
    var childrenContainer = targetContainer.querySelector(".comment-children");
    if (childrenContainer) {
      targetContainer.insertBefore(form, childrenContainer);
    } else {
      targetContainer.appendChild(form);
    }
    var textarea = form.querySelector("textarea");
    var submitReplyBtn = form.querySelector(".btn-submit-reply");
    var cancelBtn = form.querySelector(".btn-cancel-reply");
    textarea.focus();
    textarea.addEventListener("input", function () {
      if (this.value.length > C.cfg.MAX_LENGTH) {
        this.value = this.value.slice(0, C.cfg.MAX_LENGTH);
      }
      submitReplyBtn.disabled = this.value.trim().length === 0;
    });
    cancelBtn.addEventListener("click", function () {
      form.remove();
    });
    submitReplyBtn.addEventListener("click", function () {
      var content = textarea.value.trim();
      if (!content) return;
      submitChildComment(
        form.dataset.topId,
        form.dataset.targetNickname,
        content,
        form,
        form.dataset.targetId,
      );
    });
    textarea.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        if (!submitReplyBtn.disabled) submitReplyBtn.click();
      }
    });
  }

  // ---------- 删除 ----------
  function deleteComment(id) {
    id = Number(id);
    if (!id) return;
    var comment = C.utils.findComment(id);
    if (!comment) return;
    var nickname = comment.nickname || "用户";
    var hasChildren = state.comments.some(function (c) {
      return c.parent_id === id;
    });
    var confirmMsg = hasChildren
      ? "确定要删除「" + nickname + "」的这条看法及其所有回复吗？"
      : "确定要删除「" + nickname + "」的这条看法吗？";
    if (!confirm(confirmMsg)) return;
    var path = C.utils.getCurrentPath();
    C.data
      .deleteRequest("/comments/" + id + "?path=" + encodeURIComponent(path))
      .then(function (data) {
        if (data.success) {
          C.data.loadComments(state.currentPage);
          C.drawer.close("thread");
        } else {
          throw new Error(data.message || "删除失败");
        }
      })
      .catch(function (err) {
        Toast.error("删除失败：" + err.message);
        console.error("删除失败:", err);
      });
  }

  // ---------- 举报（桌面端） ----------
  function openReportModal(commentId) {
    state.reportTargetId = Number(commentId);
    document.getElementById("reportModal").classList.add("active");
    document.getElementById("reportReason").value = "";
    document.getElementById("reportSubmitBtn").disabled = false;
    document.body.style.overflow = "hidden";
  }

  function closeReportModal() {
    document.getElementById("reportModal").classList.remove("active");
    document.body.style.overflow = "";
    state.reportTargetId = null;
  }

  function submitReport() {
    var reason = document.getElementById("reportReason").value.trim();
    if (!reason) {
      Toast.warning("请填写举报理由");
      return;
    }
    if (!state.reportTargetId) {
      Toast.error("举报目标丢失，请重新操作");
      return;
    }
    var targetComment = C.utils.findComment(state.reportTargetId);
    if (!targetComment) {
      Toast.error("评论不存在");
      return;
    }
    var btn = document.getElementById("reportSubmitBtn");
    btn.disabled = true;
    btn.textContent = "提交中…";
    C.data
      .postJSON("/comments/report", {
        author_id: targetComment.user_id,
        reason: reason,
        content: targetComment.content,
      })
      .then(function (data) {
        if (data.success) {
          Toast.success("举报已提交，感谢您的反馈！");
          closeReportModal();
        } else {
          throw new Error(data.message || "提交失败");
        }
      })
      .catch(function (err) {
        Toast.error("举报失败：" + err.message);
        console.error("举报错误:", err);
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "提交举报";
      });
  }

  // ---------- 字符计数 ----------
  function updateCharCounter() {
    var inputEl = state.dom.inputEl;
    var charCounter = state.dom.charCounter;
    var len = inputEl.value.length;
    charCounter.textContent = len + " / " + C.cfg.MAX_LENGTH;
    charCounter.classList.remove("warning", "danger");
    if (len > C.cfg.MAX_LENGTH * 0.85) charCounter.classList.add("warning");
    if (len > C.cfg.MAX_LENGTH) charCounter.classList.add("danger");
    updateSubmitButton();
  }

  function updateSubmitButton() {
    var inputEl = state.dom.inputEl;
    var submitBtn = state.dom.submitBtn;
    var len = inputEl.value.trim().length;
    submitBtn.disabled =
      len === 0 || len > C.cfg.MAX_LENGTH || state.isSubmitting;
  }

  // ============================================================
  // ★ 插入表情到输入框光标位置
  // ------------------------------------------------------------
  // 参数 key：表情标识符（如 "smile"），最终插入文本为 "[smile]"
  // 优先用 setRangeText（保留撤销栈、输入法状态）
  // ============================================================
  function insertEmoji(key) {
    if (!key) return;
    var inputEl = state.dom.inputEl;
    if (!inputEl) return;
    if (inputEl.disabled) {
      Toast.warning("请先登录再使用表情");
      return;
    }

    var token = "[" + key + "]";

    if (inputEl.value.length + token.length > C.cfg.MAX_LENGTH) {
      Toast.warning("评论内容不能超过 " + C.cfg.MAX_LENGTH + " 个字符");
      return;
    }

    if (typeof inputEl.setRangeText === "function") {
      // 现代浏览器：在光标处插入，光标自动移到插入文本之后
      inputEl.setRangeText(
        token,
        inputEl.selectionStart,
        inputEl.selectionEnd,
        "end",
      );
    } else {
      // 兜底：手动拼接
      var start = inputEl.selectionStart || 0;
      var end = inputEl.selectionEnd || 0;
      var v = inputEl.value;
      inputEl.value = v.slice(0, start) + token + v.slice(end);
      var pos = start + token.length;
      inputEl.selectionStart = inputEl.selectionEnd = pos;
    }

    inputEl.focus();
    updateCharCounter();
  }

  C.actions = {
    sendReaction: sendReaction,
    pinComment: pinComment,
    submitTopComment: submitTopComment,
    submitChildComment: submitChildComment,
    openInlineReply: openInlineReply,
    deleteComment: deleteComment,
    openReportModal: openReportModal,
    closeReportModal: closeReportModal,
    submitReport: submitReport,
    updateCharCounter: updateCharCounter,
    updateSubmitButton: updateSubmitButton,
    insertEmoji: insertEmoji,   // ★ 新增
  };

  // 暴露给 HTML 内联事件
  window.closeReportModal = closeReportModal;
  window.submitReport = submitReport;
})();