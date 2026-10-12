// mcres/static/js/pages/resource/list/children/shaderpack_presets.js
(function () {
    "use strict";

    const cards = document.querySelectorAll(".preset-card");

    if (!cards.length) return;

    cards.forEach((card) => {
      const area = card.querySelector(".screenshot-area");
      if (!area) return;

      const imgs = area.querySelectorAll("img");
      const dots = area.querySelectorAll(".dot");

      if (imgs.length <= 1) return;

      let current = 0;
      let timer = null;

      imgs.forEach((img, index) => {
        img.style.position = "absolute";
        img.style.top = "0";
        img.style.left = "0";
        img.style.width = "100%";
        img.style.height = "100%";
        img.style.objectFit = "cover";
        img.style.transition = "opacity .5s ease";
        img.style.opacity = index === 0 ? "1" : "0";
      });

      function showIndex(index) {
        if (index < 0 || index >= imgs.length) return;

        imgs.forEach((img, i) => {
          img.style.opacity = i === index ? "1" : "0";
        });

        dots.forEach((dot, i) => {
          dot.classList.toggle("active", i === index);
        });

        current = index;
      }

      function stopSlide() {
        if (timer) {
          clearInterval(timer);
          timer = null;
        }
      }

      function startSlide() {
        stopSlide();

        timer = setInterval(() => {
          showIndex((current + 1) % imgs.length);
        }, 1500);
      }

      area.addEventListener("mouseenter", startSlide);

      area.addEventListener("mouseleave", () => {
        stopSlide();
        showIndex(0);
      });

      dots.forEach((dot, index) => {
        dot.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();

          showIndex(index);

          if (timer) {
            startSlide();
          }
        });
      });

      showIndex(0);
    });

    console.log("✅ 预设截图轮播加载成功");
  })();
