// static/js/pages/profile/favorites.js
(function() {
    'use strict';

    var currentFolderId = null;
    var foldersData = [];
    var contextMenu = document.getElementById('folder-context-menu');
    var contextTargetId = null;

    // ---------- 模态框控制 ----------
    var folderModal = document.getElementById('folder-modal');
    var deleteModal = document.getElementById('delete-modal');
    var modalInput = document.getElementById('modal-input');
    var modalTitle = document.getElementById('modal-title');
    var modalHint = document.getElementById('modal-hint');
    var modalConfirmBtn = document.getElementById('modal-confirm-btn');
    var modalCancelBtn = document.getElementById('modal-cancel-btn');
    var deleteConfirmBtn = document.getElementById('delete-confirm-btn');
    var deleteCancelBtn = document.getElementById('delete-cancel-btn');

    var modalMode = 'create'; // 'create' | 'rename'
    var renameTargetId = null;

    function showFolderModal(mode, folderId) {
        if (!isMe) return;
        modalMode = mode;
        if (mode === 'create') {
            modalTitle.textContent = '新建收藏夹';
            modalInput.value = '';
            modalInput.placeholder = '请输入收藏夹名称';
            renameTargetId = null;
        } else if (mode === 'rename') {
            var folder = foldersData.find(function(f) { return f.id === folderId; });
            if (!folder) return;
            modalTitle.textContent = '重命名收藏夹';
            modalInput.value = folder.name;
            modalInput.placeholder = '请输入新名称';
            renameTargetId = folderId;
        }
        modalHint.style.display = 'none';
        folderModal.style.display = 'flex';
        setTimeout(function() { modalInput.focus(); }, 100);
    }

    function hideFolderModal() {
        folderModal.style.display = 'none';
        modalHint.style.display = 'none';
        modalInput.value = '';
    }

    function showDeleteModal(folderId) {
        if (!isMe) return;
        contextTargetId = folderId;
        deleteModal.style.display = 'flex';
    }

    function hideDeleteModal() {
        deleteModal.style.display = 'none';
        contextTargetId = null;
    }

    // ---------- 模态框事件绑定 ----------
    modalCancelBtn.addEventListener('click', hideFolderModal);
    folderModal.addEventListener('click', function(e) {
        if (e.target === folderModal) hideFolderModal();
    });

    modalConfirmBtn.addEventListener('click', function() {
        var name = modalInput.value.trim();
        if (!name) {
            modalHint.textContent = '名称不能为空';
            modalHint.style.display = 'block';
            return;
        }
        if (modalMode === 'create') {
            createFolder(name);
        } else if (modalMode === 'rename') {
            renameFolder(renameTargetId, name);
        }
    });

    modalInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            modalConfirmBtn.click();
        } else if (e.key === 'Escape') {
            hideFolderModal();
        }
    });

    deleteCancelBtn.addEventListener('click', hideDeleteModal);
    deleteModal.addEventListener('click', function(e) {
        if (e.target === deleteModal) hideDeleteModal();
    });

    deleteConfirmBtn.addEventListener('click', function() {
        if (contextTargetId !== null) {
            deleteFolder(contextTargetId);
        }
        hideDeleteModal();
    });

    // ---------- 渲染收藏夹列表 ----------
    function renderFolders(folders) {
        var container = document.getElementById('folder-list');
        if (!container) return;
        foldersData = folders || [];

        if (!folders || folders.length === 0) {
            container.innerHTML = `
                <div style="padding: 12px; color: #6f6f84; text-align: center; font-size: 14px;">
                    暂无收藏夹
                </div>
            `;
            document.getElementById('folders-total').textContent = '0';
            renderResources([]);
            return;
        }

        var html = '';
        folders.forEach(function(folder) {
            var activeClass = (currentFolderId === folder.id) ? 'active' : '';
            html += `
                <button class="works-sub-btn ${activeClass}" data-folder-id="${folder.id}" data-folder-name="${folder.name}">
                    <i class="fas fa-folder"></i>
                    <span class="sub-label">${folder.name}</span>
                    <span class="sub-count">${folder.resources ? folder.resources.length : 0}</span>
                </button>
            `;
        });
        container.innerHTML = html;
        document.getElementById('folders-total').textContent = folders.length;

        container.querySelectorAll('.works-sub-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var folderId = parseInt(this.dataset.folderId, 10);
                switchFolder(folderId);
            });
            btn.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                var folderId = parseInt(this.dataset.folderId, 10);
                showContextMenu(e.clientX, e.clientY, folderId);
            });
        });

        if (currentFolderId === null && folders.length > 0) {
            switchFolder(folders[0].id);
        } else if (currentFolderId !== null) {
            var activeBtn = container.querySelector('.works-sub-btn[data-folder-id="' + currentFolderId + '"]');
            if (!activeBtn && folders.length > 0) {
                switchFolder(folders[0].id);
            }
        }
    }

    // ---------- 渲染资源列表 ----------
    function renderResources(resources) {
        var container = document.getElementById('favorites-resource-list');
        if (!container) return;

        if (!resources || resources.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-star" style="color: var(--role-color); opacity:0.3;"></i>
                    <p>这个收藏夹还是空的，去收藏一些资源吧！</p>
                </div>
            `;
            return;
        }

        var html = '';
        resources.forEach(function(item) {
            var detailUrl = '/' + item.type + '/' + item.id;
            html += `
                <div class="resource-card">
                    <a href="${detailUrl}" target="_blank" style="text-decoration:none; color:inherit;">
                        <div class="thumb">
                            <img src="${item.cover}" alt="${item.title}" loading="lazy">
                        </div>
                        <div class="info">
                            <div class="title">${item.title}</div>
                            <div class="meta">
                                <span>${item.views || 0} 浏览</span>
                                <span>${item.type === 'resourcepack' ? '资源包' : item.type === 'shaderpack' ? '光影包' : '地图'}</span>
                            </div>
                        </div>
                    </a>
                </div>
            `;
        });
        container.innerHTML = html;
    }

    // ---------- 切换收藏夹 ----------
    function switchFolder(folderId) {
        currentFolderId = folderId;
        var btns = document.querySelectorAll('#folder-list .works-sub-btn');
        btns.forEach(function(btn) {
            btn.classList.toggle('active', parseInt(btn.dataset.folderId, 10) === folderId);
        });
        var folder = foldersData.find(function(f) { return f.id === folderId; });
        renderResources(folder ? folder.resources || [] : []);
    }

    // ---------- 右键菜单 ----------
    function showContextMenu(x, y, folderId) {
        if (!isMe) return;
        contextTargetId = folderId;
        contextMenu.style.display = 'block';
        contextMenu.style.left = Math.min(x, window.innerWidth - 160) + 'px';
        contextMenu.style.top = Math.min(y, window.innerHeight - 100) + 'px';
    }

    function hideContextMenu() {
        contextMenu.style.display = 'none';
    }

    document.querySelectorAll('.context-item').forEach(function(item) {
        item.addEventListener('click', function(e) {
            e.stopPropagation();
            var action = this.dataset.action;
            if (action === 'rename') {
                hideContextMenu();
                showFolderModal('rename', contextTargetId);
            } else if (action === 'delete') {
                hideContextMenu();
                showDeleteModal(contextTargetId);
            }
        });
    });

    document.addEventListener('click', function(e) {
        if (!contextMenu.contains(e.target)) {
            hideContextMenu();
        }
    });

    // ---------- API 操作 ----------
    function createFolder(name) {
        fetch('/profile/favorites/folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name })
        })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            if (data.success) {
                hideFolderModal();
                loadFavorites();
            } else {
                modalHint.textContent = data.message || '创建失败';
                modalHint.style.display = 'block';
            }
        })
        .catch(function() {
            modalHint.textContent = '请求失败，请重试';
            modalHint.style.display = 'block';
        });
    }

    function renameFolder(folderId, name) {
        fetch('/profile/favorites/folder/' + folderId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name })
        })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            if (data.success) {
                hideFolderModal();
                loadFavorites();
            } else {
                modalHint.textContent = data.message || '重命名失败';
                modalHint.style.display = 'block';
            }
        })
        .catch(function() {
            modalHint.textContent = '请求失败，请重试';
            modalHint.style.display = 'block';
        });
    }

    function deleteFolder(folderId) {
        fetch('/profile/favorites/folder/' + folderId, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
            if (data.success) {
                if (currentFolderId === folderId) {
                    currentFolderId = null;
                }
                loadFavorites();
            } else {
                alert(data.message || '删除失败');
            }
        })
        .catch(function() {
            alert('请求失败，请重试');
        });
    }

    // ---------- 加载收藏夹数据 ----------
    function loadFavorites() {
        if (typeof favoritesData !== 'undefined') {
            if (isMe) {
                fetch('/profile/favorites/data')
                    .then(function(resp) { return resp.json(); })
                    .then(function(data) {
                        if (data.success) {
                            renderFolders(data.data);
                        } else {
                            renderFolders(favoritesData);
                        }
                    })
                    .catch(function() {
                        renderFolders(favoritesData);
                    });
            } else {
                renderFolders(favoritesData);
            }
        } else {
            console.warn('favoritesData 未定义');
            renderFolders([]);
        }
    }

    // ---------- 新建按钮 ----------
    var addBtn = document.getElementById('add-folder-btn');
    if (addBtn) {
        addBtn.addEventListener('click', function() {
            if (isMe) showFolderModal('create');
        });
    }

    // ---------- 暴露加载函数 ----------
    window.loadFavorites = loadFavorites;

    // ---------- 初始化 ----------
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            if (document.getElementById('tab-favorites') && document.getElementById('tab-favorites').classList.contains('active')) {
                loadFavorites();
            }
        });
    } else {
        if (document.getElementById('tab-favorites') && document.getElementById('tab-favorites').classList.contains('active')) {
            loadFavorites();
        }
    }
})();