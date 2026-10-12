(function () {
  "use strict";
  const slides = document.querySelectorAll(".carousel-slide");
  const dots = document.querySelectorAll(".carousel-dots .dot");
  const prevBtn = document.getElementById("carouselPrev");
  const nextBtn = document.getElementById("carouselNext");
  const dotsContainer = document.getElementById("carouselDots");
  const container = document.getElementById("carouselContainer");
  if (
    slides.length === 0 ||
    (slides.length === 1 && slides[0].querySelector(".placeholder"))
  ) {
    if (prevBtn) prevBtn.classList.add("hidden");
    if (nextBtn) nextBtn.classList.add("hidden");
    if (dotsContainer) dotsContainer.classList.add("hidden");
  } else {
    let current = 0;
    let autoTimer = null;
    const AUTO_INTERVAL = 5000;
    let isHovering = false;
    function goTo(index) {
      if (index < 0) index = slides.length - 1;
      if (index >= slides.length) index = 0;
      slides.forEach((el, i) => el.classList.toggle("active", i === index));
      dots.forEach((dot, i) => dot.classList.toggle("active", i === index));
      current = index;
      if (slides.length > 1) resetAutoPlay();
    }
    function startAutoPlay() {
      if (autoTimer) clearInterval(autoTimer);
      if (slides.length <= 1) return;
      autoTimer = setInterval(() => {
        if (!isHovering) goTo(current + 1);
      }, AUTO_INTERVAL);
    }
    function stopAutoPlay() {
      if (autoTimer) {
        clearInterval(autoTimer);
        autoTimer = null;
      }
    }
    function resetAutoPlay() {
      stopAutoPlay();
      startAutoPlay();
    }
    if (container) {
      container.addEventListener("mouseenter", function () {
        isHovering = true;
        stopAutoPlay();
      });
      container.addEventListener("mouseleave", function () {
        isHovering = false;
        startAutoPlay();
      });
    }
    prevBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      goTo(current - 1);
    });
    nextBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      goTo(current + 1);
    });
    dots.forEach((dot, idx) => {
      dot.addEventListener("click", function (e) {
        e.stopPropagation();
        goTo(idx);
      });
    });
    container.addEventListener("click", function (e) {
      if (e.target.closest(".carousel-arrow") || e.target.closest(".dot"))
        return;
      const activeSlide = this.querySelector(".carousel-slide.active");
      if (activeSlide) {
        const url = activeSlide.dataset.url;
        if (url && url !== "#") window.open(url, "_blank");
      }
    });
    goTo(0);
  }
  window.performSearch = function () {
    const input = document.getElementById("searchInput");
    const query = input.value.trim();
    if (!query) return;
    window.open("/search?q=" + encodeURIComponent(query), "_blank");
  };
  document
    .getElementById("searchInput")
    .addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        performSearch();
      }
    });
  function updateLocalTime() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, "0");
    const minutes = String(now.getMinutes()).padStart(2, "0");
    const seconds = String(now.getSeconds()).padStart(2, "0");
    const timeStr = hours + ":" + minutes + ":" + seconds;
    const el = document.getElementById("localTime");
    if (el) el.textContent = timeStr;
  }
  updateLocalTime();
  setInterval(updateLocalTime, 1000);
  const userBtn = document.getElementById("userMenuBtn");
  const dropdown = document.getElementById("dropdownMenuRoot");
  const overlay = document.getElementById("dropdownOverlay");
  if (userBtn && dropdown && overlay) {
    userBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      const isOpen = dropdown.classList.contains("active");
      if (isOpen) {
        closeDropdown();
      } else {
        openDropdown();
      }
    });
    overlay.addEventListener("click", closeDropdown);
    document.addEventListener("click", function (e) {
      if (
        dropdown.classList.contains("active") &&
        !dropdown.contains(e.target) &&
        e.target !== userBtn &&
        !userBtn.contains(e.target)
      ) {
        closeDropdown();
      }
    });
    window.addEventListener("scroll", positionDropdown);
    window.addEventListener("resize", positionDropdown);
    function openDropdown() {
      positionDropdown();
      dropdown.classList.add("active");
      overlay.classList.add("active");
    }
    function closeDropdown() {
      dropdown.classList.remove("active");
      overlay.classList.remove("active");
    }
    function positionDropdown() {
      if (!userBtn) return;
      const rect = userBtn.getBoundingClientRect();
      const left = rect.right - 200;
      const top = rect.bottom + 8;
      dropdown.style.left = Math.max(10, left) + "px";
      dropdown.style.top = top + "px";
    }
  }
  window.stopImpersonate = function () {
    if (!confirm("确认退出模拟，恢复为管理员身份？")) return;
    fetch("/admin/4_us/stop_impersonate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          window.location.reload();
        } else {
          Toast.error(data.message);
        }
      })
      .catch((err) => Toast.error("请求失败: " + err.message));
  };
  const rightNav = document.getElementById("sideNavRight");
  const sectionBlocks = document.querySelectorAll(".section-block");
  const leftNavLinks = document.querySelectorAll(".side-nav-left a");
  function getCategoryTitlesForSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) return [];
    return section.querySelectorAll(".category-title");
  }
  function buildRightNav(sectionId) {
    if (!rightNav) return;
    rightNav.innerHTML = "";
    if (!sectionId) {
      for (const block of sectionBlocks) {
        const rect = block.getBoundingClientRect();
        if (rect.bottom > 0) {
          sectionId = block.id;
          break;
        }
      }
      if (!sectionId) {
        const firstBlock = document.querySelector(".section-block");
        if (firstBlock) sectionId = firstBlock.id;
      }
    }
    if (!sectionId) return;
    const titles = getCategoryTitlesForSection(sectionId);
    if (titles.length === 0) {
      const placeholder = document.createElement("div");
      placeholder.style.cssText =
        "color: #4d5663; font-size: 13px; padding: 8px 12px; text-align: center; font-style: italic;";
      placeholder.textContent = "暂无子分类";
      rightNav.appendChild(placeholder);
      return;
    }
    titles.forEach(function (el) {
      const id = el.id;
      if (!id) return;
      const text = el.textContent
        .trim()
        .replace(/\(\d+\)/, "")
        .trim();
      const a = document.createElement("a");
      a.href = "#" + id;
      a.dataset.target = id;
      a.textContent = text;
      rightNav.appendChild(a);
    });
    highlightRightNavItems();
  }
  function highlightRightNavItems() {
    const rightLinks = rightNav.querySelectorAll("a");
    if (rightLinks.length === 0) return;
    let activeId = null;
    const allTitles = document.querySelectorAll(".category-title");
    for (let i = allTitles.length - 1; i >= 0; i--) {
      const rect = allTitles[i].getBoundingClientRect();
      if (rect.top <= 200) {
        activeId = allTitles[i].id;
        break;
      }
    }
    rightLinks.forEach(function (link) {
      const target = link.dataset.target;
      link.classList.toggle("active", target === activeId);
    });
  }
  function updateRightNav() {
    let activeSectionId = null;
    for (let i = sectionBlocks.length - 1; i >= 0; i--) {
      const rect = sectionBlocks[i].getBoundingClientRect();
      if (rect.top <= 200) {
        activeSectionId = sectionBlocks[i].id;
        break;
      }
    }
    if (!activeSectionId && sectionBlocks.length > 0) {
      activeSectionId = sectionBlocks[0].id;
    }
    if (
      activeSectionId &&
      rightNav.dataset.currentSection !== activeSectionId
    ) {
      rightNav.dataset.currentSection = activeSectionId;
      buildRightNav(activeSectionId);
      if (typeof updateHamburgerRightNav === "function") {
        updateHamburgerRightNav(activeSectionId);
      }
    } else {
      highlightRightNavItems();
      if (typeof highlightHamburgerRightNav === "function") {
        highlightHamburgerRightNav();
      }
    }
    updateLeftNavHighlight(activeSectionId);
  }
  function updateLeftNavHighlight(activeSectionId) {
    leftNavLinks.forEach(function (link) {
      const target = link.dataset.target;
      link.classList.toggle("active", target === activeSectionId);
    });
  }
  let scrollTimeout = null;
  function handleScrollOrResize() {
    if (scrollTimeout) {
      cancelAnimationFrame(scrollTimeout);
    }
    scrollTimeout = requestAnimationFrame(function () {
      updateRightNav();
      scrollTimeout = null;
    });
  }
  window.addEventListener("scroll", handleScrollOrResize, { passive: true });
  window.addEventListener("resize", handleScrollOrResize, { passive: true });
  leftNavLinks.forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      const targetId = this.dataset.target;
      const targetEl = document.getElementById(targetId);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: "smooth" });
      }
    });
  });
  rightNav.addEventListener("click", function (e) {
    const link = e.target.closest("a");
    if (!link) return;
    e.preventDefault();
    const targetId = link.dataset.target;
    const targetEl = document.getElementById(targetId);
    if (targetEl) {
      targetEl.scrollIntoView({ behavior: "smooth" });
    }
  });
  const backBtn = document.getElementById("backToTop");
  window.addEventListener("scroll", function () {
    const scrollY = window.scrollY || document.documentElement.scrollTop;
    if (scrollY > 300) {
      backBtn.classList.add("visible");
    } else {
      backBtn.classList.remove("visible");
    }
  });
  backBtn.addEventListener("click", function () {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  });
  const feedContainer = document.querySelector(".feed-scroll-container");
  if (feedContainer) {
    const list = feedContainer.querySelector(".feed-scroll-list");
    if (list && list.children.length > 1) {
      const items = Array.from(list.children);
      items.forEach((item) => {
        const clone = item.cloneNode(true);
        list.appendChild(clone);
      });
      const speed = 0.1;
      let offset = 0;
      let isPaused = false;
      let animationId = null;
      const totalHeight = list.scrollHeight / 2;
      function step() {
        if (!isPaused) {
          offset += speed;
          if (offset >= totalHeight) {
            offset = 0;
            list.style.transition = "none";
            list.style.transform = "translateY(0px)";
            void list.offsetHeight;
          } else {
            list.style.transform = "translateY(-" + offset + "px)";
          }
        }
        animationId = requestAnimationFrame(step);
      }
      feedContainer.addEventListener("mouseenter", () => {
        isPaused = true;
      });
      feedContainer.addEventListener("mouseleave", () => {
        isPaused = false;
      });
      step();
    }
  }
  const hamburgerBtn = document.getElementById("hamburgerBtn");
  const hamburgerPanel = document.getElementById("hamburgerPanel");
  const hamburgerOverlay = document.getElementById("hamburgerOverlay");
  const hamburgerClose = document.getElementById("hamburgerClose");
  const leftNavList = document.getElementById("hamburgerLeftNav");
  const rightNavList = document.getElementById("hamburgerRightNav");
  function buildHamburgerLeftNav() {
    if (!leftNavList) return;
    leftNavList.innerHTML = "";
    const leftLinks = document.querySelectorAll(".side-nav-left a");
    if (leftLinks.length === 0) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.textContent = "暂无分类";
      a.style.color = "#4d5663";
      a.style.fontStyle = "italic";
      li.appendChild(a);
      leftNavList.appendChild(li);
      return;
    }
    leftLinks.forEach(function (link) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = link.href;
      a.dataset.target = link.dataset.target;
      const iconClone = link.querySelector(".icon");
      if (iconClone) {
        a.appendChild(iconClone.cloneNode(true));
      }
      let text = link.textContent.trim();
      text = text.replace(/[📦✨🗺️]\s*/, "").trim();
      a.appendChild(document.createTextNode(" " + text));
      const target = link.dataset.target;
      const iconEl = a.querySelector("i");
      if (iconEl) {
        if (target === "section-resourcepack") {
          iconEl.classList.add("nav-icon-color-rp");
        } else if (target === "section-shaderpack") {
          iconEl.classList.add("nav-icon-color-sp");
        } else if (target === "section-map") {
          iconEl.classList.add("nav-icon-color-map");
        }
      }
      a.addEventListener("click", function (e) {
        e.preventDefault();
        const targetId = this.dataset.target;
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: "smooth" });
          closeHamburger();
        }
      });
      li.appendChild(a);
      leftNavList.appendChild(li);
    });
  }
  function updateHamburgerRightNav(sectionId) {
    if (!rightNavList) return;
    rightNavList.innerHTML = "";
    if (!sectionId) {
      for (const block of sectionBlocks) {
        const rect = block.getBoundingClientRect();
        if (rect.top <= 200) {
          sectionId = block.id;
          break;
        }
      }
      if (!sectionId && sectionBlocks.length > 0) {
        sectionId = sectionBlocks[0].id;
      }
      if (!sectionId) return;
    }
    const titles = getCategoryTitlesForSection(sectionId);
    if (titles.length === 0) {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.textContent = "暂无子分类";
      a.style.color = "#4d5663";
      a.style.fontStyle = "italic";
      a.style.cursor = "default";
      li.appendChild(a);
      rightNavList.appendChild(li);
      return;
    }
    titles.forEach(function (el) {
      const id = el.id;
      if (!id) return;
      const text = el.textContent
        .trim()
        .replace(/\(\d+\)/, "")
        .trim();
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "#" + id;
      a.dataset.target = id;
      a.textContent = text;
      a.addEventListener("click", function (e) {
        e.preventDefault();
        const targetId = this.dataset.target;
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: "smooth" });
          closeHamburger();
        }
      });
      li.appendChild(a);
      rightNavList.appendChild(li);
    });
    highlightHamburgerRightNav();
  }
  function highlightHamburgerRightNav() {
    const links = rightNavList.querySelectorAll("a");
    if (links.length === 0) return;
    let activeId = null;
    const allTitles = document.querySelectorAll(".category-title");
    for (let i = allTitles.length - 1; i >= 0; i--) {
      const rect = allTitles[i].getBoundingClientRect();
      if (rect.top <= 200) {
        activeId = allTitles[i].id;
        break;
      }
    }
    links.forEach(function (link) {
      const target = link.dataset.target;
      link.classList.toggle("active", target === activeId);
    });
  }
  window.updateHamburgerRightNav = updateHamburgerRightNav;
  window.highlightHamburgerRightNav = highlightHamburgerRightNav;
  function openHamburger() {
    if (!hamburgerPanel || !hamburgerOverlay) return;
    const activeSectionId =
      rightNav.dataset.currentSection || sectionBlocks[0]?.id;
    if (activeSectionId) {
      updateHamburgerRightNav(activeSectionId);
    }
    hamburgerPanel.classList.add("active");
    hamburgerOverlay.classList.add("active");
    document.body.style.overflow = "hidden";
  }
  function closeHamburger() {
    if (!hamburgerPanel || !hamburgerOverlay) return;
    hamburgerPanel.classList.remove("active");
    hamburgerOverlay.classList.remove("active");
    document.body.style.overflow = "";
  }
  if (hamburgerBtn && hamburgerPanel && hamburgerOverlay) {
    hamburgerBtn.addEventListener("click", openHamburger);
    hamburgerOverlay.addEventListener("click", closeHamburger);
    if (hamburgerClose) {
      hamburgerClose.addEventListener("click", closeHamburger);
    }
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && hamburgerPanel.classList.contains("active")) {
        closeHamburger();
      }
    });
    window.addEventListener("resize", function () {
      if (
        window.innerWidth >= 1400 &&
        hamburgerPanel.classList.contains("active")
      ) {
        closeHamburger();
      }
    });
    buildHamburgerLeftNav();
  }
  const firstBlock = document.querySelector(".section-block");
  if (firstBlock) {
    const firstId = firstBlock.id;
    rightNav.dataset.currentSection = firstId;
    buildRightNav(firstId);
    if (rightNavList) {
      updateHamburgerRightNav(firstId);
    }
    updateLeftNavHighlight(firstId);
  }
  requestAnimationFrame(function () {
    updateRightNav();
  });
})();

// ---------- 搜索按钮（替代内联 onclick） ----------
(function () {
  var btn = document.getElementById("searchSubmitBtn");
  if (btn) btn.addEventListener("click", performSearch);
})();
