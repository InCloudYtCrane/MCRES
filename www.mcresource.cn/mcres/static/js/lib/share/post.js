/**
 * MCRES 分享海报生成器
 * 路径：
 * /static/js/lib/share/post.js
 *
 * 特点：
 * - 固定 1 : √2 竖版比例
 * - 1200 × 1697
 * - 所有截图尽可能全部显示
 * - 截图数量增加不会增加海报高度
 * - 不规则错位 / 旋转 / 拼贴
 * - 自动压缩截图尺寸避免大面积留白
 * - MCRES Logo
 * - QRCode.js 二维码
 * - 作者署名显示在标题下方 (by xxx)
 */

(function () {
  "use strict";

  // =========================================================
  // 基础配置
  // =========================================================

  const POSTER_WIDTH = 1200;
  const POSTER_HEIGHT = Math.round(POSTER_WIDTH * Math.SQRT2);

  const LOGO_URL = "https://www.mcresource.cn/images/logo/logo.png";

  const COLORS = ["#00d9ff", "#7c4dff", "#ff3d9a", "#ffb300", "#00c896"];

  const BG = "#0b1018";

  // =========================================================
  // 对外入口
  // =========================================================

  window.generatePoster = async function () {
    try {
      const data = window.RESOURCE_DATA || {};

      if (!data.main_name) {
        posterToast("无法获取资源信息");
        return;
      }

      posterToast("正在生成海报…");

      await createPoster(data);
    } catch (error) {
      console.error("❌ 海报生成失败：", error);
      posterToast("海报生成失败，请检查控制台");
    }
  };

  // =========================================================
  // 主函数
  // =========================================================

  async function createPoster(data) {
    const canvas = document.createElement("canvas");

    canvas.width = POSTER_WIDTH;
    canvas.height = POSTER_HEIGHT;

    const ctx = canvas.getContext("2d");

    if (!ctx) {
      throw new Error("无法创建 Canvas 2D 上下文");
    }

    // -----------------------------------------------------
    // 规范数据
    // -----------------------------------------------------

    const screenshots = Array.isArray(data.screenshots)
      ? data.screenshots.filter(Boolean)
      : [];

    const resourceType = getResourceType();

    const accent = getAccentColor(resourceType);

    // -----------------------------------------------------
    // 预加载所有图片
    // -----------------------------------------------------

    posterToast("正在加载图片…");

    const coverPromise = data.cover
      ? loadImage(data.cover)
      : Promise.resolve(null);

    const logoPromise = loadImage(LOGO_URL);

    const screenshotPromises = screenshots.map((src) =>
      loadImage(src).catch((err) => {
        console.warn("⚠️ 截图加载失败：", src, err);
        return null;
      }),
    );

    const [cover, logo, screenshotImages] = await Promise.all([
      coverPromise.catch(() => null),
      logoPromise.catch(() => null),
      Promise.all(screenshotPromises),
    ]);

    const validScreenshots = screenshotImages.filter(Boolean);

    // -----------------------------------------------------
    // 背景
    // -----------------------------------------------------

    drawBackground(ctx);

    // -----------------------------------------------------
    // 背景装饰
    // -----------------------------------------------------

    drawDecorations(ctx);

    // -----------------------------------------------------
    // Hero 封面
    // -----------------------------------------------------

    drawHero(ctx, cover, data, accent);

    // -----------------------------------------------------
    // 标题
    // -----------------------------------------------------

    drawTitleBlock(ctx, data, accent, resourceType, validScreenshots.length);

    // -----------------------------------------------------
    // 截图拼贴
    // -----------------------------------------------------

    if (validScreenshots.length > 0) {
      posterToast(`正在排版 ${validScreenshots.length} 张截图…`);

      drawScreenshotGallery(ctx, validScreenshots, accent);
    }

    // -----------------------------------------------------
    // 二维码
    // -----------------------------------------------------

    const qrData = data.url || window.location.href;

    try {
      const qrCanvas = await generateQRCode(qrData);

      drawQRCode(ctx, qrCanvas, accent);
    } catch (error) {
      console.warn("⚠️ 二维码生成失败：", error);
    }

    // -----------------------------------------------------
    // 底部品牌
    // -----------------------------------------------------

    drawFooter(ctx, logo);

    // -----------------------------------------------------
    // 下载
    // -----------------------------------------------------

    await downloadPoster(canvas, data.main_name);

    posterToast("海报已生成");
  }

  // =========================================================
  // 资源类型
  // =========================================================

  function getResourceType() {
    const type =
      window.RESOURCE_TYPE || document.body.dataset.resourceType || "";

    const map = {
      resourcepack: "资源包",
      shaderpack: "光影包",
      map: "地图",
      shader: "光影包",
      resource: "资源包",
    };

    return map[type] || "Minecraft 资源";
  }

  // =========================================================
  // 主题颜色
  // =========================================================

  function getAccentColor(type) {
    if (type === "光影包") {
      return "#f5a623";
    }

    if (type === "资源包") {
      return "#55d88b";
    }

    if (type === "地图") {
      return "#4aa8ff";
    }

    return "#7c4dff";
  }

  // =========================================================
  // 背景
  // =========================================================

  function drawBackground(ctx) {
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, POSTER_WIDTH, POSTER_HEIGHT);

    // ---------------------------------------------
    // 左上色彩光
    // ---------------------------------------------

    let g1 = ctx.createRadialGradient(40, 100, 0, 40, 100, 550);

    g1.addColorStop(0, "rgba(0, 217, 255, 0.18)");

    g1.addColorStop(1, "rgba(0, 217, 255, 0)");

    ctx.fillStyle = g1;

    ctx.fillRect(0, 0, POSTER_WIDTH, 700);

    // ---------------------------------------------
    // 右上紫色光
    // ---------------------------------------------

    let g2 = ctx.createRadialGradient(1120, 300, 0, 1120, 300, 500);

    g2.addColorStop(0, "rgba(124, 77, 255, 0.18)");

    g2.addColorStop(1, "rgba(124, 77, 255, 0)");

    ctx.fillStyle = g2;

    ctx.fillRect(600, 0, 600, 800);

    // ---------------------------------------------
    // 下部粉色
    // ---------------------------------------------

    let g3 = ctx.createRadialGradient(850, 1350, 0, 850, 1350, 600);

    g3.addColorStop(0, "rgba(255, 61, 154, 0.10)");

    g3.addColorStop(1, "rgba(255, 61, 154, 0)");

    ctx.fillStyle = g3;

    ctx.fillRect(300, 900, 900, 700);

    // ---------------------------------------------
    // 顶部彩色线
    // ---------------------------------------------

    const gradient = ctx.createLinearGradient(0, 0, POSTER_WIDTH, 0);

    gradient.addColorStop(0, "#00d9ff");
    gradient.addColorStop(0.25, "#4aa8ff");
    gradient.addColorStop(0.5, "#7c4dff");
    gradient.addColorStop(0.75, "#ff3d9a");
    gradient.addColorStop(1, "#ffb300");

    ctx.fillStyle = gradient;

    ctx.fillRect(0, 0, POSTER_WIDTH, 8);
  }

  // =========================================================
  // 背景随机装饰
  // =========================================================

  function drawDecorations(ctx) {
    const seed = getSeed(
      String(window.RESOURCE_ID || window.RESOURCE_DATA?.main_name || "mcres"),
    );

    const random = seededRandom(seed);

    // ---------------------------------------------
    // 小点
    // ---------------------------------------------

    for (let i = 0; i < 65; i++) {
      const x = 20 + random() * (POSTER_WIDTH - 40);

      const y = 30 + random() * (POSTER_HEIGHT - 70);

      const radius = 1.5 + random() * 4;

      const color = COLORS[Math.floor(random() * COLORS.length)];

      ctx.globalAlpha = 0.35 + random() * 0.5;

      ctx.fillStyle = color;

      ctx.beginPath();

      ctx.arc(x, y, radius, 0, Math.PI * 2);

      ctx.fill();
    }

    ctx.globalAlpha = 1;

    // ---------------------------------------------
    // 彩色短线
    // ---------------------------------------------

    for (let i = 0; i < 28; i++) {
      const x = random() * POSTER_WIDTH;

      const y = 30 + random() * (POSTER_HEIGHT - 60);

      const width = 20 + random() * 75;

      const color = COLORS[Math.floor(random() * COLORS.length)];

      ctx.globalAlpha = 0.25 + random() * 0.35;

      ctx.strokeStyle = color;

      ctx.lineWidth = 2;

      ctx.beginPath();

      ctx.moveTo(x, y);

      ctx.lineTo(x + width, y - 5 + random() * 10);

      ctx.stroke();
    }

    ctx.globalAlpha = 1;

    // ---------------------------------------------
    // 圆环
    // ---------------------------------------------

    for (let i = 0; i < 7; i++) {
      const x = 50 + random() * (POSTER_WIDTH - 100);

      const y = 400 + random() * 1100;

      const radius = 35 + random() * 80;

      const color = COLORS[Math.floor(random() * COLORS.length)];

      ctx.globalAlpha = 0.16;

      ctx.strokeStyle = color;

      ctx.lineWidth = 2;

      ctx.beginPath();

      ctx.arc(x, y, radius, 0, Math.PI * 2);

      ctx.stroke();
    }

    ctx.globalAlpha = 1;
  }

  // =========================================================
  // Logo
  // =========================================================
  // Logo 不再在这里绘制。
  // Logo 统一在 drawFooter() 中与 MCRES · 方块工坊组合。
  // =========================================================

  function drawLogo(ctx, logo) {
    // 保留函数，避免其他代码调用时报错。
    // 实际底部 Logo 由 drawFooter() 绘制。
  }

  // =========================================================
  // Hero 封面
  // =========================================================

  function drawHero(ctx, cover, data, accent) {
    const x = 60;
    const y = 95;

    const width = 1080;
    const height = 515;

    ctx.save();

    // ---------------------------------------------
    // 阴影
    // ---------------------------------------------

    ctx.shadowColor = "rgba(0,0,0,0.65)";

    ctx.shadowBlur = 35;

    ctx.shadowOffsetY = 18;

    // ---------------------------------------------
    // 轻微旋转
    // ---------------------------------------------

    ctx.translate(x + width / 2, y + height / 2);

    ctx.rotate(-0.012);

    ctx.translate(-width / 2, -height / 2);

    // ---------------------------------------------
    // 图片裁剪
    // ---------------------------------------------

    ctx.beginPath();

    ctx.rect(0, 0, width, height);

    ctx.clip();

    if (cover) {
      drawImageCover(ctx, cover, 0, 0, width, height);
    } else {
      ctx.fillStyle = "#242b35";

      ctx.fillRect(0, 0, width, height);

      ctx.fillStyle = "#ffffff";

      ctx.font = "bold 42px Arial, sans-serif";

      ctx.textAlign = "center";

      ctx.textBaseline = "middle";

      ctx.fillText("暂无资源封面", width / 2, height / 2);
    }

    ctx.restore();

    // ---------------------------------------------
    // 彩色边框
    // ---------------------------------------------

    ctx.save();

    ctx.translate(x + width / 2, y + height / 2);

    ctx.rotate(-0.012);

    ctx.translate(-width / 2, -height / 2);

    ctx.strokeStyle = accent;

    ctx.lineWidth = 8;

    ctx.strokeRect(0, 0, width, height);

    ctx.restore();
  }

  // =========================================================
  // 标题区域（包含作者署名）
  // =========================================================

  function drawTitleBlock(ctx, data, accent, resourceType, screenshotCount) {
    const x = 62;
    const y = 555;

    const width = 760;
    const height = 185;

    ctx.save();

    // ---------------------------------------------
    // 黑色半透明标题板
    // ---------------------------------------------

    ctx.fillStyle = "rgba(6,10,16,0.94)";

    ctx.fillRect(x, y, width, height);

    // ---------------------------------------------
    // 左侧彩条
    // ---------------------------------------------

    ctx.fillStyle = "#00d9ff";

    ctx.fillRect(x, y, 8, height);

    // ---------------------------------------------
    // 彩色装饰块
    // ---------------------------------------------

    ctx.save();

    ctx.translate(x + width + 50, y + 10);

    ctx.rotate(0.15);

    ctx.fillStyle = "#00d9ff";

    ctx.fillRect(0, 0, 52, 18);

    ctx.fillStyle = "#ff3d9a";

    ctx.fillRect(58, 6, 44, 18);

    ctx.fillStyle = "#ffb300";

    ctx.fillRect(108, 12, 30, 18);

    ctx.restore();

    // ---------------------------------------------
    // 标题
    // ---------------------------------------------

    ctx.fillStyle = "#ffffff";

    ctx.font = 'bold 54px "Microsoft YaHei", "Noto Sans SC", Arial, sans-serif';

    ctx.textAlign = "left";

    ctx.textBaseline = "top";

    const title = String(data.main_name || "MCRES资源");

    const titleLines = wrapText(ctx, title, width - 60, 54);

    let titleY = y + 20;

    titleLines.slice(0, 2).forEach((line) => {
      ctx.fillText(line, x + 30, titleY);

      titleY += 64;
    });

    // =============================================
    // ===== 新增：作者署名 (by xxx) =====
    // =============================================

    const authorsData = data.authors_display || [];

    if (authorsData.length > 0) {
      // 提取作者名称
      let authorNames = authorsData
        .map((a) => {
          if (typeof a === "string") return a;
          if (a && typeof a === "object" && a.display) return a.display;
          return null;
        })
        .filter(Boolean);

      if (authorNames.length > 0) {
        const byText = "by " + authorNames.join("、");

        ctx.fillStyle = "rgba(220,230,240,0.75)";

        ctx.font = '20px "Microsoft YaHei", Arial, sans-serif';

        ctx.textAlign = "left";

        ctx.textBaseline = "top";

        ctx.fillText(byText, x + 30, titleY + 6);

        // 更新 titleY 以便简介位置下移
        titleY += 38;
      }
    }

    // ---------------------------------------------
    // 简介
    // ---------------------------------------------

    const summary = String(data.summary || "").trim();

    if (summary) {
      ctx.fillStyle = "rgba(220,230,240,0.65)";

      ctx.font = '18px "Microsoft YaHei", Arial, sans-serif';

      const summaryLines = wrapText(ctx, summary, width - 60, 18);

      let sy = Math.min(y + 122, titleY + 5);

      summaryLines.slice(0, 2).forEach((line) => {
        ctx.fillText(line, x + 30, sy);

        sy += 27;
      });
    }

    ctx.restore();

    // ---------------------------------------------
    // 标签
    // ---------------------------------------------

    const tags = [resourceType, "Minecraft"];

    if (screenshotCount > 0) {
      tags.push(`${screenshotCount} 张截图`);
    }

    let tx = 65;
    const ty = 765;

    tags.forEach((tag, index) => {
      const color = COLORS[index % COLORS.length];

      const textWidth = measureText(ctx, tag, 19);

      const tagWidth = textWidth + 34;

      ctx.fillStyle = color;

      ctx.fillRect(tx, ty, tagWidth, 42);

      ctx.fillStyle = "#ffffff";

      ctx.font = 'bold 19px "Microsoft YaHei", Arial, sans-serif';

      ctx.textAlign = "center";

      ctx.textBaseline = "middle";

      ctx.fillText(tag, tx + tagWidth / 2, ty + 21);

      tx += tagWidth + 22;
    });
  }

  // =========================================================
  // 截图拼贴
  // =========================================================

  function drawScreenshotGallery(ctx, images, accent) {
    /*
     * 固定区域：
     *
     * y = 830
     * bottom = 1565
     *
     * 不管有多少截图，
     * 海报高度永远不会改变。
     */

    const area = {
      x: 55,
      y: 825,
      width: 1090,
      height: 720,
    };

    const layouts = createJustifiedLayout(images, area);

    layouts.forEach((item, index) => {
      drawScreenshotCard(ctx, item, index, accent);
    });
  }

  // =========================================================
  // 自动拼图布局
  // =========================================================

  function createJustifiedLayout(images, area) {
    const seed = getSeed(String(window.RESOURCE_ID || images.length));

    const random = seededRandom(seed);

    const count = images.length;

    /*
     * 根据截图数量自动确定行数。
     *
     * 1~3：1行
     * 4~6：2行
     * 7~9：3行
     * 10~12：4行
     * 13+：根据数量继续增加
     */

    let rowCount;

    if (count <= 3) {
      rowCount = 1;
    } else if (count <= 6) {
      rowCount = 2;
    } else if (count <= 9) {
      rowCount = 3;
    } else if (count <= 12) {
      rowCount = 4;
    } else {
      rowCount = Math.ceil(count / 3);
    }

    /*
     * 如果截图特别多，
     * 自动变成每行更多图片。
     */

    let targetPerRow = Math.ceil(count / rowCount);

    if (count >= 15) {
      targetPerRow = 4;
      rowCount = Math.ceil(count / targetPerRow);
    }

    // ---------------------------------------------
    // 先随机打乱索引
    // ---------------------------------------------

    const indices = images.map((_, i) => i);

    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(random() * (i + 1));

      [indices[i], indices[j]] = [indices[j], indices[i]];
    }

    // ---------------------------------------------
    // 按行分组
    // ---------------------------------------------

    const rows = [];

    let pointer = 0;

    for (let r = 0; r < rowCount; r++) {
      const remaining = count - pointer;

      const rowsLeft = rowCount - r;

      let amount = Math.ceil(remaining / rowsLeft);

      // 稍微随机一下
      if (rowsLeft > 1 && amount > 1 && random() > 0.65) {
        amount--;
      }

      amount = Math.max(1, amount);

      const row = indices.slice(pointer, pointer + amount);

      pointer += amount;

      rows.push(row);
    }

    // ---------------------------------------------
    // 行高
    // ---------------------------------------------

    const gap = 14;

    const totalGap = gap * (rows.length - 1);

    const usableHeight = area.height - totalGap;

    /*
     * 不是平均高度，
     * 而是根据数量稍微随机。
     */

    const heights = [];

    let remainHeight = usableHeight;

    for (let i = 0; i < rows.length; i++) {
      const remainingRows = rows.length - i;

      let h;

      if (remainingRows === 1) {
        h = remainHeight;
      } else {
        const min = (usableHeight / rows.length) * 0.82;

        const max = (usableHeight / rows.length) * 1.18;

        h = min + random() * (max - min);

        // 防止最后一行太小
        const maxAllowed =
          remainHeight -
          (remainingRows - 1) * ((usableHeight / rows.length) * 0.72);

        h = Math.min(h, maxAllowed);
      }

      h = Math.max(120, h);

      heights.push(h);

      remainHeight -= h;
    }

    // 如果误差存在，最后修正
    const heightSum = heights.reduce((a, b) => a + b, 0);

    const correction = usableHeight - heightSum;

    heights[heights.length - 1] += correction;

    // ---------------------------------------------
    // 创建最终卡片
    // ---------------------------------------------

    const result = [];

    let currentY = area.y;

    rows.forEach((row, rowIndex) => {
      const rowHeight = heights[rowIndex];

      /*
       * 每一行使用真实图片比例，
       * 这样横向基本可以铺满，
       * 不会产生大片空白。
       */

      const ratios = row.map((index) => {
        const img = images[index];

        return Math.max(0.7, Math.min(2.2, img.width / img.height));
      });

      const ratioSum = ratios.reduce((a, b) => a + b, 0);

      const innerWidth = area.width - gap * (row.length - 1);

      const unit = innerWidth / ratioSum;

      let currentX = area.x;

      row.forEach((imageIndex, i) => {
        const ratio = ratios[i];

        let width = unit * ratio;

        /*
         * 最后一张直接补齐，
         * 防止浮点误差导致右边空一条。
         */

        if (i === row.length - 1) {
          width = area.x + area.width - currentX;
        }

        // ---------------------------------
        // 错位
        // ---------------------------------

        const jitterX = (random() - 0.5) * 16;

        const jitterY = (random() - 0.5) * 14;

        const rotation = (random() - 0.5) * 0.075;

        result.push({
          image: images[imageIndex],

          index: imageIndex,

          x: currentX + jitterX,

          y: currentY + jitterY,

          width: width - 3,

          height: rowHeight - 3,

          rotation,
        });

        currentX += width + gap;
      });

      currentY += rowHeight + gap;
    });

    return result;
  }

  // =========================================================
  // 单张截图
  // =========================================================

  function drawScreenshotCard(ctx, item, index, accent) {
    const { image, x, y, width, height, rotation } = item;

    ctx.save();

    // ---------------------------------------------
    // 中心旋转
    // ---------------------------------------------

    ctx.translate(x + width / 2, y + height / 2);

    ctx.rotate(rotation);

    ctx.translate(-width / 2, -height / 2);

    // ---------------------------------------------
    // 阴影
    // ---------------------------------------------

    ctx.shadowColor = "rgba(0,0,0,0.65)";

    ctx.shadowBlur = 22;

    ctx.shadowOffsetY = 12;

    // ---------------------------------------------
    // 白色照片边框
    // ---------------------------------------------

    const border = 9;

    ctx.fillStyle = "#f5f6f8";

    ctx.fillRect(0, 0, width, height);

    ctx.shadowColor = "transparent";

    // ---------------------------------------------
    // 图片
    // ---------------------------------------------

    drawImageCover(
      ctx,
      image,
      border,
      border,
      width - border * 2,
      height - border * 2,
    );

    // ---------------------------------------------
    // 编号黑底
    // ---------------------------------------------

    const numberWidth = 52;

    const numberHeight = 28;

    ctx.fillStyle = "rgba(0,0,0,0.85)";

    ctx.fillRect(
      border,
      height - border - numberHeight,
      numberWidth,
      numberHeight,
    );

    ctx.fillStyle = "#ffffff";

    ctx.font = "bold 14px Arial, sans-serif";

    ctx.textAlign = "center";

    ctx.textBaseline = "middle";

    ctx.fillText(
      String(index + 1).padStart(2, "0"),
      border + numberWidth / 2,
      height - border - numberHeight / 2,
    );

    // ---------------------------------------------
    // 彩色小条
    // ---------------------------------------------

    const color = COLORS[index % COLORS.length];

    ctx.fillStyle = color;

    ctx.fillRect(14, -5, 48, 7);

    // ---------------------------------------------
    // 某些截图增加一个小角标
    // ---------------------------------------------

    if (index % 4 === 0) {
      ctx.fillStyle = color;

      ctx.fillRect(width - 60, height - 5, 42, 7);
    }

    ctx.restore();
  }

  // =========================================================
  // 二维码
  // =========================================================

  async function generateQRCode(url) {
    await loadQRCodeLibrary();

    if (typeof window.QRCode !== "function") {
      throw new Error("QRCode.js 未加载");
    }

    const container = document.createElement("div");

    container.style.position = "fixed";

    container.style.left = "-99999px";

    container.style.top = "-99999px";

    container.style.width = "360px";

    container.style.height = "360px";

    container.style.background = "#ffffff";

    container.style.padding = "0";

    document.body.appendChild(container);

    try {
      new window.QRCode(container, {
        text: String(url),
        width: 360,
        height: 360,
        colorDark: "#111111",
        colorLight: "#ffffff",
        correctLevel: window.QRCode.CorrectLevel.H,
      });

      return await waitQRCode(container);
    } finally {
      setTimeout(() => {
        container.remove();
      }, 1000);
    }
  }

  // =========================================================
  // 等待二维码
  // =========================================================

  function waitQRCode(container) {
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error("二维码生成超时"));
      }, 8000);

      const check = () => {
        const canvas = container.querySelector("canvas");

        if (canvas) {
          clearTimeout(timeout);

          resolve(canvas);

          return;
        }

        const img = container.querySelector("img");

        if (img && img.complete && img.naturalWidth > 0) {
          clearTimeout(timeout);

          const c = document.createElement("canvas");

          c.width = img.naturalWidth || 360;

          c.height = img.naturalHeight || 360;

          const cctx = c.getContext("2d");

          cctx.drawImage(img, 0, 0, c.width, c.height);

          resolve(c);

          return;
        }

        requestAnimationFrame(check);
      };

      check();
    });
  }

  // =========================================================
  // 加载 QRCode.js
  // =========================================================

  function loadQRCodeLibrary() {
    if (typeof window.QRCode === "function") {
      return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
      const existing = document.querySelector("script[data-mcres-qrcode]");

      if (existing) {
        existing.addEventListener("load", () => resolve());

        existing.addEventListener("error", reject);

        return;
      }

      const script = document.createElement("script");

      script.src = "https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js";

      script.async = true;

      script.dataset.mcresQrcode = "true";

      script.onload = () => {
        if (typeof window.QRCode === "function") {
          resolve();
        } else {
          reject(new Error("QRCode.js 加载完成但对象不存在"));
        }
      };

      script.onerror = () => {
        reject(new Error("QRCode.js 加载失败"));
      };

      document.head.appendChild(script);
    });
  }

  // =========================================================
  // 绘制二维码
  // =========================================================

  function drawQRCode(ctx, qrCanvas, accent) {
    const size = 215;

    const x = POSTER_WIDTH - size - 65;

    const y = POSTER_HEIGHT - size - 115;

    ctx.save();

    ctx.translate(x + size / 2, y + size / 2);

    // 稍微歪一点
    ctx.rotate(0.025);

    ctx.translate(-size / 2, -size / 2);

    // ---------------------------------------------
    // 白色二维码卡片
    // ---------------------------------------------

    ctx.shadowColor = "rgba(0,0,0,0.5)";

    ctx.shadowBlur = 25;

    ctx.shadowOffsetY = 8;

    ctx.fillStyle = "#ffffff";

    ctx.fillRect(0, 0, size, size);

    ctx.shadowColor = "transparent";

    // ---------------------------------------------
    // QR
    // ---------------------------------------------

    const padding = 16;

    ctx.drawImage(
      qrCanvas,
      padding,
      padding,
      size - padding * 2,
      size - padding * 2,
    );

    // ---------------------------------------------
    // 彩色装饰
    // ---------------------------------------------

    ctx.fillStyle = "#00d9ff";

    ctx.fillRect(-7, 35, 7, 60);

    ctx.fillStyle = "#ff3d9a";

    ctx.fillRect(-7, 100, 7, 42);

    ctx.fillStyle = "#ffb300";

    ctx.fillRect(size - 38, size - 6, 30, 6);

    ctx.restore();

    // ---------------------------------------------
    // SCAN TO OPEN
    // ---------------------------------------------

    ctx.save();

    ctx.fillStyle = "rgba(220,225,235,0.7)";

    ctx.font = "13px Arial, sans-serif";

    ctx.textAlign = "right";

    ctx.textBaseline = "middle";

    ctx.fillText("SCAN TO OPEN", x + size - 12, y + size + 25);

    ctx.restore();
  }

  // =========================================================
  // Footer（移除作者，只保留品牌信息）
  // =========================================================

  function drawFooter(ctx, logo) {
    const y = POSTER_HEIGHT - 48;

    // ---------------------------------------------
    // Logo
    // ---------------------------------------------

    let logoWidth = 0;
    let logoHeight = 0;

    if (logo) {
      const maxWidth = 58;
      const maxHeight = 38;

      const scale = Math.min(maxWidth / logo.width, maxHeight / logo.height);

      logoWidth = logo.width * scale;
      logoHeight = logo.height * scale;

      ctx.save();
      ctx.globalAlpha = 0.95;
      ctx.drawImage(logo, 60, y - logoHeight / 2, logoWidth, logoHeight);
      ctx.restore();
    }

    // ---------------------------------------------
    // MCRES · 方块工坊
    // ---------------------------------------------

    const brandX = 60 + (logoWidth > 0 ? logoWidth + 18 : 0);

    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 22px Arial, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText("MCRES", brandX, y);

    const mcresWidth = ctx.measureText("MCRES").width;

    ctx.fillStyle = "rgba(210,220,230,0.55)";
    ctx.font = '15px "Microsoft YaHei", Arial, sans-serif';
    ctx.fillText(" · 方块工坊", brandX + mcresWidth + 3, y);

    // ---------------------------------------------
    // 彩色短线
    // ---------------------------------------------

    let x = 315;
    COLORS.slice(0, 3).forEach((color) => {
      ctx.fillStyle = color;
      ctx.fillRect(x, y - 2, 52, 4);
      x += 67;
    });

    // ---------------------------------------------
    // 网站地址
    // ---------------------------------------------

    ctx.fillStyle = "rgba(210,220,230,0.65)";
    ctx.font = "15px Arial, sans-serif";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText("mcresource.cn", brandX, y + 28);

    // ---------------------------------------------
    // 右侧英文
    // ---------------------------------------------

    ctx.fillStyle = "rgba(180,190,205,0.45)";
    ctx.font = "13px Arial, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("Minecraft Resource Collection", POSTER_WIDTH - 60, y);
  }

  // =========================================================
  // 图片加载
  //
  // 跨域图片改用 fetch → blob → objectURL。
  // 理由：
  //   1. fetch 严格走 CORS，源站有合法 ACAO 头即可通过
  //   2. cache: 'no-store' 强制走网络，绕开旧缓存条目
  //   3. blob URL 是同源的，画到 canvas 不会污染
  //   4. 错误信息明确，方便定位
  // =========================================================

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      if (!src) {
        reject(new Error("图片地址为空"));
        return;
      }

      // ---------------------------------------------
      // 判断是否同源
      // ---------------------------------------------

      let sameOrigin = false;

      try {
        const u = new URL(src, window.location.href);
        sameOrigin = u.origin === window.location.origin;
      } catch (e) {
        // 解析失败按跨域处理
      }

      // ---------------------------------------------
      // 同源图片：直接用 <img>，不需要 CORS
      // ---------------------------------------------

      if (sameOrigin) {
        const img = new Image();

        img.onload = () => resolve(img);

        img.onerror = () => {
          reject(new Error("图片加载失败：" + src));
        };

        img.src = src;

        return;
      }

      // ---------------------------------------------
      // 跨域图片：fetch → blob → objectURL
      // ---------------------------------------------

      (async () => {
        let res;

        try {
          res = await fetch(src, {
            mode: "cors",
            credentials: "omit",
            cache: "no-store",
          });
        } catch (e) {
          reject(new Error("图片请求失败：" + src));

          return;
        }

        if (!res.ok) {
          reject(new Error("图片加载失败：" + src + " (" + res.status + ")"));

          return;
        }

        let blob;

        try {
          blob = await res.blob();
        } catch (e) {
          reject(new Error("图片读取失败：" + src));
          return;
        }

        const blobUrl = URL.createObjectURL(blob);

        const img = new Image();

        img.onload = () => {
          // 解码完成后延迟释放，避免图片未画完就失效
          setTimeout(() => URL.revokeObjectURL(blobUrl), 3000);

          resolve(img);
        };

        img.onerror = () => {
          URL.revokeObjectURL(blobUrl);

          reject(new Error("图片解码失败：" + src));
        };

        img.src = blobUrl;
      })();
    });
  }

  // =========================================================
  // 图片裁剪填充
  // =========================================================

  function drawImageCover(ctx, img, x, y, width, height) {
    const sourceRatio = img.width / img.height;

    const targetRatio = width / height;

    let sx = 0;
    let sy = 0;
    let sw = img.width;
    let sh = img.height;

    if (sourceRatio > targetRatio) {
      sw = img.height * targetRatio;

      sx = (img.width - sw) / 2;
    } else {
      sh = img.width / targetRatio;

      sy = (img.height - sh) / 2;
    }

    ctx.drawImage(img, sx, sy, sw, sh, x, y, width, height);
  }

  // =========================================================
  // 文本换行
  // =========================================================

  function wrapText(ctx, text, maxWidth) {
    const chars = String(text).split("");

    const lines = [];

    let line = "";

    chars.forEach((char) => {
      const test = line + char;

      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);

        line = char;
      } else {
        line = test;
      }
    });

    if (line) {
      lines.push(line);
    }

    return lines;
  }

  // =========================================================
  // 测量文字
  // =========================================================

  function measureText(ctx, text, size) {
    ctx.font = `bold ${size}px "Microsoft YaHei", Arial, sans-serif`;

    return ctx.measureText(text).width;
  }

  // =========================================================
  // 随机种子
  // =========================================================

  function getSeed(str) {
    let hash = 2166136261;

    for (let i = 0; i < str.length; i++) {
      hash ^= str.charCodeAt(i);

      hash +=
        (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
    }

    return hash >>> 0;
  }

  // =========================================================
  // 可复现随机
  // =========================================================

  function seededRandom(seed) {
    return function () {
      seed += 0x6d2b79f5;

      let t = seed;

      t = Math.imul(t ^ (t >>> 15), t | 1);

      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);

      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // =========================================================
  // 下载
  // =========================================================

  async function downloadPoster(canvas, name) {
    const safeName = String(name || "MCRES资源")
      .replace(/[\\/:*?"<>|]/g, "_")
      .trim();

    const filename = `${safeName}_MCRES海报.png`;

    canvas.toBlob((blob) => {
      if (!blob) {
        posterToast("海报导出失败");

        return;
      }

      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");

      a.href = url;

      a.download = filename;

      document.body.appendChild(a);

      a.click();

      a.remove();

      setTimeout(() => {
        URL.revokeObjectURL(url);
      }, 1000);
    }, "image/png");
  }

  // =========================================================
  // Toast
  // =========================================================

  function posterToast(message) {
    let toast = document.getElementById("mcresPosterToast");

    if (!toast) {
      toast = document.createElement("div");

      toast.id = "mcresPosterToast";

      Object.assign(toast.style, {
        position: "fixed",
        left: "50%",
        bottom: "30px",
        transform: "translateX(-50%)",
        zIndex: "999999",
        padding: "10px 20px",
        background: "#1d2229",
        border: "1px solid rgba(255,255,255,0.1)",
        color: "#fff",
        fontSize: "14px",
        boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
        pointerEvents: "none",
        opacity: "0",
        transition: "opacity .2s ease",
      });

      document.body.appendChild(toast);
    }

    toast.textContent = message;

    toast.style.opacity = "1";

    clearTimeout(toast._timer);

    toast._timer = setTimeout(() => {
      toast.style.opacity = "0";
    }, 1800);
  }
})();
