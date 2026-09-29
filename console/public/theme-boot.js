// Applies the saved appearance, accent and transparency before first paint so
// the page never flashes the wrong look. External file because the CSP forbids
// inline scripts.
(function () {
  try {
    var root = document.documentElement;
    var pref = localStorage.getItem("falcon.appearance");
    if (pref === "light" || pref === "dark") root.dataset.theme = pref;
    var accent = localStorage.getItem("falcon.accent");
    if (accent && /^(purple|pink|red|orange|green|graphite)$/.test(accent)) root.dataset.accent = accent;
    if (localStorage.getItem("falcon.transparency") === "reduced") root.dataset.transparency = "reduced";
  } catch (e) {
    /* storage unavailable: defaults */
  }
})();
