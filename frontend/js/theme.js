/* Loaded in <head> so the right theme is set before the page paints (no flash). */
(function () {
  var t = localStorage.getItem("theme");
  if (!t || t === "auto") t = matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  document.documentElement.dataset.theme = t;
})();
