/**
 * McresEditor 工具栏模块
 * 路径：mcres/static/js/lib/editor/editor-toolbar.js
 *
 * 提供：
 *   - buildToolbar(toolbarEl, editorEl, handlers)
 *   - updateToolbarState(toolbarEl, editorEl, headingSelect)
 */
(function (global) {
  "use strict";

  const Utils = global.McresEditorUtils;
  if (!Utils) {
    console.error("[McresEditorToolbar] 缺少 McresEditorUtils");
    return;
  }

  // ============ 工具栏分组配置 ============
  const TOOLBAR_GROUPS = [
    {
      id: "history",
      buttons: [
        { cmd: "undo", label: "↩", title: "撤销 (Ctrl+Z)" },
        { cmd: "redo", label: "↪", title: "重做 (Ctrl+Y)" },
      ],
    },
    {
      id: "style",
      buttons: [
        { cmd: "bold", label: "<b>B</b>", title: "加粗 (Ctrl+B)" },
        { cmd: "italic", label: "<i>I</i>", title: "斜体 (Ctrl+I)" },
        { cmd: "underline", label: "<u>U</u>", title: "下划线 (Ctrl+U)" },
        { cmd: "strikeThrough", label: "<s>S</s>", title: "删除线" },
      ],
    },
    { id: "color", type: "color", cmd: "foreColor", title: "文字颜色" },
    { id: "bgcolor", type: "color", cmd: "hiliteColor", title: "背景色" },
    {
      id: "heading",
      type: "select",
      label: "标题",
      options: [
        { value: "p", label: "正文" },
        { value: "h1", label: "标题 1" },
        { value: "h2", label: "标题 2" },
        { value: "h3", label: "标题 3" },
        { value: "h4", label: "标题 4" },
        { value: "h5", label: "标题 5" },
        { value: "h6", label: "标题 6" },
      ],
    },
    {
      id: "align",
      buttons: [
        { cmd: "justifyLeft", label: "≡←", title: "左对齐" },
        { cmd: "justifyCenter", label: "≡↔", title: "居中" },
        { cmd: "justifyRight", label: "≡→", title: "右对齐" },
      ],
    },
    {
      id: "list",
      buttons: [
        { cmd: "insertUnorderedList", label: "• 无序列表", title: "无序列表" },
        { cmd: "insertOrderedList", label: "1. 有序列表", title: "有序列表" },
      ],
    },
    {
      id: "indent",
      buttons: [
        { cmd: "indent", label: "→", title: "增加缩进 (Tab)" },
        { cmd: "outdent", label: "←", title: "减少缩进 (Shift+Tab)" },
      ],
    },
    {
      id: "block",
      buttons: [
        { cmd: "toggleBlockquote", label: "〝 引用", title: "引用 (切换)" },
        { cmd: "insertHorizontalRule", label: "—", title: "分割线" },
      ],
    },
    {
      id: "insert",
      buttons: [
        { cmd: "createLink", label: "🔗 链接", title: "超链接" },
        { cmd: "unlink", label: "🔗 取消", title: "取消链接" },
        { cmd: "insertTable", label: "⊞ 表格", title: "插入表格" },
      ],
    },
    {
      id: "clear",
      buttons: [
        { cmd: "removeFormat", label: "✖ 清除格式", title: "清除所有格式" },
      ],
    },
  ];

  // ============ 构建 ============

  function buildToolbar(toolbarEl, editorEl, handlers) {
    let headingSelect = null;

    TOOLBAR_GROUPS.forEach((group) => {
      const div = document.createElement("div");
      div.className = "group";

      if (group.type === "color") {
        div.appendChild(buildColorInput(group, editorEl));
      } else if (group.type === "select") {
        const sel = buildHeadingSelect(group, editorEl);
        headingSelect = sel;
        div.appendChild(sel);
      } else {
        group.buttons.forEach((btn) => {
          div.appendChild(buildButton(btn, editorEl, handlers));
        });
      }

      toolbarEl.appendChild(div);
    });

    return { headingSelect };
  }

  function buildColorInput(group, editorEl) {
    const input = document.createElement("input");
    input.type = "color";
    input.title = group.title || "颜色";
    input.dataset.cmd = group.cmd;

    // H1 修复：初始值用合理默认，不再每次重置成 #000000
    input.value = group.cmd === "foreColor" ? "#e6edf3" : "#11161c";

    input.addEventListener("input", function (e) {
      e.stopPropagation();
      const color = this.value;
      editorEl.focus();
      document.execCommand(this.dataset.cmd, false, color);
      // 不再重置
    });

    input.addEventListener("mousedown", function (e) {
      e.stopPropagation();
    });

    return input;
  }

  function buildHeadingSelect(group, editorEl) {
    const sel = document.createElement("select");
    sel.title = group.label || "标题";
    sel.dataset.cmd = "formatBlock";

    group.options.forEach((opt) => {
      const o = document.createElement("option");
      o.value = opt.value;
      o.textContent = opt.label;
      sel.appendChild(o);
    });

    sel.addEventListener("change", function (e) {
      e.stopPropagation();
      const val = this.value;
      if (val) {
        editorEl.focus();
        document.execCommand("formatBlock", false, "<" + val + ">");
      }
      // 不重置为 'p'，交给 updateToolbarState 回填
    });

    sel.addEventListener("mousedown", function (e) {
      e.stopPropagation();
    });

    return sel;
  }

  function buildButton(btn, editorEl, handlers) {
    const button = document.createElement("button");
    button.innerHTML = btn.label;
    button.title = btn.title || "";
    button.dataset.cmd = btn.cmd;
    if (btn.value) button.dataset.value = btn.value;

    button.addEventListener("click", function (e) {
      e.stopPropagation();
      const cmd = this.dataset.cmd;
      const val = this.dataset.value || null;
      editorEl.focus();

      switch (cmd) {
        case "toggleBlockquote":
          if (handlers.toggleBlockquote) handlers.toggleBlockquote();
          return;
        case "createLink":
          if (handlers.createLink) handlers.createLink(this);
          return;
        case "unlink":
          document.execCommand("unlink", false, null);
          return;
        case "insertTable":
          if (handlers.insertTable) handlers.insertTable(this);
          return;
        case "removeFormat":
          if (handlers.removeFormat) handlers.removeFormat();
          return;
        case "insertHorizontalRule":
          document.execCommand("insertHorizontalRule", false, null);
          return;
      }

      if (cmd === "formatBlock" && val) {
        document.execCommand("formatBlock", false, val);
      } else {
        document.execCommand(cmd, false, null);
      }
    });

    return button;
  }

  // ============ 状态更新 ============

  function updateToolbarState(toolbarEl, editorEl, headingSelect) {
    if (!toolbarEl || !editorEl) return;

    // 按钮状态
    const buttons = toolbarEl.querySelectorAll("button[data-cmd]");
    buttons.forEach((btn) => {
      const cmd = btn.dataset.cmd;
      if (!cmd) return;
      const stateCmds = [
        "bold",
        "italic",
        "underline",
        "strikeThrough",
        "justifyLeft",
        "justifyCenter",
        "justifyRight",
        "insertUnorderedList",
        "insertOrderedList",
      ];
      if (stateCmds.includes(cmd)) {
        try {
          btn.classList.toggle("active", document.queryCommandState(cmd));
        } catch (_) {}
      }
    });

    // 引用按钮状态
    const blockquoteBtn = toolbarEl.querySelector(
      'button[data-cmd="toggleBlockquote"]',
    );
    if (blockquoteBtn) {
      try {
        const sel = window.getSelection();
        if (sel.rangeCount) {
          const node = sel.getRangeAt(0).startContainer;
          const parent = node.nodeType === 3 ? node.parentElement : node;
          blockquoteBtn.classList.toggle(
            "active",
            !!(parent && parent.closest && parent.closest("blockquote")),
          );
        }
      } catch (_) {}
    }

    // H4 修复：标题下拉框只匹配 p 和 h1~h6，其他一律回退到 p
    if (headingSelect) {
      try {
        const sel = window.getSelection();
        let tag = "p";
        if (sel.rangeCount > 0) {
          let node = sel.getRangeAt(0).startContainer;
          if (node.nodeType === 3) node = node.parentNode;
          while (node && node !== editorEl) {
            if (node.nodeType === 1) {
              const t = node.tagName.toLowerCase();
              if (/^(p|h[1-6])$/.test(t)) {
                tag = t;
                break;
              }
            }
            node = node.parentNode;
          }
        }
        headingSelect.value = tag;
      } catch (_) {}
    }

    // H1 增强：回填当前光标处颜色（避免用户正在选色时被打断）
    const colorInputs = toolbarEl.querySelectorAll(
      'input[type="color"][data-cmd]',
    );
    colorInputs.forEach((input) => {
      if (document.activeElement === input) return;
      try {
        const cmd = input.dataset.cmd;
        let rgb = "";
        if (cmd === "foreColor") {
          rgb = document.queryCommandValue("foreColor");
        } else if (cmd === "hiliteColor") {
          rgb =
            document.queryCommandValue("backColor") ||
            document.queryCommandValue("hiliteColor");
        }
        const hex = Utils.rgbToHex(rgb);
        if (hex) input.value = hex;
      } catch (_) {}
    });
  }

  global.McresEditorToolbar = {
    buildToolbar,
    updateToolbarState,
    TOOLBAR_GROUPS,
  };

  console.log("✅ McresEditorToolbar 已加载");
})(window);
