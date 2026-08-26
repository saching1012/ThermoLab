(function () {
    "use strict";

    const doc = window.top.document;

    function injectStyle() {
        if (doc.getElementById("thermolab-client-style")) return;

        const style = doc.createElement("style");
        style.id = "thermolab-client-style";

        style.textContent = `
            a[href*="streamlit.io"],
            a[href*="github.com"] {
                display: none !important;
                visibility: hidden !important;
            }

            header[data-testid="stHeader"] {
                display: none !important;
                height: 0 !important;
            }

            .st-key-topnav {
                margin-top: 0 !important;
            }

            section[data-testid="stSidebar"] {
                will-change: transform;
                backface-visibility: hidden;
                -webkit-backface-visibility: hidden;
            }

            body.thermolab-drawer-open {
                overflow: hidden !important;
            }
        `;

        doc.head.appendChild(style);
    }

    function hideBadges() {
        doc.querySelectorAll(
            'a[href*="streamlit.io"], a[href*="github.com"]'
        ).forEach(function (element) {
            element.style.setProperty(
                "display",
                "none",
                "important"
            );

            element.style.setProperty(
                "visibility",
                "hidden",
                "important"
            );
        });
    }

    function ensureManifest() {
        const manifestUrl =
            "https://saching1012.github.io/ThermoLab/static/manifest.json";

        let manifest =
            doc.querySelector('link[rel="manifest"]');

        if (!manifest) {
            manifest = doc.createElement("link");
            manifest.rel = "manifest";
            doc.head.appendChild(manifest);
        }

        if (manifest.href !== manifestUrl) {
            manifest.href = manifestUrl;
        }
    }

    function fixViewport() {

        const desired =
            "width=device-width, initial-scale=1, maximum-scale=5, user-scalable=yes";

        let viewport =
            doc.querySelector('meta[name="viewport"]');

        if (!viewport) {
            viewport = doc.createElement("meta");
            viewport.name = "viewport";
            doc.head.appendChild(viewport);
        }

        if (viewport.getAttribute("content") !== desired) {
            viewport.setAttribute("content", desired);
        }
    }

    function fixTopNavigation() {
        const nav =
            doc.querySelector(".st-key-topnav");

        if (!nav) return;

        let element = nav;
        let depth = 0;

        while (element && depth < 8) {
            element.style.setProperty(
                "margin-top",
                "0px",
                "important"
            );

            element.style.setProperty(
                "padding-top",
                "0px",
                "important"
            );

            element = element.parentElement;
            depth++;
        }

        nav.style.setProperty(
            "padding-top",
            "8px",
            "important"
        );

        nav.style.setProperty(
            "margin-top",
            "0px",
            "important"
        );

        const header =
            doc.querySelector(
                'header[data-testid="stHeader"]'
            );

        if (header) {
            header.style.setProperty(
                "display",
                "none",
                "important"
            );

            header.style.setProperty(
                "height",
                "0px",
                "important"
            );
        }
    }

    function getSidebar() {
        return doc.querySelector(
            'section[data-testid="stSidebar"]'
        );
    }

    function getBackdrop() {
        return doc.querySelector(
            ".st-key-sidebar_backdrop"
        );
    }

    function getBurger() {
        return doc.querySelector(
            ".st-key-burger_toggle"
        );
    }

    function openSidebar() {
        const sidebar = getSidebar();
        const backdrop = getBackdrop();
        const burger = getBurger();

        if (!sidebar) return;

        sidebar.style.setProperty(
            "display",
            "block",
            "important"
        );

        sidebar.style.setProperty(
            "visibility",
            "visible",
            "important"
        );

        sidebar.style.setProperty(
            "transform",
            "translate3d(0,0,0)",
            "important"
        );

        sidebar.style.setProperty(
            "pointer-events",
            "auto",
            "important"
        );

        sidebar.setAttribute(
            "aria-hidden",
            "false"
        );

        if (backdrop) {
            backdrop.style.setProperty(
                "display",
                "block",
                "important"
            );

            backdrop.style.setProperty(
                "visibility",
                "visible",
                "important"
            );

            backdrop.style.setProperty(
                "pointer-events",
                "auto",
                "important"
            );
        }

        if (burger) {
            burger.style.setProperty(
                "visibility",
                "hidden",
                "important"
            );
        }

        doc.body.classList.add(
            "thermolab-drawer-open"
        );
    }

    function closeSidebar() {
        const sidebar = getSidebar();
        const backdrop = getBackdrop();
        const burger = getBurger();

        if (!sidebar) return;

        sidebar.style.setProperty(
            "transform",
            "translate3d(100%,0,0)",
            "important"
        );

        sidebar.style.setProperty(
            "pointer-events",
            "none",
            "important"
        );

        sidebar.setAttribute(
            "aria-hidden",
            "true"
        );

        if (backdrop) {
            backdrop.style.setProperty(
                "display",
                "none",
                "important"
            );

            backdrop.style.setProperty(
                "visibility",
                "hidden",
                "important"
            );

            backdrop.style.setProperty(
                "pointer-events",
                "none",
                "important"
            );
        }

        if (burger) {
            burger.style.setProperty(
                "visibility",
                "visible",
                "important"
            );
        }

        doc.body.classList.remove(
            "thermolab-drawer-open"
        );
    }

    function wireButton(button, handler) {
        if (!button) return;

        if (button.dataset.thermolabWired === "1") {
            return;
        }

        button.dataset.thermolabWired = "1";

        button.addEventListener(
            "click",
            function () {
                handler();
            },
            false
        );
    }

    function wireNavigation() {
        const burger =
            doc.querySelector(
                ".st-key-burger_toggle button"
            );

        const close =
            doc.querySelector(
                ".st-key-sidebar_close_x button"
            );

        const backdrop =
            doc.querySelector(
                ".st-key-sidebar_backdrop button"
            );

        wireButton(burger, openSidebar);
        wireButton(close, closeSidebar);
        wireButton(backdrop, closeSidebar);
    }

    function initialize() {
        injectStyle();
        ensureManifest();
        fixViewport();
        hideBadges();
        fixTopNavigation();
        wireNavigation();
    }

    initialize();

    if (!window.thermoLabObserver) {
        window.thermoLabObserver =
            new MutationObserver(function () {
                requestAnimationFrame(function () {
                    hideBadges();
                    fixTopNavigation();
                    wireNavigation();

                    fixViewport();
                });
            });

        window.thermoLabObserver.observe(
            doc.body,
            {
                childList: true,
                subtree: true
            }
        );
    }

    if (!window.thermoLabKeyboard) {
        window.thermoLabKeyboard = true;

        doc.addEventListener(
            "keydown",
            function (event) {
                if (event.key === "Escape") {
                    closeSidebar();
                }
            },
            false
        );
    }

    if (!window.thermoLabResize) {
        window.thermoLabResize = true;

        window.addEventListener(
            "resize",
            function () {
                requestAnimationFrame(
                    fixTopNavigation
                );
            },
            { passive: true }
        );
    }

})();
