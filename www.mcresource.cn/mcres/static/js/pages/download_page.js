(function () {
  "use strict";
  const downloadBtns = document.querySelectorAll(".download-btn");
  const modal = document.getElementById("checksumModal");
  const modalClose = document.getElementById("modalCloseBtn");
  const confirmBtn = document.getElementById("confirmDownloadBtn");
  const captchaInput = document.getElementById("captchaInput");
  const captchaImg = document.getElementById("captchaImg");
  const errorDisplay = document.getElementById("modalErrors");
  let currentFile = null;

  // ===== 注册引导模态框元素 =====
  const guideModal = document.getElementById("registerGuideModal");
  const guideCloseBtn = document.getElementById("registerGuideCloseBtn");

  // ===== 打开注册引导模态框 =====
  function openRegisterGuideModal() {
    if (guideModal) {
      guideModal.classList.add("active");
      document.body.style.overflow = "hidden";
    }
  }

  // ===== 关闭注册引导模态框 =====
  function closeRegisterGuideModal() {
    if (guideModal) {
      guideModal.classList.remove("active");
      document.body.style.overflow = "";
    }
  }

  // ===== 关闭验证码模态框（供外部调用） =====
  function closeChecksumModal() {
    modal.classList.remove("active");
    document.body.style.overflow = "";
    currentFile = null;
  }

  // ===== 更新游客剩余次数显示 =====
  function updateGuestRemaining() {
    const displayEl = document.getElementById("guestRemainingDisplay");
    if (!displayEl) return;
    let current = parseInt(displayEl.textContent, 10);
    if (isNaN(current) || current <= 0) {
      displayEl.textContent = "0";
      const tip = document.getElementById("guestTip");
      if (tip) {
        tip.style.opacity = "0.6";
      }
      return;
    }
    displayEl.textContent = current - 1;
    if (current - 1 <= 0) {
      const tip = document.getElementById("guestTip");
      if (tip) {
        tip.style.opacity = "0.6";
      }
    }
  }

  // ===== 检查是否为游客 =====
  function isGuest() {
    return document.getElementById("guestTip") !== null;
  }

  downloadBtns.forEach((btn) => {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      const filename = this.dataset.filename;
      if (!filename) return;
      const type = window.location.pathname.split("/")[2];
      const id = window.location.pathname.split("/")[3];
      fetch(`/download/${type}/${id}/${filename}/checksum`)
        .then((res) => {
          if (!res.ok)
            return res.json().then((err) => {
              throw new Error(err.message || "获取校验和失败");
            });
          return res.json();
        })
        .then((data) => {
          if (data.success) {
            const cs = data.checksums;
            document.getElementById("checksum_md5").textContent = cs.md5 || "—";
            document.getElementById("checksum_crc32").textContent =
              cs.crc32 || "—";
            document.getElementById("checksum_sha256").textContent =
              cs.sha256 || "—";
            currentFile = filename;
            captchaInput.value = "";
            errorDisplay.textContent = "";
            captchaImg.src = "/captcha?" + Date.now();
            modal.classList.add("active");
            document.body.style.overflow = "hidden";
          } else {
            Toast.error("获取校验和失败：" + (data.message || "未知错误"));
          }
        })
        .catch((err) => {
          Toast.error("获取校验和失败：" + err.message);
        });
    });
  });

  // ===== 关闭验证码模态框 =====
  modalClose.addEventListener("click", closeChecksumModal);
  modal.addEventListener("click", function (e) {
    if (e.target === this) closeChecksumModal();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modal.classList.contains("active")) {
      closeChecksumModal();
    }
  });

  // ===== 注册引导模态框关闭事件 =====
  if (guideCloseBtn) {
    guideCloseBtn.addEventListener("click", closeRegisterGuideModal);
  }
  if (guideModal) {
    guideModal.addEventListener("click", function (e) {
      if (e.target === this) closeRegisterGuideModal();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && guideModal.classList.contains("active")) {
        closeRegisterGuideModal();
      }
    });
  }

  // ===== 确认下载按钮 =====
  confirmBtn.addEventListener("click", function () {
    if (!currentFile) {
      errorDisplay.textContent = "请选择要下载的文件";
      return;
    }
    const captcha = captchaInput.value.trim().toUpperCase();
    if (!captcha) {
      errorDisplay.textContent = "请输入验证码";
      return;
    }
    const type = window.location.pathname.split("/")[2];
    const id = window.location.pathname.split("/")[3];
    const formData = new FormData();
    formData.append("captcha", captcha);

    fetch(`/download/${type}/${id}/${currentFile}/request_download`, {
      method: "POST",
      body: formData,
    })
      .then((res) => {
        if (!res.ok)
          return res.json().then((err) => {
            throw err;
          });
        return res.json();
      })
      .then((data) => {
        if (data.success) {
          window.open(data.url, "_blank");
          const row = document.querySelector(
            `tr[data-filename="${currentFile}"]`,
          );
          if (row) {
            const countCell = row.querySelector(".download-count");
            if (countCell) {
              let count = parseInt(countCell.textContent) || 0;
              countCell.textContent = count + 1;
            }
          }
          if (isGuest()) {
            updateGuestRemaining();
          }
          closeChecksumModal();
        } else {
          if (data.code === "GUEST_LIMIT_REACHED") {
            closeChecksumModal();
            openRegisterGuideModal();
          } else {
            errorDisplay.textContent = data.message || "下载请求失败";
            captchaImg.src = "/captcha?" + Date.now();
            captchaInput.value = "";
          }
        }
      })
      .catch((err) => {
        if (err && err.code === "GUEST_LIMIT_REACHED") {
          closeChecksumModal();
          openRegisterGuideModal();
        } else {
          errorDisplay.textContent = err.message || "网络错误，请稍后重试";
          captchaImg.src = "/captcha?" + Date.now();
          captchaInput.value = "";
        }
      });
  });

  // ===== 回车键提交验证码 =====
  captchaInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      confirmBtn.click();
    }
  });
})();

// ===== 筛选器功能 =====
(function () {
  const versionFilter = document.getElementById("filterVersion");
  const gameVersionFilter = document.getElementById("filterGameVersion");
  const clearFiltersBtn = document.getElementById("clearFilters");
  const filterCount = document.getElementById("filterResultCount");
  const tableRows = document.querySelectorAll("#fileTableBody tr");

  function applyFilters() {
    const selectedVersion = versionFilter.value;
    const selectedGameVersion = gameVersionFilter.value;
    let visibleCount = 0;

    tableRows.forEach((row) => {
      const rowVersion = row.dataset.version || "";
      const rowGameVersion = row.dataset.gameversion || "";
      let show = true;
      if (selectedVersion !== "all" && rowVersion !== selectedVersion) {
        show = false;
      }
      if (
        selectedGameVersion !== "all" &&
        rowGameVersion !== selectedGameVersion
      ) {
        show = false;
      }
      row.style.display = show ? "" : "none";
      if (show) visibleCount++;
    });
    filterCount.textContent = `显示 ${visibleCount} 个文件`;
  }

  versionFilter.addEventListener("change", applyFilters);
  gameVersionFilter.addEventListener("change", applyFilters);
  clearFiltersBtn.addEventListener("click", function () {
    versionFilter.value = "all";
    gameVersionFilter.value = "all";
    applyFilters();
  });
  applyFilters();
  // ---------- 验证码刷新（替代内联 onclick） ----------
  captchaImg.addEventListener("click", function () {
    captchaImg.src = "/captcha?" + Date.now();
    captchaInput.value = "";
  });
})();
