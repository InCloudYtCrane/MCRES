// mcres/static/js/pages/errors/error_forbidden_comment.js
let seconds = 10;
  const el = document.getElementById("countdownNum");
  const timer = setInterval(() => {
    seconds -= 1;
    if (seconds <= 0) {
      clearInterval(timer);
      window.location.href = window.ERROR_PAGE.redirectUrl;
    } else {
      el.textContent = seconds;
    }
  }, 1000);
