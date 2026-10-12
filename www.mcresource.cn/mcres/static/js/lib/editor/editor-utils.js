/**
 * McresEditor 工具函数
 * 路径：mcres/static/js/lib/editor/editor-utils.js
 *
 * 提供：
 *   - sanitizeHTML(html)     白名单净化
 *   - cleanStyle(str)         style 属性白名单清洗
 *   - normalizeUrl(url)       URL 规范化（含危险协议拒绝）
 *   - isUrlSafe(url)          URL 安全检查
 *   - escapeHtml(text)        HTML 转义
 *   - isEditorEmpty(el)       编辑器空状态检测
 *   - rgbToHex(rgb)           rgb 转 hex
 */
(function (global) {
  "use strict";

  // ============ 白名单 ============
  const ALLOWED_TAGS = new Set([
    "P",
    "BR",
    "DIV",
    "SPAN",
    "STRONG",
    "B",
    "EM",
    "I",
    "U",
    "S",
    "STRIKE",
    "DEL",
    "SUB",
    "SUP",
    "MARK",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "UL",
    "OL",
    "LI",
    "BLOCKQUOTE",
    "PRE",
    "CODE",
    "A",
    "IMG",
    "HR",
    "TABLE",
    "THEAD",
    "TBODY",
    "TFOOT",
    "TR",
    "TD",
    "TH",
  ]);

  const FORBIDDEN_TAGS = new Set([
    "SCRIPT",
    "STYLE",
    "IFRAME",
    "OBJECT",
    "EMBED",
    "FORM",
    "INPUT",
    "BUTTON",
    "TEXTAREA",
    "SELECT",
    "LINK",
    "META",
    "AUDIO",
    "VIDEO",
    "SOURCE",
    "CANVAS",
    "SVG",
  ]);

  const ALLOWED_ATTRS = {
    "*": ["style"],
    A: ["href", "title", "target", "rel"],
    IMG: ["src", "alt", "title", "width", "height"],
    TD: ["colspan", "rowspan", "align", "valign"],
    TH: ["colspan", "rowspan", "align", "valign"],
    TABLE: ["border", "cellpadding", "cellspacing"],
  };

  const ALLOWED_STYLE_PROPS = new Set([
    "color",
    "background-color",
    "font-weight",
    "font-style",
    "font-size",
    "font-family",
    "text-decoration",
    "text-align",
    "text-indent",
    "line-height",
    "margin",
    "margin-top",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "padding",
    "padding-top",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "width",
    "height",
    "border",
  ]);

  const SAFE_PROTOCOL_RE = /^(https?:|mailto:|tel:)/i;
  const ANCHOR_OR_RELATIVE_RE = /^(#|\/(?!\/))/;
  const DATA_IMAGE_RE = /^\s*data:image\//i;
  const HAS_PROTOCOL_RE = /^[a-z][a-z0-9+.-]*:/i;

  // ============ 文本工具 ============

  function escapeHtml(text) {
    if (text == null) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ============ URL 规范化 ============

  function normalizeUrl(url) {
    let u = String(url || "").trim();
    if (!u) return "";

    if (SAFE_PROTOCOL_RE.test(u)) return u;
    if (ANCHOR_OR_RELATIVE_RE.test(u)) return u;

    // 有协议头但不在白名单（含 javascript:、data: 等），拒绝
    if (HAS_PROTOCOL_RE.test(u)) return "";

    // 无协议，补 https
    return "https://" + u;
  }

  function isUrlSafe(url) {
    if (!url) return true;
    const u = String(url).trim();
    if (SAFE_PROTOCOL_RE.test(u)) return true;
    if (ANCHOR_OR_RELATIVE_RE.test(u)) return true;
    if (DATA_IMAGE_RE.test(u)) return true;
    return false;
  }

  // ============ Style 清洗 ============

  function cleanStyle(styleStr) {
    if (!styleStr) return "";
    const parts = styleStr
      .split(";")
      .map((s) => s.trim())
      .filter(Boolean);
    const out = [];
    parts.forEach((p) => {
      const idx = p.indexOf(":");
      if (idx < 0) return;
      const prop = p.slice(0, idx).trim().toLowerCase();
      const val = p.slice(idx + 1).trim();
      if (!ALLOWED_STYLE_PROPS.has(prop)) return;
      // 过滤 expression( ) 和 url(javascript:)
      if (/expression\s*\(/i.test(val)) return;
      if (/url\s*\(\s*['"]?\s*javascript:/i.test(val)) return;
      out.push(prop + ": " + val);
    });
    return out.join("; ");
  }

  // ============ HTML 净化 ============

  function sanitizeHTML(html) {
    if (!html) return "";

    const doc = new DOMParser().parseFromString(String(html), "text/html");
    const body = doc.body;

    function clean(node) {
      if (node.nodeType === 3) return; // 文本节点，保留
      if (node.nodeType !== 1) {
        // 注释、CDATA，删除
        node.remove();
        return;
      }

      const tag = node.tagName;

      // 危险标签直接删
      if (FORBIDDEN_TAGS.has(tag)) {
        node.remove();
        return;
      }

      // <font> 特殊处理：转成 <span style="...">
      if (tag === "FONT") {
        const span = doc.createElement("span");
        const color = node.getAttribute("color");
        const face = node.getAttribute("face");
        const size = node.getAttribute("size");
        const styles = [];
        if (color) styles.push("color: " + color);
        if (face) styles.push("font-family: " + face);
        if (size) {
          const sizeMap = {
            1: "10px",
            2: "13px",
            3: "16px",
            4: "18px",
            5: "24px",
            6: "32px",
            7: "48px",
          };
          if (sizeMap[size]) styles.push("font-size: " + sizeMap[size]);
        }
        if (styles.length) span.setAttribute("style", styles.join("; "));
        while (node.firstChild) span.appendChild(node.firstChild);
        node.parentNode.replaceChild(span, node);
        clean(span);
        return;
      }

      // 白名单外标签：unwrap（保留子节点）
      if (!ALLOWED_TAGS.has(tag)) {
        const frag = doc.createDocumentFragment();
        while (node.firstChild) frag.appendChild(node.firstChild);
        node.parentNode.replaceChild(frag, node);
        return;
      }

      // 清洗属性
      Array.from(node.attributes).forEach((attr) => {
        const name = attr.name.toLowerCase();
        // 事件属性一律删
        if (name.startsWith("on")) {
          node.removeAttribute(attr.name);
          return;
        }
        const allowAll = ALLOWED_ATTRS["*"] || [];
        const allowTag = ALLOWED_ATTRS[tag] || [];
        if (!allowAll.includes(name) && !allowTag.includes(name)) {
          node.removeAttribute(attr.name);
          return;
        }
        // style 白名单
        if (name === "style") {
          const cleaned = cleanStyle(attr.value);
          if (cleaned) node.setAttribute("style", cleaned);
          else node.removeAttribute("style");
        }
        // href/src 协议检查
        if (name === "href" || name === "src") {
          const v = attr.value.trim();
          if (name === "src" && DATA_IMAGE_RE.test(v)) return;
          if (!isUrlSafe(v)) {
            node.removeAttribute(attr.name);
          }
        }
      });

      // 递归
      Array.from(node.childNodes).forEach(clean);
    }

    Array.from(body.childNodes).forEach(clean);
    return body.innerHTML;
  }

  // ============ 空状态检测 ============

  function isEditorEmpty(editorEl) {
    if (!editorEl) return true;
    if (editorEl.textContent && editorEl.textContent.trim().length > 0)
      return false;
    if (editorEl.querySelector("img, table, hr")) return false;
    return true;
  }

  // ============ RGB → HEX ============

  function rgbToHex(rgb) {
    if (!rgb) return null;
    if (/^#[0-9a-f]{6}$/i.test(rgb)) return rgb.toLowerCase();
    const m = String(rgb).match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (!m) return null;
    const toHex = (n) => {
      const h = parseInt(n, 10).toString(16);
      return h.length === 1 ? "0" + h : h;
    };
    return "#" + toHex(m[1]) + toHex(m[2]) + toHex(m[3]);
  }

  global.McresEditorUtils = {
    escapeHtml,
    normalizeUrl,
    isUrlSafe,
    cleanStyle,
    sanitizeHTML,
    isEditorEmpty,
    rgbToHex,
    ALLOWED_TAGS,
    ALLOWED_STYLE_PROPS,
  };

  console.log("✅ McresEditorUtils 已加载");
})(window);
