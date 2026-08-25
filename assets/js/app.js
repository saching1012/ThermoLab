// ---------------------------------------------------------------------
// Curious Kelvin — shared client-side script (loaded once via
// components.html on every rerun). Three independent jobs:
//   1. Hide the "Hosted with Streamlit" cloud badge.
//   2. Make sure the PWA manifest link is present in <head>.
//   3. Make the hamburger / sidebar open+close INSTANT by toggling the
//      drawer's CSS directly, instead of waiting for a full Streamlit
//      rerun round-trip. Python still keeps its own state in sync (see
//      render_nav_sidebar in app.py) so the two never disagree.
// ---------------------------------------------------------------------
try {
    var css = 'a[href*="streamlit.io"], a[href*="github.com"] ' +
              '{ display: none !important; visibility: hidden !important; }';
    var styleTag = window.top.document.createElement('style');
    styleTag.appendChild(window.top.document.createTextNode(css));
    window.top.document.head.appendChild(styleTag);

    function hideCloudBadge() {
        var sel = 'a[href*="streamlit.io"], a[href*="github.com"]';
        window.top.document.querySelectorAll(sel).forEach(function (el) {
            el.style.setProperty('display', 'none', 'important');
        });
    }
    hideCloudBadge();
    var badgeObserver = new MutationObserver(hideCloudBadge);
    badgeObserver.observe(window.top.document.body, { childList: true, subtree: true });
} catch (e) {}

try {
    (function () {
        var link = window.top.document.querySelector('link[rel="manifest"]');
        if (!link) {
            link = window.top.document.createElement('link');
            link.rel = 'manifest';
            window.top.document.head.appendChild(link);
        }
        link.href = 'https://saching1012.github.io/ThermoLab/static/manifest.json';
    })();
} catch (e) {}

try {
    (function () {
        var doc = window.top.document;

        function openSidebarNow() {
            var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            var backdrop = doc.querySelector('.st-key-sidebar_backdrop');
            var burger = doc.querySelector('.st-key-burger_toggle');
            if (!sidebar) return;
            sidebar.style.setProperty('display', 'block', 'important');
            sidebar.style.setProperty('transform', 'translateX(0)', 'important');
            sidebar.style.setProperty('visibility', 'visible', 'important');
            sidebar.style.setProperty('pointer-events', 'auto', 'important');
            var content = doc.querySelector('[data-testid="stSidebarUserContent"]');
            if (content) content.style.setProperty('visibility', 'visible', 'important');
            if (backdrop) backdrop.style.setProperty('display', 'block', 'important');
            if (burger) burger.style.setProperty('visibility', 'hidden', 'important');
        }

        function closeSidebarNow() {
            var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
            var backdrop = doc.querySelector('.st-key-sidebar_backdrop');
            var burger = doc.querySelector('.st-key-burger_toggle');
            if (!sidebar) return;
            sidebar.style.setProperty('transform', 'translateX(100%)', 'important');
            sidebar.style.setProperty('pointer-events', 'none', 'important');
            if (backdrop) backdrop.style.setProperty('display', 'none', 'important');
            if (burger) burger.style.setProperty('visibility', 'visible', 'important');
        }

        function wireUp() {
            var burgerBtn = doc.querySelector('.st-key-burger_toggle button');
            var closeBtn = doc.querySelector('.st-key-sidebar_close_x button');
            var backdropBtn = doc.querySelector('.st-key-sidebar_backdrop button');
            if (burgerBtn && !burgerBtn.dataset.ckWired) {
                burgerBtn.dataset.ckWired = '1';
                burgerBtn.addEventListener('click', openSidebarNow, true);
            }
            if (closeBtn && !closeBtn.dataset.ckWired) {
                closeBtn.dataset.ckWired = '1';
                closeBtn.addEventListener('click', closeSidebarNow, true);
            }
            if (backdropBtn && !backdropBtn.dataset.ckWired) {
                backdropBtn.dataset.ckWired = '1';
                backdropBtn.addEventListener('click', closeSidebarNow, true);
            }
        }

        // Streamlit re-renders these buttons on every rerun, so keep
        // re-checking for a while rather than wiring up only once.
        var tries = 0;
        var iv = setInterval(function () {
            tries++;
            try { wireUp(); } catch (e) {}
            if (tries > 60) clearInterval(iv);
        }, 200);
    })();
} catch (e) {}
