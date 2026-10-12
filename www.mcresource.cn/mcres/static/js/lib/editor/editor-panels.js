/**
 * McresEditor 浮动面板
 * 路径：mcres/static/js/lib/editor/editor-panels.js
 *
 * 提供：
 *   - LinkPanel          链接输入面板
 *   - TableMatrixPanel   表格行列矩阵选择器
 */
(function (global) {
  "use strict";

  const Utils = global.McresEditorUtils;
  if (!Utils) {
    console.error("[McresEditorPanels] 缺少 McresEditorUtils");
    return;
  }

  // ============================================================
  // 链接面板
  // ============================================================
  class LinkPanel {
    constructor() {
      this.el = null;
      this._closeHandler = null;
    }

    /**
     * @param {Object} opts
     *   - button      触发按钮
     *   - editorEl    编辑器元素
     *   - currentUrl  已有链接（可选）
     *   - onConfirm(url, savedRange)
     *   - onCancel(savedRange)
     */
    show(opts) {
      this.close();

      const { button, editorEl, currentUrl, onConfirm, onCancel } = opts;

      // 保存当前选区
      const sel = window.getSelection();
      let savedRange = null;
      if (sel.rangeCount > 0) {
        savedRange = sel.getRangeAt(0).cloneRange();
      }

      // 定位
      let left, top;
      if (savedRange && !savedRange.collapsed) {
        const rect = savedRange.getBoundingClientRect();
        left = rect.left;
        top = rect.bottom + 6;
        if (top + 60 > window.innerHeight) top = rect.top - 60;
      } else {
        const btnRect = button.getBoundingClientRect();
        left = btnRect.left;
        top = btnRect.bottom + 6;
      }
      if (left + 320 > window.innerWidth) left = window.innerWidth - 320;
      if (left < 10) left = 10;

      const panel = document.createElement("div");
      panel.className = "mcres-link-panel";
      panel.style.cssText = `
                position: fixed;
                left: ${left}px;
                top: ${top}px;
                background: #1d2229;
                border: 1px solid #2b313b;
                border-radius: 8px;
                padding: 12px 16px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.6);
                z-index: 10002;
                display: flex;
                align-items: center;
                gap: 10px;
                flex-wrap: wrap;
                font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            `;

      const input = document.createElement("input");
      input.type = "url";
      input.placeholder = "输入链接地址 (http:// 或 https://)";
      input.value = currentUrl || "";
      input.style.cssText = `
                flex: 1;
                min-width: 180px;
                padding: 6px 10px;
                background: #11161c;
                border: 1px solid #2b313b;
                border-radius: 4px;
                color: #e6edf3;
                font-size: 14px;
                outline: none;
            `;
      setTimeout(() => input.focus(), 50);

      const confirmBtn = document.createElement("button");
      confirmBtn.textContent = "✓ 确认";
      confirmBtn.style.cssText = `
                padding: 6px 16px;
                background: var(--editor-primary, #55d88b);
                color: #111;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-weight: 600;
            `;

      const cancelBtn = document.createElement("button");
      cancelBtn.textContent = "✕";
      cancelBtn.style.cssText = `
                padding: 6px 10px;
                background: transparent;
                color: #8b949e;
                border: none;
                cursor: pointer;
                font-size: 16px;
            `;

      const doConfirm = () => {
        const rawUrl = input.value.trim();
        const url = Utils.normalizeUrl(rawUrl);
        this.close();
        if (onConfirm) onConfirm(url, savedRange);
      };

      const doCancel = () => {
        this.close();
        if (onCancel) onCancel(savedRange);
      };

      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          doConfirm();
        } else if (e.key === "Escape") {
          e.preventDefault();
          doCancel();
        }
      });

      confirmBtn.addEventListener("click", doConfirm);
      cancelBtn.addEventListener("click", doCancel);

      panel.appendChild(input);
      panel.appendChild(confirmBtn);
      panel.appendChild(cancelBtn);
      document.body.appendChild(panel);
      this.el = panel;

      // 点击外部关闭
      setTimeout(() => {
        this._closeHandler = (e) => {
          if (!panel.contains(e.target) && e.target !== button) {
            doCancel();
          }
        };
        document.addEventListener("click", this._closeHandler);
      }, 10);
    }

    close() {
      if (this._closeHandler) {
        document.removeEventListener("click", this._closeHandler);
        this._closeHandler = null;
      }
      if (this.el) {
        this.el.remove();
        this.el = null;
      }
    }

    destroy() {
      this.close();
    }
  }

  // ============================================================
  // 表格矩阵选择器
  // ============================================================
  class TableMatrixPanel {
    constructor() {
      this.el = null;
      this._closeHandler = null;
    }

    /**
     * @param {Object} opts
     *   - button
     *   - rows   最大行数（默认 10）
     *   - cols   最大列数（默认 10）
     *   - onSelect(rows, cols)
     */
    show(opts) {
      this.close();

      const { button, onSelect } = opts;
      const rows = opts.rows || 10;
      const cols = opts.cols || 10;
      const cellSize = 28;
      const gap = 2;

      const panel = document.createElement("div");
      panel.className = "mcres-table-matrix";
      panel.style.cssText = `
                position: fixed;
                background: #1d2229;
                border: 1px solid #2b313b;
                border-radius: 8px;
                padding: 10px;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
                z-index: 10002;
                user-select: none;
                font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            `;

      const grid = document.createElement("div");
      grid.style.cssText = `
                display: grid;
                grid-template-columns: repeat(${cols}, ${cellSize}px);
                grid-template-rows: repeat(${rows}, ${cellSize}px);
                gap: ${gap}px;
            `;

      const info = document.createElement("div");
      info.style.cssText = `
                color: #8b949e;
                font-size: 12px;
                text-align: center;
                padding-top: 8px;
                min-height: 20px;
            `;
      info.textContent = "悬停选择行列，点击生成表格";

      const cells = [];

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const cell = document.createElement("div");
          cell.dataset.row = r;
          cell.dataset.col = c;
          cell.style.cssText = `
                        background: #2b313b;
                        border-radius: 2px;
                        cursor: pointer;
                        transition: background 0.1s;
                    `;
          cell.addEventListener("mouseenter", () => {
            cells.forEach((cc) => {
              const rr = parseInt(cc.dataset.row);
              const cc2 = parseInt(cc.dataset.col);
              if (rr <= r && cc2 <= c) {
                cc.style.background = "var(--editor-primary, #55d88b)";
              } else {
                cc.style.background = "#2b313b";
              }
            });
            info.textContent = r + 1 + " × " + (c + 1) + " 表格";
          });
          cell.addEventListener("click", () => {
            this.close();
            if (onSelect) onSelect(r + 1, c + 1);
          });
          grid.appendChild(cell);
          cells.push(cell);
        }
      }

      panel.appendChild(grid);
      panel.appendChild(info);

      // 定位
      const rect = button.getBoundingClientRect();
      let left = rect.left;
      let top = rect.bottom + 6;
      const panelW = cols * (cellSize + gap) + 20;
      const panelH = rows * (cellSize + gap) + 50;
      if (top + panelH > window.innerHeight) top = rect.top - panelH;
      if (left + panelW > window.innerWidth) left = window.innerWidth - panelW;
      panel.style.left = left + "px";
      panel.style.top = top + "px";

      document.body.appendChild(panel);
      this.el = panel;

      setTimeout(() => {
        this._closeHandler = (e) => {
          if (!panel.contains(e.target) && e.target !== button) {
            this.close();
          }
        };
        document.addEventListener("click", this._closeHandler);
      }, 10);
    }

    close() {
      if (this._closeHandler) {
        document.removeEventListener("click", this._closeHandler);
        this._closeHandler = null;
      }
      if (this.el) {
        this.el.remove();
        this.el = null;
      }
    }

    destroy() {
      this.close();
    }
  }

  global.McresEditorPanels = {
    LinkPanel,
    TableMatrixPanel,
  };

  console.log("✅ McresEditorPanels 已加载");
})(window);
