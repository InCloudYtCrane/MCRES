// mcres/static/js/pages/resource/edit.js
// 三个资源编辑页（resourcepack / shaderpack / map）的公共逻辑。
// 包含：裁剪弹窗、Tab 切换、作者/下载链接管理、封面上传、截图上传、脏数据检测、提交模态框、规则加载。
// Toast 由 /static/js/components/toast.js 提供。
(function () {
  "use strict";

  // ============================================================
  // 裁剪模态框
  // ============================================================
  const modal = document.getElementById("cropModal");
  const cropImage = document.getElementById("cropImage");
  const closeBtn = document.getElementById("closeCropBtn");
  const cancelBtn = document.getElementById("cancelCropBtn");
  const confirmBtn = document.getElementById("confirmCropBtn");
  let cropper = null;
  let resolveCallback = null;

  window.openCropModal = function (imageSrc) {
    return new Promise((resolve) => {
      modal.style.display = "flex";
      cropImage.src = imageSrc;
      resolveCallback = resolve;
      cropImage.onload = function () {
        if (cropper) cropper.destroy();
        cropper = new Cropper(cropImage, {
          aspectRatio: 16 / 10,
          viewMode: 1,
          dragMode: "move",
          autoCropArea: 0.9,
          responsive: true,
          restore: false,
          guides: true,
          center: true,
          highlight: false,
          cropBoxMovable: true,
          cropBoxResizable: true,
          toggleDragModeOnDblclick: false,
        });
      };
      if (cropImage.complete) cropImage.onload();
    });
  };

  function closeModal() {
    modal.style.display = "none";
    if (cropper) {
      cropper.destroy();
      cropper = null;
    }
    cropImage.src = "";
    resolveCallback = null;
  }

  confirmBtn.addEventListener("click", function () {
    if (!cropper) return;
    const canvas = cropper.getCroppedCanvas({
      width: 1280,
      height: 800,
      imageSmoothingQuality: "high",
    });
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
    if (typeof resolveCallback === "function") resolveCallback(dataUrl);
    closeModal();
  });

  function handleCancel() {
    if (typeof resolveCallback === "function") resolveCallback(null);
    closeModal();
  }

  closeBtn.addEventListener("click", handleCancel);
  cancelBtn.addEventListener("click", handleCancel);
  modal.addEventListener("click", function (e) {
    if (e.target === modal) handleCancel();
  });

  window.closeCropModal = closeModal;

  // ============================================================
  // Tab 切换
  // ============================================================
  document.querySelectorAll(".tab-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".tab-btn").forEach(function (b) {
        b.classList.remove("active");
      });
      document.querySelectorAll(".section").forEach(function (s) {
        s.classList.remove("active");
      });
      this.classList.add("active");
      document.getElementById(this.dataset.tab).classList.add("active");
    });
  });

  // ============================================================
  // 作者和下载链接管理
  // ============================================================
  window.addAuthor = function () {
    const container = document.getElementById("authorList");
    const div = document.createElement("div");
    div.className = "author-item";
    div.innerHTML = `
            <input type="text" placeholder="作者名称 (例：Patotatoman)" />
            <button type="button" class="remove-btn" onclick="this.parentElement.remove()">✕</button>
        `;
    container.appendChild(div);
  };

  window.addDownloadLink = function () {
    const container = document.getElementById("downloadList");
    const div = document.createElement("div");
    div.className = "link-item";
    div.innerHTML = `
            <input type="text" placeholder="链接名称 (例：PlanetMinecraft)" />
            <input type="url" placeholder="https://…" />
            <button type="button" class="remove-btn" onclick="this.parentElement.remove()">✕</button>
        `;
    container.appendChild(div);
  };

  // ============================================================
  // 封面上传
  // ============================================================
  (function () {
    const uploadBox = document.getElementById("coverUpload");
    const fileInput = document.getElementById("coverInput");
    const preview = document.getElementById("coverPreview");
    const deleteBtn = document.getElementById("coverDelete");
    const MAX_SIZE = 10 * 1024 * 1024;
    const ALLOWED = ["image/jpeg", "image/png", "image/webp"];
    window._coverBase64 = "";

    async function handleFile(file) {
      if (!file) return;
      if (!ALLOWED.includes(file.type)) {
        Toast.warning("仅支持 JPG、PNG、WebP 格式");
        fileInput.value = "";
        return;
      }
      if (file.size > MAX_SIZE) {
        Toast.warning("图片大小不能超过 10MB");
        fileInput.value = "";
        return;
      }
      const dataUrl = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.readAsDataURL(file);
      });
      const croppedDataUrl = await window.openCropModal(dataUrl);
      if (!croppedDataUrl) {
        fileInput.value = "";
        return;
      }
      window._coverBase64 = croppedDataUrl;
      preview.src = croppedDataUrl;
      uploadBox.classList.add("has-image");
      fileInput.value = "";
    }

    function resetUpload() {
      preview.src = "";
      uploadBox.classList.remove("has-image");
      fileInput.value = "";
      window._coverBase64 = "";
    }

    uploadBox.addEventListener("click", function (e) {
      if (e.target === deleteBtn) return;
      fileInput.click();
    });

    fileInput.addEventListener("change", function () {
      const file = this.files[0];
      if (file) handleFile(file);
    });

    deleteBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      resetUpload();
    });

    uploadBox.addEventListener("dragover", function (e) {
      e.preventDefault();
      this.style.borderColor = "var(--primary, #4A90D9)";
    });

    uploadBox.addEventListener("dragleave", function (e) {
      e.preventDefault();
      this.style.borderColor = "#3b434d";
    });

    uploadBox.addEventListener("drop", function (e) {
      e.preventDefault();
      this.style.borderColor = "#3b434d";
      const files = e.dataTransfer.files;
      if (files.length > 0) handleFile(files[0]);
    });

    uploadBox.classList.remove("has-image");
    const src = preview.src;
    if (
      src &&
      src.trim() !== "" &&
      src !== window.location.href &&
      !src.endsWith("/")
    ) {
      uploadBox.classList.add("has-image");
    } else {
      preview.src = "";
      preview.removeAttribute("src");
      window._coverBase64 = "";
      uploadBox.classList.remove("has-image");
    }

    preview.onerror = function () {
      uploadBox.classList.remove("has-image");
      preview.src = "";
      preview.removeAttribute("src");
      window._coverBase64 = "";
    };
  })();

  // ============================================================
  // 截图上传
  // ============================================================
  (function () {
    const uploadBox = document.getElementById("screenshotUpload");
    const fileInput = document.getElementById("screenshotInput");
    const listContainer = document.getElementById("screenshotList");
    const clearBtn = document.getElementById("screenshotClear");
    const MAX_SIZE = 10 * 1024 * 1024;
    const ALLOWED = ["image/jpeg", "image/png", "image/webp", "image/gif"];
    window._screenshotsBase64 = [];

    async function addScreenshot(file) {
      if (!file) return;
      if (!ALLOWED.includes(file.type)) {
        Toast.warning("仅支持 JPG、PNG、WebP、GIF 格式");
        return;
      }
      if (file.size > MAX_SIZE) {
        Toast.warning("图片大小不能超过 10MB");
        return;
      }
      if (window._screenshotsBase64.length >= 12) {
        Toast.warning("最多上传 12 张截图");
        return;
      }
      const dataUrl = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.readAsDataURL(file);
      });
      const croppedDataUrl = await window.openCropModal(dataUrl);
      if (!croppedDataUrl) return;
      window._screenshotsBase64.push(croppedDataUrl);
      renderScreenshot(croppedDataUrl);
      updateUploadState();
      fileInput.value = "";
    }

    function renderScreenshot(src) {
      const item = document.createElement("div");
      item.className = "screenshot-item";
      const img = document.createElement("img");
      img.src = src;
      img.alt = "截图";
      const del = document.createElement("button");
      del.className = "del-screenshot";
      del.textContent = "✕";
      del.type = "button";
      del.addEventListener("click", function () {
        const idx = window._screenshotsBase64.indexOf(src);
        if (idx !== -1) window._screenshotsBase64.splice(idx, 1);
        item.remove();
        updateUploadState();
      });
      item.appendChild(img);
      item.appendChild(del);
      listContainer.appendChild(item);
    }

    function updateUploadState() {
      const count = window._screenshotsBase64.length;
      const area = document.getElementById("screenshotPreviewArea");
      if (count > 0) {
        uploadBox.classList.add("has-image");
        area.style.display = "block";
        area.innerHTML = `<div style="color:#8b949e; font-size:14px; padding:12px;">✅ 已上传 ${count} 张截图</div>`;
      } else {
        uploadBox.classList.remove("has-image");
        area.style.display = "none";
        area.innerHTML = "";
      }
    }

    if (
      window._existingScreenshots &&
      Array.isArray(window._existingScreenshots)
    ) {
      window._existingScreenshots.forEach(function (src) {
        if (src) {
          window._screenshotsBase64.push(src);
          renderScreenshot(src);
        }
      });
      updateUploadState();
    }

    uploadBox.addEventListener("click", function (e) {
      if (e.target === clearBtn) return;
      if (window._screenshotsBase64.length >= 12) {
        Toast.warning("最多上传 12 张截图");
        return;
      }
      fileInput.click();
    });

    fileInput.addEventListener("change", function () {
      const files = this.files;
      if (files.length === 0) return;
      const processNext = async (index) => {
        if (index >= files.length) {
          this.value = "";
          return;
        }
        if (window._screenshotsBase64.length >= 12) {
          Toast.warning("已达到 12 张上限，剩余截图忽略");
          this.value = "";
          return;
        }
        await addScreenshot(files[index]);
        processNext(index + 1);
      };
      processNext(0);
    });

    clearBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (window._screenshotsBase64.length === 0) return;
      if (confirm("确定要清除所有已上传的截图吗？")) {
        listContainer.innerHTML = "";
        window._screenshotsBase64 = [];
        updateUploadState();
        fileInput.value = "";
      }
    });

    uploadBox.addEventListener("dragover", function (e) {
      e.preventDefault();
      this.style.borderColor = "var(--primary, #4A90D9)";
    });

    uploadBox.addEventListener("dragleave", function (e) {
      e.preventDefault();
      this.style.borderColor = "#3b434d";
    });

    uploadBox.addEventListener("drop", function (e) {
      e.preventDefault();
      this.style.borderColor = "#3b434d";
      const files = e.dataTransfer.files;
      if (files.length === 0) return;
      const processNext = async (index) => {
        if (index >= files.length) return;
        if (window._screenshotsBase64.length >= 12) {
          Toast.warning("已达到 12 张上限，剩余截图忽略");
          return;
        }
        await addScreenshot(files[index]);
        processNext(index + 1);
      };
      processNext(0);
    });

    updateUploadState();
  })();

  // ============================================================
  // 初始化作者和下载
  // ============================================================
  window.initAuthorAndDownload = function (authors, links) {
    const authorContainer = document.getElementById("authorList");
    if (!authorContainer) return;
    authorContainer.innerHTML = "";
    if (authors && authors.length) {
      authors.forEach(function (name) {
        const div = document.createElement("div");
        div.className = "author-item";
        div.innerHTML = `
                    <input type="text" placeholder="作者名称" value="${name}" />
                    <button type="button" class="remove-btn" onclick="this.parentElement.remove()">✕</button>
                `;
        authorContainer.appendChild(div);
      });
    } else {
      const div = document.createElement("div");
      div.className = "author-item";
      div.innerHTML = `
                <input type="text" placeholder="作者名称 (例：Patotatoman)" />
                <button type="button" class="remove-btn" onclick="this.parentElement.remove()">✕</button>
            `;
      authorContainer.appendChild(div);
    }

    const linkContainer = document.getElementById("downloadList");
    if (!linkContainer) return;
    linkContainer.innerHTML = "";
    if (links && links.length) {
      links.forEach(function (link) {
        const div = document.createElement("div");
        div.className = "link-item";
        div.innerHTML = `
                    <input type="text" placeholder="链接名称" value="${link.name || ""}" />
                    <input type="url" placeholder="https://…" value="${link.url || ""}" />
                    <button type="button" class="remove-btn" onclick="this.parentElement.remove()">✕</button>
                `;
        linkContainer.appendChild(div);
      });
    } else {
      const div = document.createElement("div");
      div.className = "link-item";
      div.innerHTML = `
                <input type="text" placeholder="链接名称 (例：PlanetMinecraft)" />
                <input type="url" placeholder="https://…" />
                <button type="button" class="remove-btn" onclick="this.parentElement.remove()">✕</button>
            `;
      linkContainer.appendChild(div);
    }
  };

  // ============================================================
  // 脏数据检测
  // ============================================================
  (function () {
    let isDirty = false;
    window._isDirty = false;

    function markDirty() {
      if (!isDirty) {
        isDirty = true;
        window._isDirty = true;
      }
    }

    function resetDirty() {
      isDirty = false;
      window._isDirty = false;
    }

    document.addEventListener("input", function (e) {
      const target = e.target;
      if (target.matches('input:not([type="file"]), textarea, select')) {
        markDirty();
      }
    });

    document.addEventListener("input", function (e) {
      const target = e.target;
      if (target.isContentEditable) {
        markDirty();
      }
    });

    document.addEventListener("change", function (e) {
      const target = e.target;
      if (target.matches('input[type="file"]')) {
        markDirty();
      }
    });

    document.addEventListener("click", function (e) {
      const target = e.target;
      if (
        target.closest &&
        target.closest(".delete-btn, .del-screenshot, .remove-btn")
      ) {
        markDirty();
      }
    });

    document.addEventListener("click", function (e) {
      const target = e.target;
      if (target.matches(".submit-btn, #submitBtn")) {
        setTimeout(resetDirty, 100);
      }
    });

    window.addEventListener("beforeunload", function (e) {
      const form = document.getElementById("publishForm");
      if (form && form.classList.contains("locked")) {
        return;
      }
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "您有未保存的更改，确定要离开吗？";
        return e.returnValue;
      }
    });

    window.resetDirty = resetDirty;
  })();

  // ============================================================
  // 提交模态框
  // ============================================================
  (function () {
    let submitModal = null;

    function getSubmitModal() {
      if (!submitModal) {
        submitModal = document.createElement("div");
        submitModal.id = "submitModal";
        submitModal.style.cssText = `
                    display: none;
                    position: fixed;
                    top: 0; left: 0;
                    width: 100%; height: 100%;
                    background: rgba(0,0,0,0.7);
                    z-index: 10001;
                    align-items: center;
                    justify-content: center;
                `;
        const box = document.createElement("div");
        box.className = "modal-box";
        box.innerHTML = `
                    <h3 id="submitModalTitle">确认提交</h3>
                    <div class="body-text" id="submitModalBody">确定要提交吗？</div>
                    <div class="progress-area" id="submitModalProgress">
                        进度：<span class="progress-text" id="submitProgressText">准备...</span>
                    </div>
                    <div class="btn-group">
                        <button class="btn-cancel" id="submitModalCancel">取消</button>
                        <button class="btn-confirm" id="submitModalConfirm">确定</button>
                    </div>
                `;
        submitModal.appendChild(box);
        document.body.appendChild(submitModal);

        submitModal
          .querySelector("#submitModalCancel")
          .addEventListener("click", function () {
            submitModal.style.display = "none";
            if (submitModal._reject) submitModal._reject(new Error("用户取消"));
          });

        submitModal
          .querySelector("#submitModalConfirm")
          .addEventListener("click", async function () {
            const confirmBtn = this;
            const cancelBtn = submitModal.querySelector("#submitModalCancel");
            const body = submitModal.querySelector("#submitModalBody");
            const progressDiv = submitModal.querySelector(
              "#submitModalProgress",
            );
            const progressText = submitModal.querySelector(
              "#submitProgressText",
            );

            confirmBtn.disabled = true;
            cancelBtn.disabled = true;
            body.style.display = "none";
            progressDiv.style.display = "block";
            progressText.textContent = "开始提交...";

            try {
              if (typeof submitModal._onConfirm === "function") {
                const result = await submitModal._onConfirm(function (msg) {
                  progressText.textContent = msg;
                });
                const isSkip = window._canSkipReview || false;
                progressText.textContent = isSkip
                  ? "✅ 提交完成！"
                  : "✅ 提交完成，等待管理员审核。";
                setTimeout(() => {
                  submitModal.style.display = "none";
                  confirmBtn.disabled = false;
                  cancelBtn.disabled = false;
                  body.style.display = "block";
                  progressDiv.style.display = "none";
                  if (typeof submitModal._onSuccess === "function") {
                    submitModal._onSuccess(result);
                  }
                }, 1500);
              }
            } catch (err) {
              progressText.textContent = "❌ 提交失败：" + err.message;
              confirmBtn.disabled = false;
              cancelBtn.disabled = false;
            }
          });
      }
      return submitModal;
    }

    window.showSubmitModal = function (options) {
      return new Promise((resolve, reject) => {
        const modal = getSubmitModal();
        const titleEl = modal.querySelector("#submitModalTitle");
        const bodyEl = modal.querySelector("#submitModalBody");
        const confirmBtn = modal.querySelector("#submitModalConfirm");
        const cancelBtn = modal.querySelector("#submitModalCancel");
        const progressDiv = modal.querySelector("#submitModalProgress");
        const progressText = modal.querySelector("#submitProgressText");

        progressDiv.style.display = "none";
        bodyEl.style.display = "block";
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
        progressText.textContent = "";
        titleEl.textContent = options.title || "确认提交";

        bodyEl.innerHTML = "";

        const messageDiv = document.createElement("div");
        messageDiv.textContent = options.message || "确定要提交吗？";
        bodyEl.appendChild(messageDiv);

        const duplicateWarning = options.duplicateWarning;

        if (duplicateWarning && duplicateWarning.hitCount > 0) {
          const hitCount = duplicateWarning.hitCount;
          const hitFields = duplicateWarning.hitFields || [];
          const lockSeconds = duplicateWarning.lockSeconds || 0;

          let level = "warning";
          let icon = "⚠️";
          let title = "检测到可能重复的资源";
          let extraMsg = "请确认您提交的资源不是重复收录的资源。";
          let bgColor = "rgba(245, 166, 35, 0.12)";
          let borderColor = "#f5a623";
          let textColor = "#f5a623";

          if (hitCount >= 3) {
            level = "danger";
            icon = "🚨";
            title = "高度疑似重复资源！";
            extraMsg = "您所提交的资源有极大概率撞车，请务必仔细核实！";
            bgColor = "rgba(248, 113, 113, 0.15)";
            borderColor = "#f87171";
            textColor = "#f87171";
          } else if (hitCount === 2) {
            level = "warning";
            icon = "⚠️";
            title = "存在撞车可能！";
            extraMsg = "已有 2 项信息与主站资源匹配，请确认是否重复。";
            bgColor = "rgba(245, 166, 35, 0.14)";
            borderColor = "#f5a623";
            textColor = "#f5a623";
          }

          const warningDiv = document.createElement("div");
          warningDiv.style.cssText = `
                        margin-top: 14px;
                        padding: 12px 14px;
                        border-radius: 8px;
                        background: ${bgColor};
                        border: 1px solid ${borderColor};
                        color: ${textColor};
                        font-size: 14px;
                        line-height: 1.6;
                    `;

          let fieldsHtml = hitFields
            .map((f) => `<strong>${f}</strong>`)
            .join("、");

          warningDiv.innerHTML = `
                        <div style="font-weight:700;margin-bottom:4px;">
                            ${icon} ${title}
                        </div>
                        <div>
                            以下信息已存在于主站资源中：${fieldsHtml}
                        </div>
                        <div style="margin-top:4px;color:#c9d1d9;font-size:13px;">
                            ${extraMsg}
                        </div>
                        ${
                          lockSeconds > 0
                            ? `
                            <div style="margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.08);color:#e6edf3;font-size:13px;">
                                ⏳ 请阅读以上提示，<span id="countdownNum" style="font-weight:700;color:${textColor};">${lockSeconds}</span> 秒后可确认提交
                            </div>
                        `
                            : ""
                        }
                    `;

          bodyEl.appendChild(warningDiv);

          if (lockSeconds > 0) {
            confirmBtn.disabled = true;
            let remaining = lockSeconds;
            const timerEl = warningDiv.querySelector("#countdownNum");

            const interval = setInterval(() => {
              remaining--;
              if (timerEl) timerEl.textContent = remaining;
              if (remaining <= 0) {
                clearInterval(interval);
                confirmBtn.disabled = false;
                if (timerEl) timerEl.textContent = "0（可确认）";
              }
            }, 1000);
          }
        }

        confirmBtn.textContent = options.confirmText || "确定";
        cancelBtn.textContent = options.cancelText || "取消";

        modal._onConfirm = options.onConfirm;
        modal._onSuccess = options.onSuccess;
        modal._resolve = resolve;
        modal._reject = reject;

        modal.style.display = "flex";
      });
    };
  })();

  // ============================================================
  // 加载站内规则
  // ============================================================
  (function () {
    "use strict";
    window.loadRulesToSidebar = function (containerId) {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML =
        '<div style="color:#6b7480;font-size:13px;padding:4px 0;">加载规则…</div>';
      fetch("/api/rules/list")
        .then((res) => res.json())
        .then((data) => {
          if (!data.success || !data.data || data.data.length === 0) {
            container.innerHTML =
              '<div style="color:#6b7480;font-size:13px;padding:4px 0;">暂无规则</div>';
            return;
          }
          let html = "";
          data.data.forEach((rule) => {
            html += `
                            <a href="/rule/${rule.rule_key}" target="_blank" class="rule-link" title="${rule.title}">
                                <span class="rule-icon">📜</span>
                                <span class="rule-name">${rule.title}</span>
                            </a>
                        `;
          });
          container.innerHTML = html;
        })
        .catch(() => {
          container.innerHTML =
            '<div style="color:#6b7480;font-size:13px;padding:4px 0;">加载失败</div>';
        });
    };
  })();

  console.log("✅ MCRES 公共脚本已加载（含防撞车模态框支持）");
})();
