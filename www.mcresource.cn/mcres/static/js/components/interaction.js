// ============================================================
// 三连组件交互逻辑（独立）
// Toast 由 /static/js/components/toast.js 提供（base.html 已全局加载）。
// ============================================================

(function () {
  "use strict";

  // 本地状态缓存
  let localState = {
    brick: 0,
    user_coin_count: 0,
    coins_remaining: 10,
  };

  function initInteraction() {
    const bar = document.querySelector(".interaction-bar");
    if (!bar) return;

    const resourceType = bar.dataset.resourceType;
    const resourceId = parseInt(bar.dataset.resourceId, 10);
    if (!resourceType || !resourceId) return;

    const likeBtn = bar.querySelector(".like-btn");
    const coinBtn = bar.querySelector(".coin-btn");
    const favBtn = document.getElementById("fav-btn-open-modal");
    const likeStatus = document.getElementById("like-status");
    const coinStatus = document.getElementById("coin-status");
    const favStatus = document.getElementById("fav-status");

    // ---------- 更新 UI ----------
    function updateUI(data) {
      if (data.likes_count !== undefined) {
        likeStatus.textContent =
          data.likes_count > 0 ? data.likes_count : "点赞";
      }
      if (data.coins_count !== undefined) {
        coinStatus.textContent =
          data.coins_count > 0 ? data.coins_count : "添砖";
      }
      if (data.favorites_count !== undefined) {
        favStatus.textContent =
          data.favorites_count > 0 ? data.favorites_count : "收藏";
      }

      likeBtn.classList.toggle("active", data.user_liked === true);
      favBtn.classList.toggle("active", data.user_favorited === true);
      coinBtn.classList.toggle("active", data.user_coined === true);

      const remaining =
        data.coins_remaining !== undefined ? data.coins_remaining : 10;
      coinBtn.classList.toggle("coin-limit", remaining <= 0);

      // 更新本地缓存
      if (data.brick !== undefined) localState.brick = data.brick;
      if (data.user_coin_count !== undefined)
        localState.user_coin_count = data.user_coin_count;
      if (data.coins_remaining !== undefined)
        localState.coins_remaining = data.coins_remaining;
    }

    // ---------- 调用后端 API ----------
    async function callInteraction(action) {
      const url = `/interaction?type=${resourceType}&id=${resourceId}`;
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: action }),
      });
      if (!resp.ok) {
        let msg = `请求失败 (${resp.status})`;
        try {
          const errData = await resp.json();
          if (errData.message) msg = errData.message;
        } catch (e) {
          msg = resp.statusText || msg;
        }
        throw new Error(msg);
      }
      return await resp.json();
    }

    // ---------- 获取最新互动状态 ----------
    async function fetchInteractionStatus() {
      const url = `/interaction?type=${resourceType}&id=${resourceId}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error("获取状态失败");
      return await resp.json();
    }

    // ---------- 砖块动画（使用 fa-cube 图标） ----------
    function playCoinAnimation(btn) {
      return new Promise((resolve) => {
        const rect = btn.getBoundingClientRect();
        const icon = document.createElement("i");
        icon.className = "fas fa-cube";
        icon.style.cssText = `
                    position: fixed;
                    left: ${rect.left + rect.width / 2 - 20}px;
                    top: ${rect.top - 60}px;
                    font-size: 40px;
                    color: #4A90D9;
                    pointer-events: none;
                    z-index: 9999;
                    opacity: 1;
                    transform: scale(0.8);
                    transition: all 0.7s cubic-bezier(0.25, 0.46, 0.45, 0.94);
                `;
        document.body.appendChild(icon);
        requestAnimationFrame(() => {
          icon.style.transform = "translateY(80px) scale(1.3)";
          icon.style.opacity = "0";
        });
        setTimeout(() => {
          icon.remove();
          resolve();
        }, 750);
      });
    }

    // ---------- 绑定点击事件 ----------
    function bindClick(btn, action) {
      btn.addEventListener("click", async function (e) {
        e.preventDefault();
        if (this.disabled) return;

        // 添砖特殊处理（含本地拦截）
        if (action === "coin") {
          // 1. 检查每日上限
          if (this.classList.contains("coin-limit")) {
            Toast.warning("今日投币已达上限（10次）");
            return;
          }

          // 2. 检查砖块余额
          if (localState.brick < 1) {
            Toast.warning("砖块不足，请先签到获取砖块");
            return;
          }

          // 3. 检查单资源投币上限
          if (localState.user_coin_count >= 2) {
            Toast.warning("您对该资源最多只能投2次");
            return;
          }

          // 通过所有检查，执行请求 + 动画
          this.disabled = true;
          try {
            const [result] = await Promise.all([
              callInteraction("coin"),
              playCoinAnimation(this),
            ]);
            if (result.code === 0) {
              updateUI(result.data);
              Toast.success("添砖成功！");
            } else {
              Toast.error(result.message || "操作失败");
            }
          } catch (err) {
            console.error(err);
            Toast.error(err.message || "请求异常，请重试");
          } finally {
            this.disabled = false;
          }
          return;
        }

        // 点赞 / 收藏（无动画）
        this.disabled = true;
        try {
          const result = await callInteraction(action);
          if (result.code === 0) {
            updateUI(result.data);
          } else {
            Toast.error(result.message || "操作失败");
          }
        } catch (err) {
          console.error(err);
          Toast.error(err.message || "请求异常，请重试");
        } finally {
          this.disabled = false;
        }
      });
    }

    bindClick(likeBtn, "like");
    bindClick(coinBtn, "coin");

    // ---------- 收藏：打开模态框 ----------
    if (favBtn) {
      favBtn.addEventListener("click", function (e) {
        e.preventDefault();
        openFavoritesModal();
      });
    }

    // ---------- 模态框逻辑 ----------
    let modal = document.getElementById("favorites-modal");
    let modalList = document.getElementById("favorites-modal-list");
    let modalClose = document.getElementById("favorites-modal-close");

    if (!modal) {
      console.warn(
        "收藏夹模态框未找到，请确保 interaction.html 包含模态框结构",
      );
      return;
    }

    function openFavoritesModal() {
      modalList.innerHTML =
        '<div class="modal-loading"><i class="fas fa-spinner fa-spin"></i> 加载收藏夹...</div>';
      modal.style.display = "flex";

      fetch("/profile/favorites/data", {
        credentials: "same-origin",
      })
        .then((resp) => {
          if (!resp.ok) {
            if (resp.status === 401) {
              Toast.warning("请先登录");
              modal.style.display = "none";
              return null;
            }
            throw new Error("获取收藏夹失败");
          }
          return resp.json();
        })
        .then((data) => {
          if (!data) return;
          if (data.success) {
            renderFolders(data.data);
          } else {
            modalList.innerHTML =
              '<div style="color:#f97583;text-align:center;">加载失败，请确认登录后重试</div>';
          }
        })
        .catch((err) => {
          console.error(err);
          modalList.innerHTML =
            '<div style="color:#f97583;text-align:center;">加载失败，请确认登录后重试</div>';
        });
    }

    function renderFolders(folders) {
      if (!folders || folders.length === 0) {
        modalList.innerHTML = `
                    <div style="text-align:center; color:#8a8a9e; padding:20px;">
                        暂无收藏夹，<a href="/profile/${getUserId()}" target="_blank" style="color:var(--role-color, #55d88b);">去创建</a>
                    </div>
                `;
        return;
      }

      let html = "";
      folders.forEach(function (folder) {
        let isFavorited = folder.resources.some(
          (r) => r.type === resourceType && r.id === resourceId,
        );
        let actionHtml = "";
        if (isFavorited) {
          actionHtml = `
                        <div class="folder-actions">
                            <button class="remove-btn" data-folder-id="${folder.id}">取消收藏</button>
                        </div>
                    `;
        } else {
          actionHtml = `
                        <div class="folder-actions">
                            <button class="add-btn" data-folder-id="${folder.id}">收藏到此夹</button>
                        </div>
                    `;
        }
        html += `
                    <div class="folder-item" data-folder-id="${folder.id}">
                        <span class="folder-name">${folder.name} (${folder.resources.length})</span>
                        ${actionHtml}
                    </div>
                `;
      });
      modalList.innerHTML = html;

      modalList.querySelectorAll(".add-btn").forEach((btn) => {
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          let folderId = parseInt(this.dataset.folderId, 10);
          addToFolder(folderId);
        });
      });
      modalList.querySelectorAll(".remove-btn").forEach((btn) => {
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          let folderId = parseInt(this.dataset.folderId, 10);
          removeFromFolder(folderId);
        });
      });
    }

    function addToFolder(folderId) {
      fetch("/profile/favorites/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          resource_type: resourceType,
          resource_id: resourceId,
          folder_id: folderId,
        }),
      })
        .then((resp) => resp.json())
        .then((data) => {
          if (data.success) {
            modal.style.display = "none";
            Toast.success("已添加到收藏夹");
            refreshFavStatus();
          } else {
            Toast.error(data.message || "操作失败");
          }
        })
        .catch((err) => {
          Toast.error("请求失败，请重试");
        });
    }

    function removeFromFolder(folderId) {
      fetch("/profile/favorites/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          resource_type: resourceType,
          resource_id: resourceId,
          folder_id: folderId,
        }),
      })
        .then((resp) => resp.json())
        .then((data) => {
          if (data.success) {
            modal.style.display = "none";
            Toast.success("已取消收藏");
            refreshFavStatus();
          } else {
            Toast.error(data.message || "操作失败");
          }
        })
        .catch((err) => {
          Toast.error("请求失败，请重试");
        });
    }

    function refreshFavStatus() {
      fetchInteractionStatus()
        .then((result) => {
          if (result.code === 0) {
            updateUI(result.data);
          }
        })
        .catch((err) => console.warn("刷新收藏状态失败", err));
    }

    if (modalClose) {
      modalClose.addEventListener("click", function () {
        modal.style.display = "none";
      });
    }
    modal.addEventListener("click", function (e) {
      if (e.target === modal) {
        modal.style.display = "none";
      }
    });

    function getUserId() {
      const match = window.location.pathname.match(/\/profile\/(\d+)/);
      return match ? match[1] : "";
    }

    // ---------- 初始化时获取状态并缓存 ----------
    fetchInteractionStatus()
      .then((result) => {
        if (result.code === 0) {
          updateUI(result.data);
        }
      })
      .catch((err) => console.warn("初始化获取状态失败", err));

    console.log("✅ 三连组件已初始化（带本地拦截和砖块动画）");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initInteraction);
  } else {
    initInteraction();
  }
})();
