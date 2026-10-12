/**
 * TableManager - Excel 风格表格编辑逻辑
 * 路径：mcres/static/js/lib/editor/table.js
 *
 * 状态机：idle → selected → editing
 * 支持：单元格选择/编辑、矩形多选、Excel 键盘导航、多格复制粘贴、
 *       多选右键批量操作（插入/删除多行多列、批量表头切换）
 */
(function (global) {
    "use strict";

    const IS_TOUCH = (function () {
        try { return window.matchMedia("(hover: none)").matches; }
        catch (_) { return "ontouchstart" in window; }
    })();

    const STATE = { IDLE: "idle", SELECTED: "selected", EDITING: "editing" };

    class TableManager {
        constructor(editorInstance) {
            this.editor = editorInstance.editor;
            this.container = editorInstance.container;
            this.toolbar = editorInstance.toolbar;

            // 状态机
            this._state = STATE.IDLE;
            this._activeCell = null;
            this._anchorCell = null;
            this._selectedCells = new Set();

            // 鼠标
            this._mouseDownCell = null;
            this._lastHoverCell = null;
            this._isDragging = false;
            this._lastRange = null;

            // editing 下的 mousedown 标记
            this._mouseDownInEditingSameCell = false;
            this._mouseDownInEditingOtherCell = false;

            // 菜单
            this._menu = null;

            // 清理
            this._cleanups = [];

            this._bindEvents();
            this._addStyles();
        }

        // ============================================================
        // 样式
        // ============================================================
        _addStyles() {
            const styleId = "mcres-table-style";
            if (document.getElementById(styleId)) return;
            const style = document.createElement("style");
            style.id = styleId;
            style.textContent = `
                .mcres-cell-selected { background: rgba(85, 216, 139, 0.10) !important; }
                .mcres-cell-active {
                    outline: 2px solid var(--editor-primary, #55d88b) !important;
                    outline-offset: -2px;
                    background: rgba(85, 216, 139, 0.06) !important;
                }
                .mcres-cell-editing {
                    outline: 2px solid var(--editor-primary, #55d88b) !important;
                    outline-offset: -2px;
                    background: var(--editor-bg, #11161c) !important;
                    caret-color: auto !important;
                }
                .editor-content.mcres-table-selected { caret-color: transparent; }
            `;
            document.head.appendChild(style);
        }

        // ============================================================
        // 事件
        // ============================================================
        _bindEvents() {
            const on = (target, type, handler, opts) => {
                target.addEventListener(type, handler, opts);
                this._cleanups.push(() => target.removeEventListener(type, handler, opts));
            };

            on(this.editor, "contextmenu", (e) => {
                const td = e.target.closest("td, th");
                if (td) {
                    e.preventDefault();
                    this._showMenu(e.clientX, e.clientY, td);
                } else {
                    this._hideMenu();
                }
            });

            on(document, "click", (e) => {
                if (this._menu && !this._menu.contains(e.target)) this._hideMenu();
            });

            on(this.editor, "mousedown", (e) => this._onMouseDown(e));
            on(document, "mousemove", (e) => this._onMouseMove(e));
            on(document, "mouseup", (e) => this._onMouseUp(e));
            on(this.editor, "dblclick", (e) => this._onDblClick(e));

            on(this.editor, "keydown", (e) => this._onKeyDown(e));
            on(this.editor, "copy", (e) => this._onCopy(e));
            on(this.editor, "cut", (e) => this._onCut(e));
            on(this.editor, "paste", (e) => this._onPaste(e));

            on(document, "mousedown", (e) => {
                if (!this.editor.contains(e.target)) {
                    if (this._state === STATE.EDITING) this._toSelected(this._activeCell);
                    else if (this._state === STATE.SELECTED) this._toIdle();
                }
            });
        }

        // ============================================================
        // 状态转换
        // ============================================================
        _toIdle() {
            this._exitEditMode();
            this._clearSelection();
            this._state = STATE.IDLE;
            this._activeCell = null;
            this._anchorCell = null;
            this.editor.classList.remove("mcres-table-selected");
        }

        _toSelected(cell) {
            if (!cell) return;
            this._exitEditMode();
            this._clearSelection(false);
            this._activeCell = cell;
            this._anchorCell = cell;
            this._selectedCells.add(cell);
            this._applyCellClasses();
            this._placeCaretAtEnd(cell);
            this._state = STATE.SELECTED;
            this.editor.classList.add("mcres-table-selected");
        }

        _toEditing(cell, selectAll = false) {
            if (!cell) return;
            if (!this._selectedCells.has(cell)) {
                this._clearSelection(false);
                this._selectedCells.add(cell);
                this._activeCell = cell;
                this._anchorCell = cell;
            }
            this._applyCellClasses();
            this.editor.classList.remove("mcres-table-selected");

            this._state = STATE.EDITING;
            this.editor.focus();

            const range = document.createRange();
            const sel = window.getSelection();
            range.selectNodeContents(cell);
            if (!selectAll) range.collapse(false);
            sel.removeAllRanges();
            sel.addRange(range);
        }

        _exitEditMode() {
            if (this._state === STATE.EDITING) {
                if (this._activeCell) this._activeCell.classList.remove("mcres-cell-editing");
                this.editor.classList.remove("mcres-table-selected");
            }
        }

        // ============================================================
        // 视觉
        // ============================================================
        _applyCellClasses() {
            this.editor
                .querySelectorAll(".mcres-cell-selected, .mcres-cell-active, .mcres-cell-editing")
                .forEach(el => el.classList.remove("mcres-cell-selected", "mcres-cell-active", "mcres-cell-editing"));

            this._selectedCells.forEach(cell => cell.classList.add("mcres-cell-selected"));
            if (this._activeCell) this._activeCell.classList.add("mcres-cell-active");
            if (this._state === STATE.EDITING && this._activeCell) {
                this._activeCell.classList.add("mcres-cell-editing");
            }
        }

        _placeCaretAtEnd(cell) {
            if (!cell) return;
            const range = document.createRange();
            range.selectNodeContents(cell);
            range.collapse(false);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            this.editor.focus();
        }

        // ============================================================
        // 鼠标
        // ============================================================
        _onMouseDown(e) {
            if (e.button === 2) return;
            const td = e.target.closest("td, th");

            if (!td) {
                if (!e.target.closest("table")) {
                    if (this._state !== STATE.IDLE) this._toIdle();
                }
                return;
            }

            // 统一记录起点，供拖动检测使用
            this._mouseDownCell = td;
            this._lastHoverCell = td;
            this._isDragging = false;
            this._mouseDownInEditingSameCell = false;
            this._mouseDownInEditingOtherCell = false;

            // editing 模式
            if (this._state === STATE.EDITING) {
                if (td === this._activeCell) {
                    // 点自己：让浏览器定位光标，不 preventDefault
                    this._mouseDownInEditingSameCell = true;
                    return;
                } else {
                    // 点别处：preventDefault 阻止光标跳过去
                    // 等 mouseup 决定：没拖动就切格
                    e.preventDefault();
                    this._mouseDownInEditingOtherCell = true;
                    return;
                }
            }

            // selected / idle
            e.preventDefault();

            const ctrl = e.ctrlKey || e.metaKey;
            const shift = e.shiftKey;

            if (shift && this._anchorCell) {
                this._selectRange(this._anchorCell, td);
            } else if (ctrl) {
                if (this._selectedCells.has(td)) {
                    this._selectedCells.delete(td);
                    td.classList.remove("mcres-cell-selected", "mcres-cell-active");
                } else {
                    this._selectedCells.add(td);
                }
                this._activeCell = td;
                this._anchorCell = td;
                this._applyCellClasses();
                this._placeCaretAtEnd(td);
                this._state = STATE.SELECTED;
                this.editor.classList.add("mcres-table-selected");
            } else {
                this._toSelected(td);
            }
        }

        _onMouseMove(e) {
            if (!this._mouseDownCell) return;

            if (!this._isDragging) {
                const rect = this._mouseDownCell.getBoundingClientRect();
                const dx = e.clientX - rect.left - rect.width / 2;
                const dy = e.clientY - rect.top - rect.height / 2;
                if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
                    this._isDragging = true;

                    // editing 下拖动 → 退出编辑，开始选择
                    if (this._state === STATE.EDITING) {
                        if (this._activeCell) {
                            this._activeCell.classList.remove("mcres-cell-editing");
                        }
                        this.editor.classList.remove("mcres-table-selected");
                        this._state = STATE.SELECTED;
                    }

                    this._clearSelection(false);
                    this._activeCell = this._mouseDownCell;
                    this._anchorCell = this._mouseDownCell;
                    this._selectedCells.add(this._mouseDownCell);
                    this._applyCellClasses();
                }
            }

            if (!this._isDragging) return;

            const td = document.elementFromPoint(e.clientX, e.clientY)?.closest("td, th");
            if (td && td !== this._lastHoverCell && td.closest("table") === this._mouseDownCell.closest("table")) {
                this._lastHoverCell = td;
                this._selectRange(this._mouseDownCell, td, true);
            }
        }

        _onMouseUp(e) {
            const mouseDownCell = this._mouseDownCell;
            const wasDragging = this._isDragging;
            const wasSameCell = this._mouseDownInEditingSameCell;
            const wasOtherCell = this._mouseDownInEditingOtherCell;

            this._mouseDownCell = null;
            this._lastHoverCell = null;
            this._isDragging = false;
            this._mouseDownInEditingSameCell = false;
            this._mouseDownInEditingOtherCell = false;

            if (wasDragging) return;
            if (wasSameCell) return;
            if (wasOtherCell && mouseDownCell) this._toSelected(mouseDownCell);
        }

        _onDblClick(e) {
            const td = e.target.closest("td, th");
            if (!td) return;
            e.preventDefault();
            this._toEditing(td, false);
        }

        // ============================================================
        // 选区
        // ============================================================
        _selectRange(anchorCell, targetCell, keepActive = false) {
            const table = anchorCell.closest("table");
            if (!table) return;

            const aRow = anchorCell.closest("tr");
            const tRow = targetCell.closest("tr");
            const minRow = Math.min(aRow.rowIndex, tRow.rowIndex);
            const maxRow = Math.max(aRow.rowIndex, tRow.rowIndex);
            const minCol = Math.min(anchorCell.cellIndex, targetCell.cellIndex);
            const maxCol = Math.max(anchorCell.cellIndex, targetCell.cellIndex);

            if (this._lastRange &&
                this._lastRange.minRow === minRow && this._lastRange.maxRow === maxRow &&
                this._lastRange.minCol === minCol && this._lastRange.maxCol === maxCol) {
                return;
            }

            this._selectedCells.forEach(c =>
                c.classList.remove("mcres-cell-selected", "mcres-cell-active")
            );
            this._selectedCells.clear();

            for (let r = minRow; r <= maxRow; r++) {
                const row = table.rows[r];
                if (!row) continue;
                for (let c = minCol; c <= maxCol; c++) {
                    const cell = row.cells[c];
                    if (cell) this._selectedCells.add(cell);
                }
            }

            if (!keepActive) this._activeCell = anchorCell;
            this._applyCellClasses();
            if (this._activeCell) this._placeCaretAtEnd(this._activeCell);

            this._lastRange = { minRow, maxRow, minCol, maxCol };
            this._state = STATE.SELECTED;
            this.editor.classList.add("mcres-table-selected");
        }

        _clearSelection(resetActive = true) {
            this._selectedCells.forEach(cell =>
                cell.classList.remove("mcres-cell-selected", "mcres-cell-active", "mcres-cell-editing")
            );
            this._selectedCells.clear();
            this._lastRange = null;
            if (resetActive) {
                this._activeCell = null;
                this._anchorCell = null;
            }
        }

        _getSelectionBounds() {
            if (this._selectedCells.size === 0) return null;
            let minRow = Infinity, maxRow = -Infinity;
            let minCol = Infinity, maxCol = -Infinity;
            this._selectedCells.forEach(cell => {
                const row = cell.closest("tr");
                if (!row) return;
                // 用 Array.from 显式获取索引，避免嵌套表格时 rowIndex 失效
                const parent = row.parentNode;
                const rows = Array.from(parent.children).filter(el => el.tagName === "TR");
                const rIdx = rows.indexOf(row);
                const cells = Array.from(row.children).filter(el =>
                    el.tagName === "TD" || el.tagName === "TH"
                );
                const cIdx = cells.indexOf(cell);
                if (rIdx < 0 || cIdx < 0) return;
                minRow = Math.min(minRow, rIdx);
                maxRow = Math.max(maxRow, rIdx);
                minCol = Math.min(minCol, cIdx);
                maxCol = Math.max(maxCol, cIdx);
            });
            if (minRow === Infinity) return null;
            return { minRow, maxRow, minCol, maxCol };
        }

        // ============================================================
        // 键盘
        // ============================================================
        _onKeyDown(e) {
            const table = this._activeCell && this._activeCell.closest("table");
            if (this._state === STATE.SELECTED && table) {
                if (this._handleSelectedKey(e, table)) return;
            } else if (this._state === STATE.EDITING) {
                if (this._handleEditingKey(e, table)) return;
            }
        }

        _handleSelectedKey(e, table) {
            const cell = this._activeCell;
            const key = e.key;

            if ((e.ctrlKey || e.metaKey) && key.toLowerCase() === "a") {
                e.preventDefault();
                this._selectAllInTable(table);
                return true;
            }
            if (key === "Escape") { e.preventDefault(); this._toIdle(); return true; }
            if (key === "F2") { e.preventDefault(); this._toEditing(cell, false); return true; }
            if (key === "Enter" && !e.altKey) {
                e.preventDefault();
                if (e.shiftKey) this._moveActive(-1, 0);
                else this._toEditing(cell, false);
                return true;
            }
            if (key === "Tab") {
                e.preventDefault();
                this._moveActive(0, e.shiftKey ? -1 : 1, true);
                return true;
            }
            if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(key)) {
                e.preventDefault();
                const dr = key === "ArrowDown" ? 1 : key === "ArrowUp" ? -1 : 0;
                const dc = key === "ArrowRight" ? 1 : key === "ArrowLeft" ? -1 : 0;
                if (e.shiftKey) this._extendActive(dr, dc);
                else this._moveActive(dr, dc);
                return true;
            }
            if (key === "Home") {
                e.preventDefault();
                const row = cell.closest("tr");
                const target = e.ctrlKey ? table.rows[0]?.cells[0] : row?.cells[0];
                if (target) this._toSelected(target);
                return true;
            }
            if (key === "End") {
                e.preventDefault();
                let target;
                if (e.ctrlKey) {
                    const lastRow = table.rows[table.rows.length - 1];
                    target = lastRow?.cells[lastRow.cells.length - 1];
                } else {
                    const row = cell.closest("tr");
                    target = row?.cells[row.cells.length - 1];
                }
                if (target) this._toSelected(target);
                return true;
            }
            if (key === "PageUp") {
                e.preventDefault();
                const target = table.rows[0]?.cells[cell.cellIndex];
                if (target) this._toSelected(target);
                return true;
            }
            if (key === "PageDown") {
                e.preventDefault();
                const lastRow = table.rows[table.rows.length - 1];
                const target = lastRow?.cells[cell.cellIndex];
                if (target) this._toSelected(target);
                return true;
            }
            if (key === "Delete" || key === "Backspace") {
                e.preventDefault();
                this._clearSelectedContent();
                return true;
            }
            if (key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
                e.preventDefault();
                cell.textContent = "";
                this._toEditing(cell, false);
                try { document.execCommand("insertText", false, key); }
                catch (_) { cell.textContent = key; }
                this.editor.dispatchEvent(new Event("input", { bubbles: true }));
                return true;
            }
            return false;
        }

        _handleEditingKey(e, table) {
            const cell = this._activeCell;
            const key = e.key;

            if (key === "Enter" && e.altKey) {
                e.preventDefault();
                try { document.execCommand("insertLineBreak"); }
                catch (_) { document.execCommand("insertHTML", false, "<br>"); }
                return true;
            }
            if (key === "Enter") {
                e.preventDefault();
                this._toSelected(cell);
                this._moveActive(e.shiftKey ? -1 : 1, 0);
                return true;
            }
            if (key === "Tab") {
                e.preventDefault();
                this._toSelected(cell);
                this._moveActive(0, e.shiftKey ? -1 : 1, true);
                return true;
            }
            if (key === "Escape") {
                e.preventDefault();
                this._toSelected(cell);
                return true;
            }
            return false;
        }

        _moveActive(dr, dc, wrapRow = false) {
            const cell = this._activeCell;
            if (!cell) return;
            const table = cell.closest("table");
            if (!table) return;

            const row = cell.closest("tr");
            let targetRow = row.rowIndex;
            let targetCol = cell.cellIndex;

            if (dc !== 0) {
                targetCol += dc;
                const currentRowCells = row.cells;
                if (targetCol >= currentRowCells.length) {
                    if (wrapRow) {
                        targetRow += 1;
                        targetCol = 0;
                        if (targetRow >= table.rows.length) {
                            this._appendRow(table);
                            return;
                        }
                    } else {
                        targetCol = currentRowCells.length - 1;
                    }
                } else if (targetCol < 0) {
                    if (wrapRow) {
                        targetRow -= 1;
                        if (targetRow < 0) {
                            targetRow = 0;
                            targetCol = 0;
                        } else {
                            targetCol = table.rows[targetRow].cells.length - 1;
                        }
                    } else {
                        targetCol = 0;
                    }
                }
            }

            if (dr !== 0) {
                targetRow += dr;
                if (targetRow < 0) targetRow = 0;
                if (targetRow >= table.rows.length) targetRow = table.rows.length - 1;
            }

            const targetRowEl = table.rows[targetRow];
            if (!targetRowEl) return;
            if (targetCol >= targetRowEl.cells.length) targetCol = targetRowEl.cells.length - 1;
            if (targetCol < 0) targetCol = 0;
            const target = targetRowEl.cells[targetCol];
            if (target) this._toSelected(target);
        }

        _extendActive(dr, dc) {
            const cell = this._activeCell;
            if (!cell) return;
            const table = cell.closest("table");
            const row = cell.closest("tr");
            if (!table || !row) return;

            let targetRow = row.rowIndex + dr;
            let targetCol = cell.cellIndex + dc;
            if (targetRow < 0) targetRow = 0;
            if (targetRow >= table.rows.length) targetRow = table.rows.length - 1;
            const targetRowEl = table.rows[targetRow];
            if (!targetRowEl) return;
            if (targetCol < 0) targetCol = 0;
            if (targetCol >= targetRowEl.cells.length) targetCol = targetRowEl.cells.length - 1;

            const targetCell = targetRowEl.cells[targetCol];
            if (targetCell) {
                if (!this._anchorCell) this._anchorCell = cell;
                this._selectRange(this._anchorCell, targetCell, false);
            }
        }

        _selectAllInTable(table) {
            this._clearSelection(false);
            let firstCell = null;
            for (let r = 0; r < table.rows.length; r++) {
                const row = table.rows[r];
                for (let c = 0; c < row.cells.length; c++) {
                    const cell = row.cells[c];
                    this._selectedCells.add(cell);
                    if (!firstCell) firstCell = cell;
                }
            }
            this._activeCell = firstCell;
            this._anchorCell = firstCell;
            this._applyCellClasses();
            if (firstCell) this._placeCaretAtEnd(firstCell);
            this._state = STATE.SELECTED;
            this.editor.classList.add("mcres-table-selected");
        }

        _clearSelectedContent() {
            if (this._selectedCells.size === 0) return;
            this._selectedCells.forEach(cell => { cell.innerHTML = ""; });
            this.editor.dispatchEvent(new Event("input", { bubbles: true }));
        }

        // ============================================================
        // 复制 / 剪切 / 粘贴
        // ============================================================
        _onCopy(e) {
            if (this._selectedCells.size <= 1) return;
            const table = this._activeCell && this._activeCell.closest("table");
            if (!table) return;

            const bounds = this._getSelectionBounds();
            if (!bounds) return;

            e.preventDefault();

            const tsv = [];
            const htmlRows = [];
            for (let r = bounds.minRow; r <= bounds.maxRow; r++) {
                const row = table.rows[r];
                if (!row) continue;
                const texts = [];
                const cells = [];
                for (let c = bounds.minCol; c <= bounds.maxCol; c++) {
                    const cell = row.cells[c];
                    if (cell) {
                        texts.push(cell.textContent.replace(/\u00a0/g, " "));
                        cells.push(`<td>${cell.innerHTML || ""}</td>`);
                    } else {
                        texts.push("");
                        cells.push("<td></td>");
                    }
                }
                tsv.push(texts.join("\t"));
                htmlRows.push(`<tr>${cells.join("")}</tr>`);
            }

            if (e.clipboardData) {
                e.clipboardData.setData("text/plain", tsv.join("\n"));
                e.clipboardData.setData("text/html", `<table><tbody>${htmlRows.join("")}</tbody></table>`);
            }
        }

        _onCut(e) {
            if (this._selectedCells.size <= 1) return;
            this._onCopy(e);
            this._clearSelectedContent();
        }

        _onPaste(e) {
            const clipboard = e.clipboardData || window.clipboardData;
            if (!clipboard) return;

            const text = clipboard.getData("text/plain") || "";
            if (!text) return;
            if (text.indexOf("\t") === -1 && text.indexOf("\n") === -1) return;

            let cell = this._activeCell;
            if (!cell || !cell.closest("table")) return;

            if (this._state === STATE.EDITING) this._toSelected(cell);

            e.preventDefault();

            const table = cell.closest("table");
            const lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
            while (lines.length > 1 && lines[lines.length - 1] === "") lines.pop();
            const rows = lines.map(line => line.split("\t"));

            const startRow = cell.closest("tr").rowIndex;
            const startCol = cell.cellIndex;

            for (let r = 0; r < rows.length; r++) {
                const targetRowIdx = startRow + r;
                if (targetRowIdx >= table.rows.length) {
                    this._appendRow(table);
                }
                const rowEl = table.rows[targetRowIdx];
                if (!rowEl) continue;
                for (let c = 0; c < rows[r].length; c++) {
                    const targetColIdx = startCol + c;
                    if (targetColIdx >= rowEl.cells.length) break;
                    const targetCell = rowEl.cells[targetColIdx];
                    if (targetCell) targetCell.textContent = rows[r][c];
                }
            }

            this.editor.dispatchEvent(new Event("input", { bubbles: true }));
        }

        // ============================================================
        // 行列操作（用元素引用，避免索引错位）
        // ============================================================
        _appendRow(table) {
            const tbody = table.querySelector("tbody") || table;
            const lastRow = tbody.rows[tbody.rows.length - 1];
            if (!lastRow) return;
            const newRow = tbody.insertRow(tbody.rows.length);
            const colCount = lastRow.cells.length;
            for (let i = 0; i < colCount; i++) {
                const cell = newRow.insertCell(i);
                cell.innerHTML = "<br>";
                cell.style.textAlign = "center";
            }
            return newRow;
        }

        /**
         * 相对 refRow 插入 count 行
         * @param {HTMLTableElement} table
         * @param {HTMLElement} refRow    参考行（table 级索引解析后的元素）
         * @param {string} position       'before' | 'after'
         * @param {number} count
         */
        _insertRowsRelativeTo(table, refRow, position, count) {
            if (!refRow || !refRow.parentNode) return;
            const parent = refRow.parentNode;   // tbody 或 table
            const colCount = refRow.cells.length;

            // 计算插入锚点
            // before: 每次插到 refRow 前面
            // after:  每次插到 refRow 之后（先取 nextSibling 快照）
            const anchor = position === "before" ? refRow : refRow.nextSibling;

            for (let i = 0; i < count; i++) {
                const newRow = document.createElement("tr");
                for (let c = 0; c < colCount; c++) {
                    const cell = document.createElement("td");
                    cell.innerHTML = "<br>";
                    cell.style.textAlign = "center";
                    newRow.appendChild(cell);
                }
                parent.insertBefore(newRow, anchor);
            }
        }

        _deleteRowsByRefs(rows) {
            const table = rows[0] && rows[0].closest("table");
            if (!table) return;
            const totalRows = table.rows.length;
            if (totalRows - rows.length < 1) {
                Toast.warning("表格至少保留一行");
                return;
            }
            rows.forEach(row => {
                if (row && row.parentNode) row.parentNode.removeChild(row);
            });
        }

        _insertColsAt(table, atIndex, count) {
            const rows = Array.from(table.rows);
            rows.forEach(row => {
                // 用 cellIndex 定位（同一行内的 cells 索引稳定）
                for (let i = 0; i < count; i++) {
                    const cell = row.insertCell(atIndex);
                    cell.innerHTML = "<br>";
                    cell.style.textAlign = "center";
                }
            });
        }

        _deleteColsRange(table, minCol, maxCol) {
            const rows = Array.from(table.rows);
            if (rows.length === 0) return;
            const totalCols = rows[0].cells.length;
            if (totalCols - (maxCol - minCol + 1) < 1) {
                Toast.warning("表格至少保留一列");
                return;
            }
            rows.forEach(row => {
                for (let c = maxCol; c >= minCol; c--) {
                    if (c < row.cells.length) row.deleteCell(c);
                }
            });
        }

        /**
         * 表头切换（支持多行范围）
         */
        _setHeaderRange(table, minRow, maxRow, enable) {
            const rows = Array.from(table.rows).slice(minRow, maxRow + 1);
            const mapping = new Map();

            rows.forEach(row => {
                const cells = Array.from(row.cells);
                cells.forEach(cell => {
                    const newCell = document.createElement(enable ? "th" : "td");
                    newCell.innerHTML = cell.innerHTML || "<br>";
                    if (cell.className) newCell.className = cell.className;
                    if (cell.style.cssText) newCell.style.cssText = cell.style.cssText;
                    newCell.style.textAlign = "center";
                    cell.parentNode.replaceChild(newCell, cell);
                    mapping.set(cell, newCell);
                });
            });

            // 重建引用
            const newSelected = new Set();
            this._selectedCells.forEach(cell => newSelected.add(mapping.get(cell) || cell));
            this._selectedCells = newSelected;

            if (this._activeCell && mapping.has(this._activeCell)) {
                this._activeCell = mapping.get(this._activeCell);
            }
            if (this._anchorCell && mapping.has(this._anchorCell)) {
                this._anchorCell = mapping.get(this._anchorCell);
            }

            this._lastRange = null;
            this._applyCellClasses();
        }

        // ============================================================
        // 右键菜单
        // ============================================================
        _showMenu(x, y, td) {
            this._hideMenu();

            // 右键点未选中格：先选中它
            if (!this._selectedCells.has(td)) {
                this._toSelected(td);
            }

            const menu = document.createElement("div");
            menu.className = "mcres-table-menu";
            menu.style.cssText = `
                position: fixed;
                left: ${x}px; top: ${y}px;
                background: #1d2229;
                border: 1px solid #2b313b;
                border-radius: 8px;
                padding: 6px 0;
                min-width: 200px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.6);
                z-index: 10004;
                color: #e6edf3;
                font-size: 13px;
                font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            `;
            menu._td = td;

            const self = this;
            const bounds = this._getSelectionBounds();
            const multi = this._selectedCells.size > 1;
            const rowCount = multi && bounds ? (bounds.maxRow - bounds.minRow + 1) : 1;
            const colCount = multi && bounds ? (bounds.maxCol - bounds.minCol + 1) : 1;

            const rowLabel = (label) => multi && rowCount > 1 ? `${label} (${rowCount} 行)` : label;
            const colLabel = (label) => multi && colCount > 1 ? `${label} (${colCount} 列)` : label;

            const items = [];

            const rowSub = this._createSubMenu("行操作", [
                { label: rowLabel("上方插入行"), action: "insertRowAbove" },
                { label: rowLabel("下方插入行"), action: "insertRowBelow" },
                { label: rowLabel("删除选中行"), action: "deleteRow" },
                { label: "设置为表头", action: "setHeader" },
                { label: "取消表头", action: "clearHeader" }
            ]);
            items.push({ type: "sub", element: rowSub });

            const colSub = this._createSubMenu("列操作", [
                { label: colLabel("左侧插入列"), action: "insertColLeft" },
                { label: colLabel("右侧插入列"), action: "insertColRight" },
                { label: colLabel("删除选中列"), action: "deleteCol" }
            ]);
            items.push({ type: "sub", element: colSub });

            items.push({ type: "item", label: "✏️ 多单元格编辑", action: "multiEdit" });
            items.push({ type: "item", label: "🗑️ 删除表格", action: "deleteTable" });
            items.push({ type: "item", label: "🧹 清除选中", action: "clearSelect" });

            items.forEach(item => {
                if (item.type === "sub") {
                    menu.appendChild(item.element);
                } else {
                    const div = document.createElement("div");
                    div.textContent = item.label;
                    div.style.cssText = `padding: 6px 16px; cursor: pointer; transition: background 0.1s;`;
                    div.addEventListener("mouseenter", () => { div.style.background = "#2b313b"; });
                    div.addEventListener("mouseleave", () => { div.style.background = "transparent"; });
                    div.addEventListener("click", (e) => {
                        e.stopPropagation();
                        self._executeAction(item.action, td);
                        self._hideMenu();
                    });
                    menu.appendChild(div);
                }
            });

            document.body.appendChild(menu);
            this._menu = menu;

            const rect = menu.getBoundingClientRect();
            if (rect.right > window.innerWidth) menu.style.left = window.innerWidth - rect.width - 10 + "px";
            if (rect.bottom > window.innerHeight) menu.style.top = window.innerHeight - rect.height - 10 + "px";
        }

        _createSubMenu(label, items) {
            const container = document.createElement("div");
            container.style.cssText = `
                position: relative;
                padding: 6px 16px;
                cursor: pointer;
                transition: background 0.1s;
                display: flex;
                justify-content: space-between;
                align-items: center;
            `;
            container.innerHTML = `<span>${label}</span><span style="margin-left:20px;opacity:0.5;">▶</span>`;

            const subMenu = document.createElement("div");
            subMenu.style.cssText = `
                position: absolute;
                left: 100%; top: -6px;
                background: #1d2229;
                border: 1px solid #2b313b;
                border-radius: 8px;
                padding: 6px 0;
                min-width: 160px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.6);
                display: none;
                z-index: 10005;
            `;

            const self = this;
            items.forEach(item => {
                const div = document.createElement("div");
                div.textContent = item.label;
                div.style.cssText = `padding: 6px 16px; cursor: pointer; transition: background 0.1s; white-space: nowrap;`;
                div.addEventListener("mouseenter", () => { div.style.background = "#2b313b"; });
                div.addEventListener("mouseleave", () => { div.style.background = "transparent"; });
                div.addEventListener("click", (e) => {
                    e.stopPropagation();
                    const parentMenu = container.closest(".mcres-table-menu");
                    const td = parentMenu ? parentMenu._td : null;
                    if (td) {
                        self._executeAction(item.action, td);
                        self._hideMenu();
                    }
                });
                subMenu.appendChild(div);
            });

            container.appendChild(subMenu);

            if (!IS_TOUCH) {
                container.addEventListener("mouseenter", () => { subMenu.style.display = "block"; });
                container.addEventListener("mouseleave", () => { subMenu.style.display = "none"; });
            }
            container.addEventListener("click", (e) => {
                e.stopPropagation();
                if (IS_TOUCH) {
                    subMenu.style.display = subMenu.style.display === "block" ? "none" : "block";
                }
            });

            return container;
        }

        _hideMenu() {
            if (this._menu) {
                this._menu.remove();
                this._menu = null;
            }
        }

        // ============================================================
        // 执行动作（作用于整个选区）
        // ============================================================
        _executeAction(action, td) {
            const table = td.closest("table");
            if (!table) return;

            // 计算作用范围
            let bounds = this._getSelectionBounds();
            if (!bounds) {
                // 退化：只用 td 那一格
                const row = td.closest("tr");
                const parent = row.parentNode;
                const rows = Array.from(parent.children).filter(el => el.tagName === "TR");
                const rIdx = rows.indexOf(row);
                const cells = Array.from(row.children).filter(el =>
                    el.tagName === "TD" || el.tagName === "TH"
                );
                const cIdx = cells.indexOf(td);
                bounds = { minRow: rIdx, maxRow: rIdx, minCol: cIdx, maxCol: cIdx };
            }

            const rowCount = bounds.maxRow - bounds.minRow + 1;
            const colCount = bounds.maxCol - bounds.minCol + 1;

            // 解析 refRow 元素（避免依赖 table.rows 的索引语义）
            const allRows = Array.from(table.rows);
            const minRowEl = allRows[bounds.minRow];
            const maxRowEl = allRows[bounds.maxRow];

            switch (action) {
                case "multiEdit":
                    this._showMultiEditModal();
                    return;

                case "insertRowAbove":
                    if (!minRowEl) return;
                    this._insertRowsRelativeTo(table, minRowEl, "before", rowCount);
                    break;

                case "insertRowBelow":
                    if (!maxRowEl) return;
                    this._insertRowsRelativeTo(table, maxRowEl, "after", rowCount);
                    break;

                case "deleteRow": {
                    const rowsToDelete = allRows.slice(bounds.minRow, bounds.maxRow + 1);
                    this._deleteRowsByRefs(rowsToDelete);
                    // 删除后选中状态作废
                    this._toIdle();
                    break;
                }

                case "insertColLeft":
                    this._insertColsAt(table, bounds.minCol, colCount);
                    break;

                case "insertColRight":
                    this._insertColsAt(table, bounds.maxCol + 1, colCount);
                    break;

                case "deleteCol":
                    this._deleteColsRange(table, bounds.minCol, bounds.maxCol);
                    this._toIdle();
                    break;

                case "setHeader":
                    this._setHeaderRange(table, bounds.minRow, bounds.maxRow, true);
                    break;

                case "clearHeader":
                    this._setHeaderRange(table, bounds.minRow, bounds.maxRow, false);
                    break;

                case "deleteTable":
                    if (confirm("确定要删除整个表格吗？")) table.remove();
                    break;

                case "clearSelect":
                    this._toIdle();
                    return;
            }

            this.editor.dispatchEvent(new Event("input", { bubbles: true }));
            this.editor.focus();
        }

        // ============================================================
        // 多单元格编辑
        // ============================================================
        _showMultiEditModal() {
            if (this._selectedCells.size < 2) {
                Toast.warning("请先选中多个单元格");
                return;
            }

            const self = this;
            const modal = document.createElement("div");
            modal.style.cssText = `
                position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0,0,0,0.6);
                display: flex; align-items: center; justify-content: center;
                z-index: 10006;
            `;

            const box = document.createElement("div");
            box.style.cssText = `
                background: #1d2229; padding: 30px; border-radius: 16px;
                min-width: 320px; max-width: 500px; color: #e6edf3;
                font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            `;
            box.innerHTML = `
                <h3 style="margin-bottom:12px;">✏️ 批量编辑单元格</h3>
                <p style="color:rgba(255,255,255,0.6); margin-bottom:16px;">输入内容将应用到选中的 <strong>${this._selectedCells.size}</strong> 个单元格</p>
                <textarea id="multiEditInput" style="width:100%;padding:10px;background:#11161c;border:1px solid #2b313b;border-radius:8px;color:#e6edf3;font-size:14px;resize:vertical;min-height:60px;outline:none;font-family:inherit;"></textarea>
                <p style="color:rgba(255,255,255,0.35);font-size:12px;margin-top:8px;">Esc 取消 · Ctrl+Enter 确认</p>
                <div style="display:flex;gap:12px;justify-content:flex-end;margin-top:16px;">
                    <button id="multiEditCancel" style="padding:8px 20px;background:#3b434d;border:none;border-radius:8px;color:#fff;cursor:pointer;">取消</button>
                    <button id="multiEditConfirm" style="padding:8px 20px;background:var(--editor-primary,#55d88b);border:none;border-radius:8px;color:#111;cursor:pointer;font-weight:600;">确认</button>
                </div>
            `;
            modal.appendChild(box);
            document.body.appendChild(modal);

            const input = box.querySelector("#multiEditInput");
            const cancelBtn = box.querySelector("#multiEditCancel");
            const confirmBtn = box.querySelector("#multiEditConfirm");

            const close = () => {
                document.removeEventListener("keydown", onKeyDown, true);
                modal.remove();
            };
            const confirm = () => {
                const val = input.value;
                self._selectedCells.forEach(cell => { cell.textContent = val; });
                self.editor.dispatchEvent(new Event("input", { bubbles: true }));
                close();
            };
            const onKeyDown = (e) => {
                if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
                else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); e.stopPropagation(); confirm(); }
            };

            cancelBtn.addEventListener("click", close);
            confirmBtn.addEventListener("click", confirm);
            modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
            document.addEventListener("keydown", onKeyDown, true);

            input.focus();
        }

        // ============================================================
        // 销毁
        // ============================================================
        destroy() {
            this._hideMenu();
            this._toIdle();
            this._cleanups.forEach(fn => { try { fn(); } catch (_) {} });
            this._cleanups = [];
        }
    }

    global.TableManager = TableManager;
})(window);