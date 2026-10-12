/**
 * McresEditor 富文本编辑器主类
 * 路径：mcres/static/js/lib/editor/editor.js
 *
 * 依赖（按此顺序加载）：
 *   1. editor-utils.js
 *   2. editor-toolbar.js
 *   3. editor-panels.js
 *   4. table.js（可选）
 *   5. editor.js（本文件）
 *
 * API 与旧版兼容：
 *   new McresEditor(container, initialData, placeholder)
 *   .getData() / .setData(html) / .destroy() / .focus()
 */
(function (global) {
  "use strict";

  const Utils = global.McresEditorUtils;
  const Toolbar = global.McresEditorToolbar;
  const Panels = global.McresEditorPanels;

  if (!Utils || !Toolbar || !Panels) {
    console.error("[McresEditor] 依赖未全部加载，请检查脚本顺序");
    return;
  }

  class McresEditor {
    constructor(container, initialData = "", placeholder = "在这里编写……") {
      if (!container) throw new Error("容器元素不能为空");
      this.container = container;
      this.placeholder = placeholder;
      this.initialData = initialData;

      this.editor = null;
      this.toolbar = null;
      this._headingSelect = null;

      // 浮动面板实例
      this._linkPanel = new Panels.LinkPanel();
      this._tablePanel = new Panels.TableMatrixPanel();

      // 状态
      this._ctrlPressed = false;
      this._hoveredLink = null;
      this._tooltip = null;
      this._hideTooltip = null;
      this._tableManager = null;

      // 事件清理句柄
      this._cleanups = [];
      this._selRaf = null;

      this._init();
    }

    _init() {
      this.container.innerHTML = "";
      this.container.className = "editor-wrapper";

      // 工具栏容器
      const toolbarEl = document.createElement("div");
      toolbarEl.className = "editor-toolbar";
      this.container.appendChild(toolbarEl);
      this.toolbar = toolbarEl;

      // 内容区
      const content = document.createElement("div");
      content.className = "editor-content";
      content.contentEditable = "true";
      content.dataset.placeholder = this.placeholder;
      this.container.appendChild(content);
      this.editor = content;

      // 链接悬停提示
      this._createTooltip();

      // 构建工具栏
      const handlers = {
        toggleBlockquote: () => this._toggleBlockquote(),
        createLink: (btn) => this._showLinkPanel(btn),
        insertTable: (btn) => this._showTableMatrix(btn),
        removeFormat: () => this._clearAllFormatting(),
      };
      const result = Toolbar.buildToolbar(toolbarEl, content, handlers);
      this._headingSelect = result.headingSelect;

      // 写入初始数据（走净化）
      if (this.initialData && this.initialData.trim()) {
        content.innerHTML = Utils.sanitizeHTML(this.initialData);
      }

      // 绑定事件
      this._bindEvents();

      // 初始化状态
      this._updateToolbarState();
      this._handleEmptyState();

      // 表格管理（可选）
      if (typeof global.TableManager !== "undefined") {
        this._tableManager = new global.TableManager(this);
        console.log("✅ TableManager 已加载");
      }

      console.log("✅ McresEditor 初始化完成");
    }

    _createTooltip() {
      const tip = document.createElement("div");
      tip.className = "mcres-link-tooltip";
      tip.style.cssText = `
                position: fixed;
                background: #1d2229;
                color: #e6edf3;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 12px;
                border: 1px solid #2b313b;
                box-shadow: 0 2px 8px rgba(0,0,0,0.5);
                pointer-events: none;
                z-index: 10003;
                display: none;
                max-width: 400px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                font-family: "Microsoft YaHei", sans-serif;
            `;
      document.body.appendChild(tip);
      this._tooltip = tip;
    }

    // ---------- 事件 ----------
    _bindEvents() {
      const editor = this.editor;
      const self = this;

      const on = (target, type, handler, opts) => {
        target.addEventListener(type, handler, opts);
        self._cleanups.push(() =>
          target.removeEventListener(type, handler, opts),
        );
      };

      // Ctrl 键状态（用于链接悬停提示）
      on(document, "keydown", (e) => {
        if (e.key === "Control") {
          self._ctrlPressed = true;
          if (self._hoveredLink) self._hoveredLink.style.cursor = "pointer";
        }
      });
      on(document, "keyup", (e) => {
        if (e.key === "Control") {
          self._ctrlPressed = false;
          if (self._hoveredLink) self._hoveredLink.style.cursor = "default";
        }
      });

      // H3 修复：selectionchange 用 rAF 防抖
      on(document, "selectionchange", () => {
        if (document.activeElement !== editor) return;
        if (self._selRaf) cancelAnimationFrame(self._selRaf);
        self._selRaf = requestAnimationFrame(() => {
          self._selRaf = null;
          self._updateToolbarState();
        });
      });

      // S2 修复：粘贴拦截
      on(editor, "paste", (e) => self._handlePaste(e));

      // 输入事件
      on(editor, "input", () => {
        self._updateToolbarState();
        self._handleEmptyState();
        editor.dispatchEvent(new CustomEvent("editor-change"));
      });

      // Tab 缩进
      on(editor, "keydown", function (e) {
        if (e.key === "Tab") {
          const sel = window.getSelection();
          if (sel.rangeCount) {
            const node = sel.getRangeAt(0).startContainer;
            const parent = node.nodeType === 3 ? node.parentElement : node;
            if (parent) {
              const listItem = parent.closest("li");
              if (listItem) {
                e.preventDefault();
                if (e.shiftKey) document.execCommand("outdent", false, null);
                else document.execCommand("indent", false, null);
                return;
              }
            }
          }
          if (!e.shiftKey) {
            e.preventDefault();
            document.execCommand("insertText", false, "    ");
          }
        }
        setTimeout(() => self._updateToolbarState(), 50);
      });

      on(editor, "focus", () => self._updateToolbarState());
      on(editor, "mouseup", () => self._updateToolbarState());

      // H2 修复：mousedown 放行 input/select
      on(this.toolbar, "mousedown", (e) => {
        const t = e.target;
        if (t.tagName === "INPUT" || t.tagName === "SELECT") return;
        e.preventDefault();
        editor.focus();
      });

      // 链接悬停提示
      on(editor, "mouseover", function (e) {
        const target = e.target.closest("a");
        if (target && target.href) {
          self._hoveredLink = target;
          target.style.cursor = self._ctrlPressed ? "pointer" : "default";
          const tip = self._tooltip;
          tip.textContent = target.href;
          tip.style.display = "block";
          const rect = target.getBoundingClientRect();
          let top = rect.bottom + 6;
          let left = rect.left;
          const tipWidth = tip.getBoundingClientRect().width || 200;
          if (top + 30 > window.innerHeight) top = rect.top - 30;
          if (left + tipWidth > window.innerWidth)
            left = window.innerWidth - tipWidth - 10;
          if (left < 10) left = 10;
          tip.style.top = top + "px";
          tip.style.left = left + "px";
        }
      });

      on(editor, "mouseout", function (e) {
        const target = e.target.closest("a");
        if (target) {
          self._hoveredLink = null;
          target.style.cursor = "default";
          if (self._tooltip) self._tooltip.style.display = "none";
        }
      });

      // Ctrl+点击打开链接
      on(editor, "click", function (e) {
        if (e.ctrlKey) {
          const target = e.target.closest("a");
          if (target && target.href) {
            e.preventDefault();
            e.stopPropagation();
            window.open(target.href, "_blank", "noopener,noreferrer");
          }
        }
      });

      // 滚动/窗口变化隐藏 tooltip
      const hideTooltip = () => {
        if (self._tooltip) self._tooltip.style.display = "none";
      };
      on(window, "scroll", hideTooltip, true);
      on(window, "resize", hideTooltip);
      this._hideTooltip = hideTooltip;
    }

    // ---------- S2：粘贴 ----------
    _handlePaste(e) {
      e.preventDefault();
      const clipboard = e.clipboardData || window.clipboardData;
      if (!clipboard) return;

      const html = clipboard.getData("text/html");
      const text = clipboard.getData("text/plain");

      // Shift+粘贴 或 只有纯文本：强制走纯文本
      if (e.shiftKey || !html) {
        if (text) document.execCommand("insertText", false, text);
        return;
      }

      // HTML 净化后插入
      const cleaned = Utils.sanitizeHTML(html);
      if (cleaned) {
        document.execCommand("insertHTML", false, cleaned);
      } else if (text) {
        document.execCommand("insertText", false, text);
      }

      this.editor.dispatchEvent(new Event("input", { bubbles: true }));
    }

    // ---------- H5：空状态 ----------
    _handleEmptyState() {
      const isEmpty = Utils.isEditorEmpty(this.editor);
      this.editor.classList.toggle("is-empty", isEmpty);
    }

    // ---------- 状态更新 ----------
    _updateToolbarState() {
      Toolbar.updateToolbarState(
        this.toolbar,
        this.editor,
        this._headingSelect,
      );
    }

    // ---------- 链接面板 ----------
    _showLinkPanel(button) {
      const editor = this.editor;
      const self = this;

      const sel = window.getSelection();
      let currentUrl = "";
      if (sel.rangeCount > 0) {
        const range = sel.getRangeAt(0);
        let node = range.startContainer;
        if (node.nodeType === 3) node = node.parentElement;
        const anchor = node && node.closest && node.closest("a");
        if (anchor) currentUrl = anchor.getAttribute("href") || "";
      }

      this._linkPanel.show({
        button,
        editorEl: editor,
        currentUrl,
        onConfirm: (url, savedRange) => {
          if (savedRange) {
            const s = window.getSelection();
            s.removeAllRanges();
            s.addRange(savedRange);
          }
          editor.focus();

          if (url) {
            document.execCommand("createLink", false, url);
            // 为新链接加 target/rel
            const s = window.getSelection();
            if (s.rangeCount > 0) {
              let node = s.getRangeAt(0).startContainer;
              if (node.nodeType === 3) node = node.parentElement;
              const link = node && node.closest && node.closest("a");
              if (link) {
                link.target = "_blank";
                link.rel = "noopener noreferrer";
              }
            }
          } else {
            document.execCommand("unlink", false, null);
          }

          self._updateToolbarState();
          editor.dispatchEvent(new Event("input", { bubbles: true }));
          editor.focus();
        },
        onCancel: (savedRange) => {
          if (savedRange) {
            const s = window.getSelection();
            s.removeAllRanges();
            s.addRange(savedRange);
          }
          editor.focus();
        },
      });
    }

    // ---------- 表格矩阵 ----------
    _showTableMatrix(button) {
      const self = this;
      this._tablePanel.show({
        button,
        onSelect: (rows, cols) => self._insertTable(rows, cols),
      });
    }

    // ---------- 插入表格 ----------
    _insertTable(rows, cols) {
      let html = "<table><tbody>";
      for (let i = 0; i < rows; i++) {
        html += "<tr>";
        for (let j = 0; j < cols; j++) {
          html += '<td style="text-align:center;"><br></td>';
        }
        html += "</tr>";
      }
      html += "</tbody></table><p><br></p>";

      document.execCommand("insertHTML", false, html);
      this.editor.focus();

      const table = this.editor.querySelector("table:last-of-type");
      if (table) {
        const firstTd = table.querySelector("td");
        if (firstTd) {
          const range = document.createRange();
          range.setStart(firstTd, 0);
          range.collapse(true);
          const sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }
      this.editor.dispatchEvent(new Event("input", { bubbles: true }));
      this._updateToolbarState();
    }

    // ---------- 引用切换 ----------
    _toggleBlockquote() {
      const editor = this.editor;
      const sel = window.getSelection();
      if (!sel.rangeCount) return;
      const range = sel.getRangeAt(0);
      let node = range.startContainer;
      if (node.nodeType === 3) node = node.parentElement;
      const blockquote = node.closest("blockquote");

      if (blockquote) {
        // 取消引用：拆成多个 p（保留段落结构）
        const parent = blockquote.parentNode;
        const frag = document.createDocumentFragment();
        const children = Array.from(blockquote.children);
        const hasBlockChildren = children.some((c) =>
          /^(P|DIV)$/.test(c.tagName),
        );

        if (!hasBlockChildren) {
          const p = document.createElement("p");
          while (blockquote.firstChild) p.appendChild(blockquote.firstChild);
          frag.appendChild(p);
        } else {
          children.forEach((child) => {
            if (/^(P|DIV)$/.test(child.tagName)) {
              const p = document.createElement("p");
              while (child.firstChild) p.appendChild(child.firstChild);
              frag.appendChild(p);
            } else {
              const p = document.createElement("p");
              p.appendChild(child.cloneNode(true));
              frag.appendChild(p);
            }
          });
        }
        parent.replaceChild(frag, blockquote);
      } else {
        document.execCommand("formatBlock", false, "<blockquote>");
      }
      editor.dispatchEvent(new Event("input", { bubbles: true }));
    }

    // ---------- 清除格式 ----------
    _clearAllFormatting() {
      const editor = this.editor;
      if (!editor) return;
      editor.focus();

      document.execCommand("removeFormat", false, null);

      const sel = window.getSelection();
      if (!sel.rangeCount) return;
      const range = sel.getRangeAt(0);

      // M1：折叠光标时，找到当前块级元素
      let commonAncestor = range.commonAncestorContainer;
      if (range.collapsed) {
        let node =
          commonAncestor.nodeType === 3
            ? commonAncestor.parentElement
            : commonAncestor;
        while (node && node !== editor) {
          if (
            /^(P|H[1-6]|DIV|BLOCKQUOTE|UL|OL|LI|PRE|TABLE|TD|TH)$/.test(
              node.tagName,
            )
          ) {
            commonAncestor = node;
            break;
          }
          node = node.parentNode;
        }
      }

      const blockTags = [
        "UL",
        "OL",
        "LI",
        "BLOCKQUOTE",
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "H6",
        "DIV",
        "SECTION",
        "ARTICLE",
      ];
      const nodesToReplace = [];
      const walker = document.createTreeWalker(
        commonAncestor,
        NodeFilter.SHOW_ELEMENT,
        {
          acceptNode: function (n) {
            if (blockTags.includes(n.tagName) && range.intersectsNode(n)) {
              return NodeFilter.FILTER_ACCEPT;
            }
            return NodeFilter.FILTER_SKIP;
          },
        },
      );

      let node;
      while ((node = walker.nextNode())) {
        if (!nodesToReplace.includes(node)) nodesToReplace.push(node);
      }

      if (nodesToReplace.length === 0) {
        this._updateToolbarState();
        return;
      }

      nodesToReplace.reverse().forEach((el) => {
        const p = document.createElement("p");
        while (el.firstChild) p.appendChild(el.firstChild);
        el.parentNode.replaceChild(p, el);
      });

      // M9：空 p 直接删除，不再塞 <br>
      editor.querySelectorAll("p:empty").forEach((p) => {
        if (!p.hasChildNodes()) p.remove();
      });

      editor.dispatchEvent(new Event("input", { bubbles: true }));
      this._updateToolbarState();
    }

    // ---------- 公开 API ----------

    /** S3：输出走净化 */
    getData() {
      return Utils.sanitizeHTML(this.editor.innerHTML);
    }

    /** S3：输入走净化 */
    setData(html) {
      this.editor.innerHTML = Utils.sanitizeHTML(html || "");
      this._handleEmptyState();
      this._updateToolbarState();
    }

    focus() {
      this.editor.focus();
    }

    destroy() {
      // 关闭面板
      if (this._linkPanel) this._linkPanel.destroy();
      if (this._tablePanel) this._tablePanel.destroy();

      // 移除 tooltip
      if (this._tooltip) {
        this._tooltip.remove();
        this._tooltip = null;
      }

      // 取消 pending rAF
      if (this._selRaf) {
        cancelAnimationFrame(this._selRaf);
        this._selRaf = null;
      }

      // 执行所有事件清理
      this._cleanups.forEach((fn) => {
        try {
          fn();
        } catch (_) {}
      });
      this._cleanups = [];

      // 表格管理
      if (
        this._tableManager &&
        typeof this._tableManager.destroy === "function"
      ) {
        this._tableManager.destroy();
      }

      this.container.innerHTML = "";
    }
  }

  global.McresEditor = McresEditor;
})(window);
