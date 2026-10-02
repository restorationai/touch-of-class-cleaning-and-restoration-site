/* Rank AI embeddable estimate form loader.
 * Usage on any landing page:
 *   <script src="https://DOMAIN/embed/estimate.js" data-source="google_ads" async></script>
 * Injects an auto-resizing iframe right after the script tag: no fixed
 * height, no surrounding white space. data-source tags every lead.
 */
(function () {
  var s = document.currentScript;
  if (!s) return;
  var origin;
  try { origin = new URL(s.src).origin; } catch (e) { return; }
  var source = (s.getAttribute("data-source") || "google_ads").toLowerCase();
  var frame = document.createElement("iframe");
  frame.src = origin + "/embed/estimate/?source=" + encodeURIComponent(source) + "&js=1";
  frame.style.cssText = "width:100%;border:0;display:block;height:620px;overflow:hidden";
  frame.setAttribute("loading", "lazy");
  frame.setAttribute("title", "Free estimate");
  frame.setAttribute("scrolling", "no");
  s.parentNode.insertBefore(frame, s.nextSibling);
  window.addEventListener("message", function (e) {
    if (e.origin !== origin || e.source !== frame.contentWindow) return;
    var d = e.data || {};
    if (d && d.type === "rankai-embed-height" && d.height > 0) {
      frame.style.height = Math.ceil(d.height) + "px";
    }
  });
})();
