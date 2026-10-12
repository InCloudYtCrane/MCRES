// mcres/static/js/pages/resource/edit/children/shaderpack_preset_new.js
(function() {
      'use strict';

      // ---------- 后端注入数据 ----------
      var presetResource = window.PRESET_FORM.resource;
      var reviewId = window.PRESET_FORM.reviewId;
      var presetId = window.PRESET_FORM.presetId;
      var shaderpackId = window.PRESET_FORM.shaderpackId;
      var canSkipReview = window.PRESET_FORM.canSkipReview;

      var changeSummary = window.PRESET_FORM.changeSummary;
      var messenger = window.PRESET_FORM.messenger;

      // ---------- 全局状态 ----------
      var screenshotList = [];
      if (presetResource && presetResource.screenshots) {
          screenshotList = presetResource.screenshots.slice();
      }
      var MAX_SCREENSHOTS = 6;
      var MIN_SCREENSHOTS = 1;
      var MAX_FILE_SIZE = 10 * 1024 * 1024;

      // DOM 引用
      var uploadBox = document.getElementById('screenshotUpload');
      var fileInput = document.getElementById('screenshotInput');
      var previewArea = document.getElementById('screenshotPreviewArea');
      var clearBtn = document.getElementById('screenshotClear');
      var listContainer = document.getElementById('screenshotList');

      var cropModal = document.getElementById('cropModal');
      var cropImage = document.getElementById('cropImage');
      var closeCropBtn = document.getElementById('closeCropBtn');
      var cancelCropBtn = document.getElementById('cancelCropBtn');
      var confirmCropBtn = document.getElementById('confirmCropBtn');

      var submitModal = document.getElementById('submitModal');
      var submitModalTitle = document.getElementById('submitModalTitle');
      var submitModalBody = document.getElementById('submitModalBody');
      var submitModalProgress = document.getElementById('submitModalProgress');
      var submitProgressText = document.getElementById('submitProgressText');
      var submitModalCancel = document.getElementById('submitModalCancel');
      var submitModalConfirm = document.getElementById('submitModalConfirm');

      var cropper = null;
      var cropResolve = null;

      // ---------- 回填传话筒和改动说明 ----------
      var messengerEl = document.getElementById('messenger');
      if (messengerEl) messengerEl.value = messenger;
      var changeEl = document.getElementById('changeSummary');
      if (changeEl) changeEl.value = changeSummary;

      // ---------- 截图 UI 更新 ----------
      function updateUI() {
          var count = screenshotList.length;
          if (count > 0) {
              previewArea.style.display = 'block';
              previewArea.textContent = '✅ 已上传 ' + count + ' 张截图';
              uploadBox.classList.add('has-image');
          } else {
              previewArea.style.display = 'none';
              previewArea.textContent = '';
              uploadBox.classList.remove('has-image');
          }
          listContainer.innerHTML = '';
          screenshotList.forEach(function(src, index) {
              var item = document.createElement('div');
              item.className = 'screenshot-item';
              var img = document.createElement('img');
              img.src = src;
              img.alt = '截图 ' + (index+1);
              var del = document.createElement('button');
              del.className = 'del-screenshot';
              del.textContent = '✕';
              del.type = 'button';
              del.addEventListener('click', function(e) {
                  e.stopPropagation();
                  screenshotList.splice(index, 1);
                  updateUI();
              });
              item.appendChild(img);
              item.appendChild(del);
              listContainer.appendChild(item);
          });
          window._screenshotsBase64 = screenshotList;
      }

      // ---------- 裁剪相关 ----------
      function openCropModal(file) {
          return new Promise(function(resolve) {
              var reader = new FileReader();
              reader.onload = function(e) {
                  cropImage.src = e.target.result;
                  cropModal.style.display = 'flex';
                  if (cropper) cropper.destroy();
                  cropper = new Cropper(cropImage, {
                      aspectRatio: 16 / 10,
                      viewMode: 1,
                      dragMode: 'move',
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
                  cropResolve = resolve;
              };
              reader.readAsDataURL(file);
          });
      }

      function closeCropModal() {
          if (cropper) {
              cropper.destroy();
              cropper = null;
          }
          cropImage.src = '';
          cropModal.style.display = 'none';
          if (cropResolve) {
              cropResolve(null);
              cropResolve = null;
          }
      }

      function confirmCrop() {
          if (!cropper) return;
          var canvas = cropper.getCroppedCanvas({
              width: 1280,
              height: 800,
              imageSmoothingQuality: 'high',
          });
          var dataUrl = canvas.toDataURL('image/jpeg', 0.85);
          if (cropResolve) {
              cropResolve(dataUrl);
              cropResolve = null;
          }
          closeCropModal();
      }

      closeCropBtn.addEventListener('click', closeCropModal);
      cancelCropBtn.addEventListener('click', closeCropModal);
      confirmCropBtn.addEventListener('click', confirmCrop);
      cropModal.addEventListener('click', function(e) {
          if (e.target === this) closeCropModal();
      });
      document.addEventListener('keydown', function(e) {
          if (e.key === 'Escape' && cropModal.style.display === 'flex') {
              closeCropModal();
          }
      });

      // ---------- 截图上传处理 ----------
      function handleFiles(files) {
          if (!files || files.length === 0) return;
          if (screenshotList.length >= MAX_SCREENSHOTS) {
              Toast.warning('最多只能上传 ' + MAX_SCREENSHOTS + ' 张截图');
              return;
          }
          var processNext = function(index) {
              if (index >= files.length) {
                  fileInput.value = '';
                  return;
              }
              if (screenshotList.length >= MAX_SCREENSHOTS) {
                  Toast.warning('已达到 ' + MAX_SCREENSHOTS + ' 张上限，剩余截图忽略');
                  fileInput.value = '';
                  return;
              }
              var file = files[index];
              var allowedTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
              if (!allowedTypes.includes(file.type)) {
                  Toast.warning('不支持的文件格式，请使用 JPG / PNG / WebP / GIF');
                  processNext(index + 1);
                  return;
              }
              if (file.size > MAX_FILE_SIZE) {
                  Toast.warning('图片大小不能超过 10MB');
                  processNext(index + 1);
                  return;
              }
              openCropModal(file).then(function(croppedDataUrl) {
                  if (croppedDataUrl) {
                      screenshotList.push(croppedDataUrl);
                      updateUI();
                  }
                  processNext(index + 1);
              });
          };
          processNext(0);
      }

      uploadBox.addEventListener('click', function(e) {
          if (clearBtn && clearBtn.contains(e.target)) return;
          if (screenshotList.length >= MAX_SCREENSHOTS) {
              Toast.warning('最多只能上传 ' + MAX_SCREENSHOTS + ' 张截图');
              return;
          }
          fileInput.click();
      });

      fileInput.addEventListener('change', function() {
          if (this.files.length) {
              handleFiles(this.files);
          } else {
              this.value = '';
          }
      });

      clearBtn.addEventListener('click', function(e) {
          e.stopPropagation();
          if (screenshotList.length === 0) return;
          if (confirm('确定要清除所有已上传的截图吗？')) {
              screenshotList = [];
              updateUI();
              fileInput.value = '';
          }
      });

      uploadBox.addEventListener('dragover', function(e) {
          e.preventDefault();
          this.style.borderColor = 'var(--primary, #f5a623)';
      });
      uploadBox.addEventListener('dragleave', function(e) {
          e.preventDefault();
          this.style.borderColor = '#3b434d';
      });
      uploadBox.addEventListener('drop', function(e) {
          e.preventDefault();
          this.style.borderColor = '#3b434d';
          var files = e.dataTransfer.files;
          if (files.length) {
              handleFiles(files);
          }
      });

      // ---------- 初始化截图 ----------
      updateUI();

      // ---------- 富文本编辑器 ----------
      var editorContainer = document.getElementById('presetEditor');
      if (editorContainer && typeof McresEditor !== 'undefined') {
          var initialDesc = presetResource ? presetResource.description || '' : '';
          window._presetEditor = new McresEditor(
              editorContainer,
              initialDesc,
              '在这里编写预设介绍……'
          );
      } else {
          window._presetEditor = null;
          console.warn('McresEditor 未加载');
      }

      // ---------- 自动扩展配置文件文本域 ----------
      var configCode = document.getElementById('config_code');
      if (configCode) {
          function autoResize() {
              if (!configCode) return;
              requestAnimationFrame(function() {
                  configCode.style.height = 'auto';
                  configCode.style.height = configCode.scrollHeight + 'px';
              });
          }
          configCode.addEventListener('input', autoResize);
          if (document.readyState === 'complete') {
              setTimeout(autoResize, 100);
          } else {
              window.addEventListener('load', function() {
                  setTimeout(autoResize, 100);
                  setTimeout(autoResize, 300);
              });
          }
          window.addEventListener('resize', function() {
              if (configCode.value.trim()) {
                  autoResize();
              }
          });
          setTimeout(autoResize, 50);
      }

      // ---------- Tab 切换 ----------
      document.querySelectorAll('.tab-btn').forEach(function(btn) {
          btn.addEventListener('click', function() {
              document.querySelectorAll('.tab-btn').forEach(function(b) {
                  b.classList.remove('active');
              });
              document.querySelectorAll('.section').forEach(function(s) {
                  s.classList.remove('active');
              });
              this.classList.add('active');
              document.getElementById(this.dataset.tab).classList.add('active');
          });
      });

      // ---------- 加载站内规则 ----------
      (function loadRules() {
          const container = document.getElementById('rulesSidebarList');
          if (!container) return;

          container.innerHTML = '<div style="color:#6b7480;font-size:13px;padding:4px 0;">加载规则…</div>';

          fetch('/api/rules/list')
              .then(res => res.json())
              .then(data => {
                  if (!data.success || !data.data || data.data.length === 0) {
                      container.innerHTML = '<div style="color:#6b7480;font-size:13px;padding:4px 0;">暂无规则</div>';
                      return;
                  }
                  let html = '';
                  data.data.forEach(rule => {
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
                  container.innerHTML = '<div style="color:#6b7480;font-size:13px;padding:4px 0;">加载失败</div>';
              });
      })();

      // ---------- 提交模态框管理 ----------
      var submitModalResolve = null;
      var submitModalReject = null;

      function showSubmitModal(options) {
          return new Promise(function(resolve, reject) {
              submitModalTitle.textContent = options.title || '确认提交';
              submitModalBody.textContent = options.message || '确定要提交吗？';
              submitModalConfirm.textContent = options.confirmText || '确定';
              submitModalCancel.textContent = options.cancelText || '取消';
              submitModalProgress.style.display = 'none';
              submitProgressText.textContent = '';
              submitModalConfirm.disabled = false;
              submitModalCancel.disabled = false;
              submitModal.style.display = 'flex';
              submitModalResolve = resolve;
              submitModalReject = reject;

              var newConfirm = submitModalConfirm.cloneNode(true);
              submitModalConfirm.parentNode.replaceChild(newConfirm, submitModalConfirm);
              submitModalConfirm = newConfirm;
              var newCancel = submitModalCancel.cloneNode(true);
              submitModalCancel.parentNode.replaceChild(newCancel, submitModalCancel);
              submitModalCancel = newCancel;

              submitModalCancel.addEventListener('click', function() {
                  submitModal.style.display = 'none';
                  if (submitModalReject) submitModalReject(new Error('用户取消'));
              });

              submitModalConfirm.addEventListener('click', async function() {
                  var confirmBtn = this;
                  var cancelBtn = submitModalCancel;
                  confirmBtn.disabled = true;
                  cancelBtn.disabled = true;
                  submitModalBody.style.display = 'none';
                  submitModalProgress.style.display = 'block';
                  submitProgressText.textContent = '开始提交...';

                  try {
                      if (typeof options.onConfirm === 'function') {
                          var result = await options.onConfirm(function(msg) {
                              submitProgressText.textContent = msg;
                          });
                          submitProgressText.textContent = canSkipReview ? '✅ 提交完成！' : '✅ 提交完成，等待审核。';
                          setTimeout(function() {
                              submitModal.style.display = 'none';
                              confirmBtn.disabled = false;
                              cancelBtn.disabled = false;
                              submitModalBody.style.display = 'block';
                              submitModalProgress.style.display = 'none';
                              if (typeof options.onSuccess === 'function') {
                                  options.onSuccess(result);
                              }
                              if (submitModalResolve) submitModalResolve(result);
                          }, 1200);
                      }
                  } catch (err) {
                      submitProgressText.textContent = '❌ 提交失败：' + err.message;
                      confirmBtn.disabled = false;
                      cancelBtn.disabled = false;
                      if (submitModalReject) submitModalReject(err);
                  }
              });
          });
      }

      // ---------- 提交逻辑 ----------
      document.getElementById('submitBtn').addEventListener('click', function() {
          if (document.getElementById('presetForm').classList.contains('locked')) {
              Toast.warning('该预设正在审核中，暂时无法编辑');
              return;
          }

          var presetName = document.getElementById('preset_name').value.trim();
          var shaderVersion = document.getElementById('shader_version').value.trim();
          var mcVersion = document.getElementById('mc_version').value.trim();
          var configCodeVal = document.getElementById('config_code').value.trim();
          var configNotes = document.getElementById('config_notes').value.trim();
          var changeSummary = document.getElementById('changeSummary').value.trim();
          var messengerEl = document.getElementById('messenger');
          var messenger = messengerEl ? messengerEl.value.trim() : '';
          var description = window._presetEditor ? window._presetEditor.getData() : '';
          var screenshots = screenshotList;

          var errors = [];
          if (!presetName) errors.push('请填写「预设名称」');
          if (screenshots.length < MIN_SCREENSHOTS) errors.push('请至少上传一张「预设截图」');
          if (!shaderVersion) errors.push('请填写「光影包版本」');
          if (!mcVersion) errors.push('请填写「游戏版本」');
          if (!configCodeVal) errors.push('请填写「配置文件内容」');

          if (errors.length > 0) {
              Toast.warning('请完善以下必填项：\n\n• ' + errors.join('\n• '));
              return;
          }

          var payload = {
              name: presetName,
              shader_version: shaderVersion,
              mc_version: mcVersion,
              description: description,
              config_code: configCodeVal,
              config_notes: configNotes,
              screenshots: screenshots,
              change_summary: changeSummary || '',
              messenger: messenger || ''
          };

          var apiUrl;
          if (presetId) {
              apiUrl = '/shaderpack/' + shaderpackId + '/preset/edit/' + presetId;
          } else {
              apiUrl = '/shaderpack/' + shaderpackId + '/preset/new';
              if (reviewId) {
                  payload.review_id = parseInt(reviewId, 10);
              }
          }

          var submitBtn = document.getElementById('submitBtn');
          submitBtn.disabled = true;
          submitBtn.textContent = presetId ? '更新中…' : '提交中…';

          showSubmitModal({
              title: '确认提交',
              message: '确定要' + (presetId || reviewId ? '更新' : '发布') + '此预设吗？',
              onConfirm: async function(updateProgress) {
                  updateProgress('提交数据中…');
                  var response = await fetch(apiUrl, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(payload),
                  });
                  if (!response.ok) {
                      var errMsg = 'HTTP ' + response.status;
                      try {
                          var errData = await response.json();
                          errMsg = errData.message || errMsg;
                      } catch (_) {}
                      throw new Error(errMsg);
                  }
                  var data = await response.json();
                  updateProgress('处理响应…');
                  return data;
              },
              onSuccess: function(data) {
                  if (data.redirect_url) {
                      window.location.href = data.redirect_url;
                  } else {
                      window.location.href = '/shaderpack/' + shaderpackId;
                  }
              }
          }).catch(function(err) {
              if (err.message !== '用户取消') {
                  console.error(err);
                  Toast.warning('提交失败：' + err.message);
              }
          }).finally(function() {
              submitBtn.disabled = false;
              submitBtn.textContent = presetId ? '更新预设' : '发布预设';
          });
      });

      console.log('✅ 预设页面已加载');
  })();
