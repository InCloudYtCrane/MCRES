// mcres/static/js/components/navbar.js
(function () {
      "use strict";

      // 滚动加深背景
      var navbar = document.getElementById("mnNavbar");
      if (navbar) {
        var onScroll = function () {
          navbar.classList.toggle("mn-scrolled", window.scrollY > 20);
        };
        document.addEventListener("scroll", onScroll, { passive: true });
        onScroll();
      }

      // 抽屉
      var drawer = document.getElementById("mnDrawer");
      var overlay = document.getElementById("mnDrawerOverlay");
      var burger = document.getElementById("mnHamburger");
      var closeBtn = document.getElementById("mnDrawerClose");

      function openDrawer() {
        if (!drawer) return;
        drawer.classList.add("mn-open");
        if (overlay) overlay.classList.add("mn-open");
        document.body.style.overflow = "hidden";
      }
      function closeDrawer() {
        if (!drawer) return;
        drawer.classList.remove("mn-open");
        if (overlay) overlay.classList.remove("mn-open");
        document.body.style.overflow = "";
      }

      if (burger) burger.addEventListener("click", openDrawer);
      if (overlay) overlay.addEventListener("click", closeDrawer);
      if (closeBtn) closeBtn.addEventListener("click", closeDrawer);

      document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") closeDrawer();
      });
      window.addEventListener("resize", function () {
        if (window.innerWidth > 900) closeDrawer();
      });
      if (drawer) {
        drawer.querySelectorAll("a").forEach(function (a) {
          a.addEventListener("click", function () {
            if (this.target !== "_blank") setTimeout(closeDrawer, 150);
          });
        });
      }

      // 移动端点用户按钮 toggle 菜单
      var userWrap = document.getElementById("mnUser");
      if (userWrap) {
        var btn = userWrap.querySelector(".mn-user-btn");
        if (btn) {
          btn.addEventListener("click", function (e) {
            if (window.matchMedia("(hover: none)").matches) {
              e.preventDefault();
              userWrap.classList.toggle("mn-open");
            }
          });
        }
        document.addEventListener("click", function (e) {
          if (!userWrap.contains(e.target))
            userWrap.classList.remove("mn-open");
        });
      }
    })();
