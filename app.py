import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import functools
import io
import os
import time
import base64

from CoolProp.CoolProp import PhaseSI, PropsSI

APP_NAME = "Curious Kelvin"
APP_QUOTE = "Every state, every cycle — let's reach equilibrium."
LOGO_PATH = "static/launchericon-512x512.png"
LOGO_ICON_PATH = "static/launchericon-192x192.png"
FLUID_IMG_PATH = "static/fluid.jpg"
CYCLE_IMG_PATH = "static/cycle.jpg"
ASSET_CSS_DIR = "assets/css"
ASSET_JS_DIR = "assets/js"


@functools.lru_cache(maxsize=16)
def _img_data_uri(path):
    """Read a local image file and return it as a base64 data URI. Returns
    an empty string (never raises) if the file can't be found, so a missing
    asset just means no image renders instead of a crash."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        ext = path.rsplit(".", 1)[-1].lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "svg": "image/svg+xml", "webp": "image/webp"}.get(ext, "application/octet-stream")
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return ""


@functools.lru_cache(maxsize=8)
def _read_text_asset(path):
    """Read an external CSS/JS asset file as plain text. Returns an empty
    string if missing so the app still runs (just without that styling)
    rather than crashing when assets/ hasn't been deployed yet."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


_page_icon = LOGO_ICON_PATH if os.path.exists(LOGO_ICON_PATH) else "🧪"
st.set_page_config(
    page_title=APP_NAME,
    page_icon=_page_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)
import streamlit.components.v1 as components
_app_js = _read_text_asset(f"{ASSET_JS_DIR}/app.js")
if _app_js:
    components.html(f"<script>{_app_js}</script>", height=0, width=0)

# ---------------------------------------------------------------------
# Guaranteed-inline JS (ships inside app.py, not a separate file that can
# go missing on upload). Two independent jobs:
#
# 1. A real, always-there scroll indicator. Plain CSS scrollbar styling
#    (::-webkit-scrollbar) is a desktop-browser feature — stock Android
#    Chrome/WebView ignores it entirely for normal page scrolling, no
#    matter how it's written, which is why no amount of CSS ever made one
#    appear. This instead draws a small pill on the right edge with a
#    plain positioned <div>, sized/positioned from real scroll metrics on
#    every scroll event — that works on any browser, since it isn't
#    asking the browser to themes something it won't.
#
# 2. A floating fullscreen (⛶) button on every Plotly chart. Plotly.js
#    has no built-in fullscreen modebar button, and a custom modebar
#    button with a real JS click handler can't be sent through
#    st.plotly_chart's plain JSON config — so this adds one directly to
#    each chart's container via the Fullscreen API instead.
# ---------------------------------------------------------------------
components.html(
    """
    <script>
    (function () {
        var doc = window.top.document;

        // ---- 0. Pinch-to-zoom on charts. Streamlit ships its own
        // <meta name="viewport"> tag with user-scalable=no by default —
        // that's a BROWSER-level restriction, above any page CSS, so no
        // touch-action rule on the chart elements could ever undo it: the
        // browser refuses the pinch gesture before it reaches Plotly's own
        // JS handler at all. This rewrites that tag directly. Placed in
        // THIS guaranteed-inline script (not the separate assets/js/app.js
        // file) because that external file depends on a correct upload/
        // deploy path that has proven unreliable to verify from here —
        // this block ships inside app.py itself and cannot go missing. ----
        function fixViewport() {
            var desired = 'width=device-width, initial-scale=1, maximum-scale=5, user-scalable=yes';
            var vp = doc.querySelector('meta[name="viewport"]');
            if (!vp) {
                vp = doc.createElement('meta');
                vp.name = 'viewport';
                doc.head.appendChild(vp);
            }
            if (vp.getAttribute('content') !== desired) {
                vp.setAttribute('content', desired);
            }
        }
        fixViewport();
        setInterval(fixViewport, 1000);

        // ---- 1. Custom scroll indicator ----
        function ensureThumb() {
            var thumb = doc.getElementById('ck-scroll-thumb');
            if (!thumb) {
                thumb = doc.createElement('div');
                thumb.id = 'ck-scroll-thumb';
                thumb.style.cssText =
                    'position:fixed;right:3px;top:0;width:5px;border-radius:999px;' +
                    'background:rgba(0,194,255,0.65);z-index:2147483647;' +
                    'pointer-events:none;opacity:0;transition:opacity .25s ease;';
                doc.body.appendChild(thumb);
            }
            return thumb;
        }
        var hideTimer = null;
        function updateThumb() {
            var el = doc.scrollingElement || doc.documentElement;
            var thumb = ensureThumb();
            var scrollable = el.scrollHeight - el.clientHeight;
            if (scrollable <= 4) { thumb.style.opacity = '0'; return; }
            var trackH = el.clientHeight - 16;
            var ratio = el.clientHeight / el.scrollHeight;
            var thumbH = Math.max(trackH * ratio, 32);
            var thumbTop = 8 + (el.scrollTop / scrollable) * (trackH - thumbH);
            thumb.style.height = thumbH + 'px';
            thumb.style.top = thumbTop + 'px';
            thumb.style.opacity = '1';
            if (hideTimer) clearTimeout(hideTimer);
            hideTimer = setTimeout(function () { thumb.style.opacity = '0'; }, 900);
        }
        doc.addEventListener('scroll', updateThumb, true);
        window.top.addEventListener('resize', updateThumb);
        updateThumb();
        setInterval(updateThumb, 1500);

        // ---- 2. Per-chart fullscreen button ----
        function addFullscreenButtons() {
            var charts = doc.querySelectorAll('[data-testid="stPlotlyChart"]');
            charts.forEach(function (chart) {
                if (chart.dataset.ckFsWired) return;
                chart.dataset.ckFsWired = '1';
                var cs = doc.defaultView.getComputedStyle(chart);
                if (cs.position === 'static') chart.style.position = 'relative';
                var btn = doc.createElement('button');
                btn.innerHTML = '⛶';
                btn.title = 'Toggle fullscreen';
                btn.style.cssText =
                    'position:absolute;top:6px;right:6px;z-index:50;' +
                    'width:30px;height:30px;border-radius:8px;border:none;' +
                    'background:rgba(0,0,0,0.55);color:#fff;font-size:16px;' +
                    'cursor:pointer;line-height:1;';
                btn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    if (doc.fullscreenElement === chart) {
                        doc.exitFullscreen();
                    } else if (chart.requestFullscreen) {
                        chart.requestFullscreen().catch(function () {
                            chart.classList.toggle('ck-chart-fullscreen');
                        });
                    } else {
                        chart.classList.toggle('ck-chart-fullscreen');
                    }
                });
                chart.appendChild(btn);
            });
        }
        addFullscreenButtons();
        setInterval(addFullscreenButtons, 1000);
    })();
    </script>
    """,
    height=0,
    width=0,
)


def is_valid_number(value):

    return (
        value is not None
        and np.isfinite(value)
        and not np.isnan(value)
    )
fluid_map = {
    "Water": "Water",
    "CO₂": "CO2",
    "Ammonia": "Ammonia",
    "R134a": "R134a",
    "Air": "Air"
}
fluid_limits = {

    "Water": {
        "P_min": 0.01,
        "P_max": 10000.0,
        "T_min": 0.01,
        "T_max": 2000.0, 
        "H_min": 0.0,
        "H_max": 5000.0, 
        "S_min": 0.0,
        "S_max": 15.0,
        "V_min": 0.0001,
        "V_max": 500.0
    },

    "CO₂": {

        "P_min": 0.1,
        "P_max": 500.0,

        
        "T_min": -120.0,
        "T_max": 300.0,

        "H_min": -500.0,
        "H_max": 1200.0,

        "S_min": -2.0,
        "S_max": 6.0,

        "V_min": 0.00005,
        "V_max": 50.0
    },

    "Ammonia": {

        "P_min": 0.05,
        "P_max": 300.0,

        "T_min": -77.0,
        "T_max": 200.0,

        "H_min": 0.0,
        "H_max": 2500.0,

        "S_min": 0.0,
        "S_max": 10.0,

        "V_min": 0.0001,
        "V_max": 50.0
    },

    "R134a": {

        "P_min": 0.05,
        "P_max": 100.0,

        "T_min": -100.0,
        "T_max": 150.0,

        "H_min": 0.0,
        "H_max": 700.0,

        "S_min": 0.0,
        "S_max": 5.0,

        "V_min": 0.0001,
        "V_max": 10.0
    },

    "Air": {

        "P_min": 0.01,
        "P_max": 500.0,

        "T_min": -150.0,
        "T_max": 1500.0,

        "H_min": 0.0,
        "H_max": 3000.0,

        "S_min": 0.0,
        "S_max": 15.0,

        "V_min": 0.0001,
        "V_max": 500.0
    }
}

def get_plot_temperature_range(fluid_display):

    limits = fluid_limits[fluid_display]

    Tmin = limits['T_min'] + 273.15
    Tmax = limits['T_max'] + 273.15

    return Tmin, Tmax

def safe_props(output, i1, v1, i2, v2, fluid):

    try:
        return PropsSI(output, i1, v1, i2, v2, fluid)

    except Exception:
        return np.nan
    

@functools.lru_cache(maxsize=200000)
def cached_props(output, i1, v1, i2, v2, fluid):

    try:
        return PropsSI(output, i1, float(v1), i2, float(v2), fluid)

    except:
        return np.nan


@functools.lru_cache(maxsize=200000)
def cached_propsi(output, i1, v1, i2, v2, fluid):
    
    return PropsSI(output, i1, float(v1), i2, float(v2), fluid)

@st.cache_data(show_spinner=False)
def build_isobar_path(P, T_start, T_end, fluid_name, n_seg=60):
    
    Ss_, Ts_, Hs_ = [], [], []

    def add_PT(T_k):
        try:
            s_v = cached_propsi('S', 'P', P, 'T', T_k, fluid_name)
            h_v = cached_propsi('H', 'P', P, 'T', T_k, fluid_name)
            if is_valid_number(s_v) and is_valid_number(h_v):
                Ss_.append(s_v / 1000)
                Ts_.append(T_k - 273.15)
                Hs_.append(h_v / 1000)
        except Exception:
            pass

    def add_PQ(Q):
        try:
            T_sat = cached_propsi('T', 'P', P, 'Q', Q, fluid_name)
            s_v = cached_propsi('S', 'P', P, 'Q', Q, fluid_name)
            h_v = cached_propsi('H', 'P', P, 'Q', Q, fluid_name)
            if is_valid_number(s_v) and is_valid_number(h_v):
                Ss_.append(s_v / 1000)
                Ts_.append(T_sat - 273.15)
                Hs_.append(h_v / 1000)
        except Exception:
            pass

    try:
        Tsat_ = cached_propsi('T', 'P', P, 'Q', 0, fluid_name)
    except Exception:
        Tsat_ = np.nan

    add_PT(T_start)

    if np.isfinite(Tsat_) and T_start < Tsat_ <= T_end:
        
        n_liq = max(int(n_seg * 0.35), 12)
        for T_k in np.linspace(T_start, Tsat_, n_liq + 1)[1:-1]:
            add_PT(T_k)

        
        
        add_PQ(0.0)
        n_mix = max(int(n_seg * 0.30), 16)
        for Q in np.linspace(0.0, 1.0, n_mix + 1)[1:]:
            add_PQ(float(Q))

        
        if T_end > Tsat_:
            n_vap = max(int(n_seg * 0.35), 12)
            for T_k in np.linspace(Tsat_, T_end, n_vap + 1)[1:-1]:
                add_PT(T_k)
            add_PT(T_end)
        else:
            
            add_PQ(1.0)
    elif np.isfinite(Tsat_) and T_end < Tsat_ <= T_start:
        
        n_vap = max(int(n_seg * 0.35), 12)
        for T_k in np.linspace(T_start, Tsat_, n_vap + 1)[1:-1]:
            add_PT(T_k)
        add_PQ(1.0)
        n_mix = max(int(n_seg * 0.30), 16)
        for Q in np.linspace(1.0, 0.0, n_mix + 1)[1:]:
            add_PQ(float(Q))
        if T_end < Tsat_:
            n_liq = max(int(n_seg * 0.35), 12)
            for T_k in np.linspace(Tsat_, T_end, n_liq + 1)[1:-1]:
                add_PT(T_k)
            add_PT(T_end)
        else:
            add_PQ(0.0)
    else:
        
        for T_k in np.linspace(T_start, T_end, n_seg + 1)[1:-1]:
            add_PT(T_k)
        add_PT(T_end)

    return Ss_, Ts_, Hs_
def fmt(value, digits=5):

    try:

        if value is None:
            return "N/A"

        if np.isnan(value):
            return "N/A"

        return round(value, digits)

    except:
        return "N/A"
@st.cache_data(show_spinner=False)
def has_saturation_dome(fluid):
    try:
        PropsSI('Tcrit', fluid)
        PropsSI('Ttriple', fluid)

        PropsSI(
            'P',
            'T',
            300,
            'Q',
            0,
            fluid
        )

        return True

    except:
        return False
UNIT_DEFS = {
    "P": {  
        "canonical": "bar",
        "factors": {
            "Pa": 1e-5, "kPa": 1e-2, "MPa": 10.0, "GPa": 1e4,
            "bar": 1.0, "atm": 1.01325, "psi": 0.0689476,
            "mmHg": 0.00133322, "kgf/cm²": 0.980665,
        },
    },
    "H": {  
        "canonical": "kJ/kg",
        "factors": {
            "J/kg": 1e-3, "kJ/kg": 1.0, "MJ/kg": 1000.0,
            "kcal/kg": 4.184, "BTU/lb": 2.326,
        },
    },
    "S": {  
        "canonical": "kJ/kg.K",
        "factors": {
            "J/kg.K": 1e-3, "kJ/kg.K": 1.0,
            "kcal/kg.K": 4.184, "BTU/lb.R": 4.1868,
        },
    },
    "V": {  
        "canonical": "m³/kg",
        "factors": {
            "m³/kg": 1.0, "L/kg": 1e-3, "cm³/g": 1e-3, "ft³/lb": 0.0624280,
        },
    },
}

_T_UNITS = ["°C", "K", "°F", "°R"]


def _t_to_c(value, unit):
    if unit == "°C":
        return value
    if unit == "K":
        return value - 273.15
    if unit == "°F":
        return (value - 32.0) * 5.0 / 9.0
    if unit == "°R":
        return value * 5.0 / 9.0 - 273.15
    return value


def _c_to_t(value_c, unit):
    if unit == "°C":
        return value_c
    if unit == "K":
        return value_c + 273.15
    if unit == "°F":
        return value_c * 9.0 / 5.0 + 32.0
    if unit == "°R":
        return (value_c + 273.15) * 9.0 / 5.0
    return value_c


def _to_canonical(value, unit, kind):
    
    if kind == "T":
        return _t_to_c(value, unit)
    return value * UNIT_DEFS[kind]["factors"][unit]


def _from_canonical(value_canon, unit, kind):
    
    if kind == "T":
        return _c_to_t(value_canon, unit)
    return value_canon / UNIT_DEFS[kind]["factors"][unit]


def disp_unit(kind):
    
    canonical_unit = "°C" if kind == "T" else UNIT_DEFS[kind]["canonical"]
    return st.session_state.get(f"disp_unit_{kind}", canonical_unit)


def fmt_canon(value_canon, kind, decimals=None):
    
    u = disp_unit(kind)
    try:
        v = _from_canonical(value_canon, u, kind)
    except Exception:
        v = value_canon
    if decimals is not None:
        try:
            v = round(v, decimals)
        except Exception:
            pass
    return v, u
def axis_title(base_label, kind):
    
    return f"{base_label} ({disp_unit(kind)})"
def conv(value, kind):
    
    u = disp_unit(kind)
    try:
        return _from_canonical(value, u, kind)
    except Exception:
        return value


def tc():
    
    if _is_dark():
        return dict(
            isotherm='rgba(239, 68, 68, 0.55)', isobar='rgba(0, 220, 220, 0.55)',
            dome_liq='#00e5ff', dome_vap='#3b82f6',
            state='#ffd23f', marker='#ffffff', marker_line='#000000',
            pump='#39FF14', boiler='#ffd23f', turbine='#ff9f1c',
            condenser='#FF3CAC', supercrit='#ff9f1c', reheat='#ff7a1a',
            grid='#3a2f24', fwh='#38bdf8', extraction='#9aa5b1', label_text='#ffffff',
        )
    else:
        return dict(
            isotherm='rgba(190, 24, 30, 0.55)', isobar='rgba(8, 118, 150, 0.55)',
            dome_liq='#0d7d99', dome_vap='#1d4ed8',
            state='#b45309', marker='#17120a', marker_line='#ffffff',
            pump='#15803d', boiler='#b45309', turbine='#c2410c',
            condenser='#a3175c', supercrit='#c2410c', reheat='#c2410c',
            grid='#e7d9bc', fwh='#0369a1', extraction='#8a7a5f', label_text='#17120a',
        )
def show_state_table(data):
    if isinstance(data, pd.DataFrame):
        # Every column here mixes fmt()-rounded numbers with plain-text
        # labels (phase names, "N/A", "—") — pandas ends up with an
        # 'object' dtype pyarrow can't reliably infer, which otherwise
        # surfaces as a silent ArrowInvalid recovery (and a noisy log)
        # every time one of these tables renders. Stringify for display;
        # nothing downstream needs these as numeric dtypes.
        data = data.astype(str)
    styled = data.style if isinstance(data, pd.DataFrame) else data
    try:
        styled = styled.hide(axis="index")
    except (AttributeError, TypeError):
        styled = styled.hide_index()  
    st.table(styled)


_RENDERED_UNIT_DROPDOWNS = set()  


def unit_number_input(label, kind, min_value, max_value, value, step, key, help=None, format=None):
    
    unit_options = _T_UNITS if kind == "T" else list(UNIT_DEFS[kind]["factors"].keys())
    canonical_unit = "°C" if kind == "T" else UNIT_DEFS[kind]["canonical"]

    unit_key = f"disp_unit_{kind}"          
    prev_key = f"disp_unit_{kind}__prevu"
    field_unit_key = f"{key}__unit"          

    if unit_key not in st.session_state:
        st.session_state[unit_key] = canonical_unit
    if prev_key not in st.session_state:
        st.session_state[prev_key] = st.session_state[unit_key]
    if key not in st.session_state:
        st.session_state[key] = float(_from_canonical(value, st.session_state[unit_key], kind))

    st.session_state[field_unit_key] = st.session_state[unit_key]

    def _sync_shared_unit(_unit_key=unit_key, _field_unit_key=field_unit_key):
        st.session_state[_unit_key] = st.session_state[_field_unit_key]
    c_field, c_unit = st.container(key=f"unitrow_{key}").columns([62, 38])

    with c_unit:
        chosen_unit = st.selectbox(
            "Unit", unit_options, key=field_unit_key,
            on_change=_sync_shared_unit, label_visibility="visible"
        )
    if chosen_unit != st.session_state[prev_key]:
        cur_canon = _to_canonical(st.session_state[key], st.session_state[prev_key], kind)
        st.session_state[key] = _from_canonical(cur_canon, chosen_unit, kind)
        st.session_state[prev_key] = chosen_unit
    disp_min = _from_canonical(min_value, chosen_unit, kind)
    disp_max = _from_canonical(max_value, chosen_unit, kind)
    if disp_min > disp_max:
        disp_min, disp_max = disp_max, disp_min
    disp_step = abs(_from_canonical(min_value + step, chosen_unit, kind) - disp_min) or step
    with c_field:
        entered = st.number_input(
            label,
            min_value=float(disp_min),
            max_value=float(disp_max),
            step=float(disp_step),
            key=key,
            help=help,
            **({"format": format} if format else {}),
        )

    return _to_canonical(entered, chosen_unit, kind)
if "app_theme" not in st.session_state:
    _theme_qp = st.query_params.get("theme")
    if _theme_qp in ("dark", "light"):
        st.session_state.app_theme = _theme_qp
    else:
        # No explicit choice yet (no toggle used this session). Follow the
        # browser/OS preference Streamlit itself already resolved — this is
        # synchronous on the very first run, no JS/reload/flash needed.
        _system_theme = None
        try:
            _system_theme = st.context.theme.type
        except Exception:
            pass
        st.session_state.app_theme = _system_theme if _system_theme in ("dark", "light") else "dark"

def _toggle_theme():
    st.session_state.app_theme = "light" if st.session_state.app_theme == "dark" else "dark"  
    st.query_params["theme"] = st.session_state.app_theme
def _is_dark():
    return st.session_state.app_theme == "dark"
def _theme_qs(): 
    return f"theme={st.session_state.app_theme}"
_DARK_CSS = _read_text_asset(f"{ASSET_CSS_DIR}/theme_dark.css")

_LIGHT_CSS = _read_text_asset(f"{ASSET_CSS_DIR}/theme_light.css")

_active_css = _DARK_CSS if _is_dark() else _LIGHT_CSS

st.markdown(f"<style>{_active_css}</style>", unsafe_allow_html=True)
_base_reset_css = _read_text_asset(f"{ASSET_CSS_DIR}/base_reset.css")
st.markdown(f"<style>{_base_reset_css}</style>", unsafe_allow_html=True)
_RESPONSIVE_CSS = _read_text_asset(f"{ASSET_CSS_DIR}/responsive.css")
st.markdown(f"<style>{_RESPONSIVE_CSS}</style>", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# EXTRA_CSS — one place for everything added on top of the original
# theme/responsive stylesheets: standard mobile typography, the splash
# screen, the photo dashboard cards, square selection cards, the
# scrollbar treatment, and general spacing tightening. Kept as its own
# block (loaded last, so it wins the cascade) instead of scattered edits
# through the older CSS, to keep this batch of changes easy to find.
# ---------------------------------------------------------------------
_EXTRA_CSS = _read_text_asset(f"{ASSET_CSS_DIR}/extra.css")
st.markdown(f"<style>{_EXTRA_CSS}</style>", unsafe_allow_html=True)

_MOBILE_APP_CSS = """
:root {
    scrollbar-color: rgba(128, 112, 92, 0.72) transparent;
    scrollbar-width: thin;
}
html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {
    scrollbar-color: rgba(128, 112, 92, 0.72) transparent !important;
    scrollbar-width: thin !important;
}
html::-webkit-scrollbar, body::-webkit-scrollbar, [data-testid="stAppViewContainer"]::-webkit-scrollbar, [data-testid="stAppViewBlockContainer"]::-webkit-scrollbar {
    width: 7px;
    height: 7px;
}
html::-webkit-scrollbar-track, body::-webkit-scrollbar-track, [data-testid="stAppViewContainer"]::-webkit-scrollbar-track, [data-testid="stAppViewBlockContainer"]::-webkit-scrollbar-track {
    background: transparent !important;
}
html::-webkit-scrollbar-thumb, body::-webkit-scrollbar-thumb, [data-testid="stAppViewContainer"]::-webkit-scrollbar-thumb, [data-testid="stAppViewBlockContainer"]::-webkit-scrollbar-thumb {
    background: rgba(128, 112, 92, 0.72) !important;
    border-radius: 999px;
    border: 1px solid transparent;
    background-clip: padding-box;
}
html::-webkit-scrollbar-thumb:hover, body::-webkit-scrollbar-thumb:hover, [data-testid="stAppViewContainer"]::-webkit-scrollbar-thumb:hover, [data-testid="stAppViewBlockContainer"]::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 194, 255, 0.9) !important;
}
[data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"], .main, .block-container {
    overflow-x: clip !important;
}
.st-key-topnav {
    position: sticky !important;
    top: 0 !important;
    z-index: 900000 !important;
    isolation: isolate;
}
.st-key-topnav .app-header {
    min-width: 0 !important;
}
.st-key-topnav .brand-logo {
    width: 30px !important;
    height: 30px !important;
    min-width: 30px !important;
    max-width: 30px !important;
    object-fit: contain !important;
    border-radius: 8px !important;
}
.st-key-topnav .brand .txt {
    font-size: 0.98rem !important;
    line-height: 1.08 !important;
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
.st-key-topnav .brand .txt .active {
    font-size: 0.62rem !important;
    line-height: 1.1 !important;
}
section[data-testid="stSidebar"] {
    z-index: 1000000 !important;
    isolation: isolate !important;
    overflow: hidden !important;
}
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
    position: relative !important;
    z-index: 1 !important;
}
section[data-testid="stSidebar"] .nav-brand {
    min-width: 0 !important;
}
section[data-testid="stSidebar"] .nav-brand .nav-logo {
    width: 32px !important;
    height: 32px !important;
    min-width: 32px !important;
    max-width: 32px !important;
    object-fit: contain !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] .nav-brand .txt {
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    font-size: 0.98rem !important;
}
section[data-testid="stSidebar"] .nav-brand .txt small {
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
section[data-testid="stSidebar"] * {
    box-sizing: border-box;
}
@media (max-width: 640px) {
    .block-container {
        width: 100% !important;
        max-width: 100% !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
    }
    .st-key-topnav {
        margin-left: -12px !important;
        margin-right: -12px !important;
        padding-left: 8px !important;
        padding-right: 8px !important;
    }
    .st-key-topnav .brand-logo {
        width: 26px !important;
        height: 26px !important;
        min-width: 26px !important;
        max-width: 26px !important;
    }
    .st-key-topnav .brand .txt {
        font-size: 0.88rem !important;
    }
    .st-key-topnav .brand .txt .active {
        font-size: 0.55rem !important;
        letter-spacing: 1px !important;
    }
    section[data-testid="stSidebar"] {
        width: min(84vw, 320px) !important;
        min-width: 230px !important;
        max-width: 320px !important;
    }
    section[data-testid="stSidebar"] .nav-brand .nav-logo {
        width: 30px !important;
        height: 30px !important;
        min-width: 30px !important;
        max-width: 30px !important;
    }
    section[data-testid="stSidebar"] .nav-brand .txt {
        font-size: 0.92rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        overflow-x: hidden !important;
        overflow-y: auto !important;
        max-height: calc(100vh - 8px) !important;
        padding-bottom: 24px !important;
    }
    .st-key-sidebar_backdrop {
        z-index: 999990 !important;
    }
}

/* ---- Fallback fullscreen state for charts on browsers without the
   Fullscreen API (or where it's blocked inside an iframe) ---- */
.ck-chart-fullscreen {
    position: fixed !important;
    inset: 0 !important;
    z-index: 999999 !important;
    background: var(--ck-fs-bg, #14100c) !important;
    padding: 12px !important;
    height: 100vh !important;
    width: 100vw !important;
}
"""
st.markdown(f"<style>{_MOBILE_APP_CSS}</style>", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Splash screen — logo + tagline, shown once per browser session before
# the actual app appears. Rendered after the theme CSS above so its
# colors match whichever theme is active.
# ---------------------------------------------------------------------
if "splash_done" not in st.session_state:
    st.session_state.splash_done = False
if not st.session_state.splash_done:
    _splash_bg = "#14100c" if _is_dark() else "#fbf4e8"
    _splash_name_c = "#f2f6fa" if _is_dark() else "#17120a"
    _splash_quote_c = "#9fb3c2" if _is_dark() else "#5c4f3d"
    _splash_logo = _img_data_uri(LOGO_PATH)
    st.markdown(
        f'<div class="ck-splash" style="background:{_splash_bg};">'
        f'<img class="ck-splash-logo" src="{_splash_logo}" alt="{APP_NAME}" />'
        f'<div class="ck-splash-name" style="color:{_splash_name_c};">{APP_NAME}</div>'
        f'<div class="ck-splash-quote" style="color:{_splash_quote_c};">&ldquo;{APP_QUOTE}&rdquo;</div>'
        '</div>',
        unsafe_allow_html=True
    )
    time.sleep(1.8)
    st.session_state.splash_done = True
    st.rerun()

_sidebar_open = st.session_state.get("sidebar_open", False)
# NOTE: the "Close menu" button below is now ALWAYS rendered (same key,
# same position, every rerun) instead of being conditionally shown/hidden
# by an if/else branch. Toggling that button's presence in the tree used
# to shift the auto-generated identity of every unkeyed element rendered
# after it (including the plotly charts further down the page), which is
# what caused charts to flicker/disappear whenever the hamburger menu was
# opened or closed. Visibility is now handled purely with CSS.
if _sidebar_open:
    st.markdown(
        '<style>section[data-testid="stSidebar"] {'
        ' display: block !important; transform: translateX(0) !important;'
        ' visibility: visible !important; pointer-events: auto !important; }'
        ' .st-key-sidebar_backdrop { display: block !important; }'
        ' .st-key-burger_toggle { visibility: hidden !important; pointer-events: none !important; }'
        ' </style>',
        unsafe_allow_html=True
    )
else:
    st.markdown(
        '<style>section[data-testid="stSidebar"] {'
        ' transform: translateX(100%) !important;'
        ' pointer-events: none !important; }'
        ' div[data-testid="stSidebarUserContent"] { visibility: hidden; }'
        ' .st-key-sidebar_backdrop { display: none !important; }'
        ' .st-key-burger_toggle { visibility: visible !important; pointer-events: auto !important; }'
        ' </style>',
        unsafe_allow_html=True
    )
if st.button("Close menu", key="sidebar_backdrop", help="Close menu"):
    st.session_state.sidebar_open = False
    st.rerun()
if "wizard_step" not in st.session_state:
    st.session_state.wizard_step = "welcome"          
if "wizard_mode" not in st.session_state:
    st.session_state.wizard_mode = None                
if "wizard_cycle_type" not in st.session_state:
    st.session_state.wizard_cycle_type = None           
if "sidebar_open" not in st.session_state:
    st.session_state.sidebar_open = False              
CYCLE_FLUID = {"rankine": "Water", "brayton": "Air"}

def get_wizard_steps():
    if st.session_state.wizard_mode == "cycles":
        return ["welcome", "cycle_type", "workspace"]
    return ["welcome", "fluid", "workspace"]


def get_wizard_labels():
    if st.session_state.wizard_mode == "cycles":
        return {"welcome": "1 · Mode", "cycle_type": "2 · Cycle", "workspace": "3 · Inputs & Output"}
    return {"welcome": "1 · Mode", "fluid": "2 · Fluid", "workspace": "3 · Inputs & Output"}

_qp = st.query_params
if "mode" in _qp:
    _req_mode = _qp["mode"]
    if _req_mode == "explorer":
        st.session_state.wizard_mode = "explorer"
        st.session_state.wizard_step = "fluid"
    elif _req_mode == "cycles":
        st.session_state.wizard_mode = "cycles"
        st.session_state.wizard_cycle_type = None
        st.session_state.wizard_step = "cycle_type"
    st.query_params.clear()
    st.rerun()
if "cycle" in _qp:
    _req_cycle = _qp["cycle"]
    if _req_cycle in ("rankine", "brayton"):       
        st.session_state.wizard_mode = "cycles"
        st.session_state.wizard_cycle_type = _req_cycle
        st.session_state.fluid_select = CYCLE_FLUID[_req_cycle]      
        st.session_state.wizard_step = "workspace"
    st.query_params.clear()
    st.rerun()
if "restart" in _qp:
    st.session_state.wizard_step = "welcome"
    st.session_state.wizard_mode = None
    st.session_state.wizard_cycle_type = None
    st.query_params.clear()
    st.rerun()
st.session_state.app_view = st.session_state.wizard_mode or "home"
def _go(view_name):
    st.session_state.wizard_mode = view_name
    if view_name == "cycles":
        st.session_state.wizard_cycle_type = None
        st.session_state.wizard_step = "cycle_type"
    else:
        st.session_state.wizard_step = "fluid"
def render_cycle_type_select():
    render_header("Choose Cycle Type")
    st.markdown("### Which power cycle do you want to analyze?")
    st.caption("Each cycle uses a fixed working fluid, so you'll go straight to inputs after this.")
    cc1, cc2 = st.container(key="iconrow_cycle").columns(2, gap="small")
    with cc1:
        st.markdown(f"""
        <a class="dash-card-link" href="?cycle=rankine&{_theme_qs()}" target="_self">
          <div class="dash-card dash-card-icon">
              <div class="icon">🔵</div>
              <h3>Rankine</h3>
          </div>
        </a>
        """, unsafe_allow_html=True)
    with cc2:
        st.markdown(f"""
        <a class="dash-card-link" href="?cycle=brayton&{_theme_qs()}" target="_self">
          <div class="dash-card dash-card-icon">
              <div class="icon">🟠</div>
              <h3>Brayton</h3>
          </div>
        </a>
        """, unsafe_allow_html=True)
    render_footer()
def render_welcome():
    render_header("")
    st.markdown("### What do you want to work on?")
    st.caption("Tap a card to continue")
    hc1, hc2 = st.container(key="iconrow_welcome").columns(2, gap="small")

    # Photos (base64 data URIs) and per-theme colors used in the card HTML
    _fluid_photo = _img_data_uri(FLUID_IMG_PATH)
    _cycle_photo = _img_data_uri(CYCLE_IMG_PATH)
    _card_bg = "#1d160f" if _is_dark() else "#fffdf8"
    _card_border = "#3a2c1c" if _is_dark() else "#e3d2ad"
    _card_title_c = "#f2f6fa" if _is_dark() else "#17120a"
    _card_sub_c = "#b3a690" if _is_dark() else "#5c4f3d"

    with hc1:
        st.markdown(
            f"""
            <a class="dash-card-link" href="?mode=explorer&{_theme_qs()}" target="_self">
              <div class="dash-card-v2" style="background:{_card_bg};border-color:{_card_border};">
                  <div class="dash-card-v2-img" style="background-image:url('{_fluid_photo}')"></div>
                  <div class="dash-card-v2-body">
                      <div class="icon">🌡️</div>
                      <div class="txt">
                          <h3 style="color:{_card_title_c};margin:0;">Fluids</h3>
                          <p style="color:{_card_sub_c};margin:2px 0 0 0;">Explore thermodynamic properties</p>
                      </div>
                  </div>
              </div>
            </a>
            """,
            unsafe_allow_html=True,
        )

    with hc2:
        st.markdown(
            f"""
            <a class="dash-card-link" href="?mode=cycles&{_theme_qs()}" target="_self">
              <div class="dash-card-v2" style="background:{_card_bg};border-color:{_card_border};">
                  <div class="dash-card-v2-img" style="background-image:url('{_cycle_photo}')"></div>
                  <div class="dash-card-v2-body">
                      <div class="icon">⚡</div>
                      <div class="txt">
                          <h3 style="color:{_card_title_c};margin:0;">Cycle</h3>
                          <p style="color:{_card_sub_c};margin:2px 0 0 0;">Analyze power cycles</p>
                      </div>
                  </div>
              </div>
            </a>
            """,
            unsafe_allow_html=True,
        )

    render_footer()
def render_fluid_select():
    render_header("Choose Working Fluid")
    st.markdown("### Select a working fluid")
    st.caption("This fluid is used for every calculation on the next screen.")
    fluid_icons = {"Water": "💧", "CO₂": "☁️", "Ammonia": "🧪", "R134a": "❄️", "Air": "💨"}  
    with st.container(key="fluid_select_grid"):
        cols = st.columns(len(fluid_map))
        for col, fname in zip(cols, fluid_map.keys()):
            with col:
                is_sel = st.session_state.get("fluid_select") == fname
                btn_label = f"{fluid_icons.get(fname, '⚛️')}\n\n{'✅ ' if is_sel else ''}{fname}"
                if st.button(btn_label, key=f"fluidcard_{fname}", use_container_width=True):
                    st.session_state.fluid_select = fname
                    st.session_state.wizard_step = "workspace"
                    st.rerun()
    st.divider()
    if st.session_state.get("fluid_select"):
        st.success(
            f"Selected fluid: **{st.session_state['fluid_select']}** — "
            f"tap another fluid above to change it."
        )
    else:
        st.info("Pick a fluid above to continue.")
    render_footer()
def render_header(active_label):    
    step = st.session_state.wizard_step
    wsteps = get_wizard_steps()
    idx = wsteps.index(step) if step in wsteps else 0
    with st.container(key="topnav"):        
        c_prev, c_brand, c_burger = st.columns([0.55, 7.0, 0.55])
        with c_prev:
            can_prev = idx > 0
            if st.button("◀", key="wiz_prev_top", disabled=not can_prev, help="Previous"):
                st.session_state.wizard_step = wsteps[idx - 1]
                st.rerun()
        with c_brand:
            _logo_uri = _img_data_uri(LOGO_ICON_PATH)
            _active_html = f'<span class="active">{active_label}</span>' if active_label else ''
            st.markdown(
                '<div class="app-header"><div class="brand">'
                f'<img class="brand-logo top-logo" src="{_logo_uri}" alt="logo" />'
                f'<div class="txt">{APP_NAME}{_active_html}</div></div></div>',
                unsafe_allow_html=True
            )
        with c_burger:
            if st.button("☰", key="burger_toggle", help="Show menu", use_container_width=True):
                st.session_state.sidebar_open = True
                st.rerun()
def render_topbar(active_label):
    render_header(active_label)
def render_footer():
    # Footer removed from every page per product decision — kept as a
    # no-op (instead of deleting every call site) so nothing else needs
    # to change.
    return
def render_nav_sidebar():
    step = st.session_state.wizard_step
    with st.sidebar:
        _sb_close_col, _sb_brand_col = st.columns([1, 5])
        with _sb_close_col:
            if st.button("✕", key="sidebar_close_x", help="Close menu"):
                st.session_state.sidebar_open = False
                st.rerun()
        with _sb_brand_col:
            _sb_logo_uri = _img_data_uri(LOGO_ICON_PATH)
            st.markdown(
                f'<div class="nav-brand"><img class="brand-logo nav-logo" src="{_sb_logo_uri}" alt="logo" />'
                f'<div class="txt">{APP_NAME}<small>Fluid &amp; Cycle Analysis</small></div></div>',
                unsafe_allow_html=True
            )
        st.markdown(
            '<div class="sb-profile">'
            '<div class="sb-avatar">👤</div>'
            '<div class="sb-profile-txt"><b>Guest User</b><br>'
            '<small>Not signed in</small></div>'
            '</div>',
            unsafe_allow_html=True
        )
        _sidebar_dark = st.toggle(
            "🌙 Dark Mode", value=_is_dark(), key="theme_toggle_sidebar",
            help="Switch dark / light mode — applies everywhere in the app, on every page."
        )
        if _sidebar_dark != _is_dark():
            _toggle_theme()
            st.rerun()
        with st.expander("🔔 Notifications"):
            st.caption("No new activity right now — you're all caught up.")
            st.caption("• Welcome to Curious Kelvin — Fluid & Cycle Simulation Lab!")
            st.caption("• Tip: tap a state point marker on any chart for exact values.")
        with st.expander("❓ Help & Support"):
            st.caption("**Getting started:** pick Fluids or Cycle from the home "
                       "screen, choose a fluid, then adjust inputs on the left.")
            st.caption("**Stuck on a calculation?** Check that your pressures and "
                       "temperatures stay within each fluid's valid range.")
            if st.button("📧 Contact support", key="sb_contact_support", use_container_width=True):
                st.toast("This is option under progess", icon="📧")
        with st.expander("ℹ️ About this app"):
            st.caption("**Curious Kelvin — Fluid & Cycle Simulation Lab**  \nVersion 1.0.0")
            st.caption("Built with Streamlit, Plotly &amp; CoolProp.")
        if st.button("⭐ Rate this app", key="sb_rate_app", use_container_width=True):
            st.toast("Thanks for the feedback! ⭐⭐⭐⭐⭐", icon="⭐")
        if st.button("📤 Share app", key="sb_share_app", use_container_width=True):
            st.toast("Link copied! (demo — sharing isn't wired up yet)", icon="📤")
        if st.button("🚪 Sign Out", key="sb_sign_out", use_container_width=True):
            st.toast("You're browsing as a Guest — no sign-in is required.", icon="🚪")
        st.divider()
        global fluid_display, fluid, limits, is_two_phase_fluid, want_quality
        if step == "welcome":
            fluid_display = st.session_state.get("fluid_select", list(fluid_map.keys())[0])
            fluid = fluid_map[fluid_display]
            limits = fluid_limits[fluid_display]
            is_two_phase_fluid = has_saturation_dome(fluid)
            want_quality = st.session_state.get("quality_check", True) if is_two_phase_fluid else False
        elif step == "cycle_type":
            st.markdown(
                '<div class="small-box">Tap <b>Rankine</b> or <b>Brayton</b> in the main '
                'panel — you\'ll go straight to inputs, since each cycle uses a fixed '
                'working fluid.</div>', unsafe_allow_html=True
            )
            fluid_display = st.session_state.get("fluid_select", list(fluid_map.keys())[0])
            fluid = fluid_map[fluid_display]
            limits = fluid_limits[fluid_display]
            is_two_phase_fluid = has_saturation_dome(fluid)
            want_quality = st.session_state.get("quality_check", True) if is_two_phase_fluid else False
        elif step == "fluid":
            st.markdown(
                '<div class="small-box">Tap a fluid card in the main panel to '
                'continue to your workspace.</div>', unsafe_allow_html=True
            )
            fluid_display = st.session_state.get("fluid_select", list(fluid_map.keys())[0])
            fluid = fluid_map[fluid_display]
            limits = fluid_limits[fluid_display]
            is_two_phase_fluid = has_saturation_dome(fluid)
            want_quality = st.session_state.get("quality_check", True) if is_two_phase_fluid else False
        else:
            st.title("⚙ Control Panel")
            fluid_display = st.session_state.get("fluid_select", list(fluid_map.keys())[0])
            if st.session_state.wizard_mode == "cycles":
                cyc = st.session_state.get("wizard_cycle_type")
                cyc_label = {"rankine": "🔵 Rankine Cycle", "brayton": "🟠 Brayton Cycle"}.get(cyc, "Cycle")
                st.markdown(f"**{cyc_label}**  \nWorking Fluid: {fluid_display} (fixed)")
                if st.button("🔄 Change cycle type", key="change_cycle_btn", use_container_width=True):
                    st.session_state.wizard_step = "cycle_type"
                    st.rerun()
            else:
                st.markdown(f"**Working Fluid:** {fluid_display}")
                if st.button("🔄 Change fluid", key="change_fluid_btn", use_container_width=True):
                    st.session_state.wizard_step = "fluid"
                    st.rerun()
            fluid = fluid_map[fluid_display]
            limits = fluid_limits[fluid_display]
            is_two_phase_fluid = has_saturation_dome(fluid)
            st.divider()
            want_quality = st.session_state.get("quality_check", True) if is_two_phase_fluid else False
render_nav_sidebar()
if st.session_state.wizard_step == "welcome":
    render_welcome()
    st.stop()
if st.session_state.wizard_step == "cycle_type":
    render_cycle_type_select()
    st.stop()
if st.session_state.wizard_step == "fluid":
    render_fluid_select()
    st.stop()
def solve_state(i1, v1, i2, v2, fluid):
    state = {}
    state['P'] = safe_props('P', i1, v1, i2, v2, fluid)
    state['T'] = safe_props('T', i1, v1, i2, v2, fluid)
    state['D'] = safe_props('D', i1, v1, i2, v2, fluid)
    state['H'] = safe_props('H', i1, v1, i2, v2, fluid)
    state['S'] = safe_props('S', i1, v1, i2, v2, fluid)
    state['U'] = safe_props('U', i1, v1, i2, v2, fluid)
    if np.isnan(state['D']) or state['D'] <= 0:
        state['V'] = np.nan
    else:
        state['V'] = 1 / state['D']
    return state
def detect_phase(state, quality, Tsat, fluid):
    P = state['P']
    T = state['T']
    tol = 0.05  
    try:
        Tsat_local = PropsSI('T', 'P', P, 'Q', 0, fluid)
    except:
        Tsat_local = np.nan
    if np.isfinite(Tsat_local):
        if abs(T - Tsat_local) <= tol:
            return "Saturated State"
    try:
        phase = PhaseSI(
            'P',
            P,
            'T',
            T,
            fluid
        ).lower()
    except:
        phase = ""
    if np.isfinite(quality):
        if quality <= 0.001:
            return "Saturated Liquid"
        elif quality >= 0.999:
            return "Dry Saturated Vapor"
        elif 0 < quality < 1:
            return "Saturated State"
    if "supercritical" in phase:
        rho = state['D']
        try:
            rho_crit = PropsSI(
                'rhocrit',
                fluid
            )
            if rho > rho_crit:
                return "Supercritical Dense Fluid"
            else:
                return "Supercritical Gas"
        except:
            return "Supercritical Fluid"
    if "liquid" in phase:
        return "Subcooled Liquid"
    if "gas" in phase:
        return "Superheated Vapor"
    if "twophase" in phase:
        return "Saturated State"
    if "critical" in phase:
        return "Critical Region"
    try:
        Pc = PropsSI('pcrit', fluid)
        if P < Pc:
            Tsat = PropsSI(
                'T',
                'P',
                P,
                'Q',
                0,
                fluid
            )
            if T < Tsat:
                return "Subcooled Liquid"
            else:
                return "Superheated Vapor"
    except:
        pass
    return "Dense Fluid"
def sat_prop(output, input_type, value, Q, fluid):
    try:
        return PropsSI(
            output,
            input_type,
            value,
            'Q',
            Q,
            fluid
        )
    except Exception:
        return np.nan
@st.cache_data(show_spinner=False)
def generate_dome(fluid):
    if not has_saturation_dome(fluid):
        return None
    Tcrit = PropsSI('Tcrit', fluid)
    Ttriple = PropsSI('Ttriple', fluid)
    Ts = np.linspace(Ttriple + 0.1, Tcrit - 3.0, 150)
    data = {'T': [], 'P': [], 'vf': [], 'vg': [], 'sf': [], 'sg': [], 'hf': [], 'hg': []}
    for T in Ts:
        try:
            data['T'].append(T - 273.15)
            data['P'].append(cached_props('P', 'T', T, 'Q', 0, fluid) / 100000)
            data['vf'].append(1 / cached_props('D', 'T', T, 'Q', 0, fluid))
            data['vg'].append(1 / cached_props('D', 'T', T, 'Q', 1, fluid))
            data['sf'].append(cached_props('S', 'T', T, 'Q', 0, fluid) / 1000)
            data['sg'].append(cached_props('S', 'T', T, 'Q', 1, fluid) / 1000)
            data['hf'].append(cached_props('H', 'T', T, 'Q', 0, fluid) / 1000)
            data['hg'].append(cached_props('H', 'T', T, 'Q', 1, fluid) / 1000)
        except:
            pass
    return data
dome = generate_dome(fluid)
plot_config = {
    # Autoscale (+ the custom fullscreen ⛶ button injected on each chart
    # separately) is all that's left in the modebar now — Pan is removed
    # per request, on top of the box-zoom/zoom-in/out/reset-axes/download
    # buttons already dropped earlier.
    'displayModeBar': True,
    'responsive': True,
    'scrollZoom': True,
    'doubleClick': 'reset+autosize',
    'displaylogo': False,
    'modeBarButtonsToRemove': [
        'toImage', 'zoom2d', 'pan2d', 'select2d', 'lasso2d',
        'zoomIn2d', 'zoomOut2d', 'resetScale2d',
    ],
}
layout_common = dict(
    template='plotly_dark' if _is_dark() else 'plotly_white',
    height=600,  
    hovermode='closest',
    # dragmode=False turned out to disable more than just single-finger
    # drag/pan — Plotly's pinch-to-zoom touch handling is wired through the
    # same drag-interaction layer, so setting it to False silently killed
    # pinch-zoom too, which is why it stopped working after the pan button
    # was removed. 'zoom' is Plotly's own default: a single-finger/mouse
    # drag draws a rubber-band zoom box (it doesn't pan or reposition the
    # chart), and — critically — it leaves that same interaction layer
    # active, so two-finger pinch (scrollZoom, still on above) works again.
    dragmode='zoom',
    # A finger is far less precise than a mouse pointer, so the default
    # ~20px hover-detection radius is too tight for tap-to-see-tooltip on a
    # phone — widen it so a tap near a curve/marker still registers.
    hoverdistance=40,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color=tc()['label_text'], size=12),
    legend=dict(
        orientation='h',
        yanchor='bottom',
        y=1.02,
        xanchor='right',
        x=1,
        font=dict(size=10, color=tc()['label_text'])
    ),
    margin=dict(l=60, r=40, t=60, b=60)
)
layout_common_grid = dict(layout_common)
layout_common_grid.update(
    height=480,
    margin=dict(l=54, r=20, t=42, b=88),
    legend=dict(
        orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5,
        font=dict(size=10, color=tc()['label_text'])
    ),
)
if hasattr(st, "fragment"):
    @st.fragment
    def render_power_cycle_analysis():
        _render_power_cycle_analysis_body()
else:
    def render_power_cycle_analysis():
        _render_power_cycle_analysis_body()
def _render_power_cycle_analysis_body():
    st.divider()
    _cyc = st.session_state.get("wizard_cycle_type")
    if _cyc == "rankine":
        st.title("🔵 Rankine Cycle Analysis")
        st.caption("Working fluid: Water/Steam.")
    elif _cyc == "brayton":
        st.title("🟠 Brayton Cycle Analysis")
        st.caption("Working fluid: Air (gas-turbine cycle).")
    else:
        st.title("⚡ Power Cycle Analysis")
        st.caption("Rankine uses Water/Steam. Brayton uses Air as the gas-turbine working fluid.")
    cycle_tab1 = st.container(key="rankine_panel")
    cycle_tab2 = st.container(key="brayton_panel")
    if _cyc == "brayton":
        st.markdown('<style>.st-key-rankine_panel{display:none !important;}</style>', unsafe_allow_html=True)
    elif _cyc == "rankine":
        st.markdown('<style>.st-key-brayton_panel{display:none !important;}</style>', unsafe_allow_html=True)
    if fluid_display == "Water":
        with cycle_tab1:
            st.subheader("Ideal / Practical Rankine Cycle")
            st.caption(
                "State numbering follows the standard convention: "
                "1 = Condenser Exit / Pump Inlet · 2 = Pump Exit / Boiler Inlet · "
                "3 = Boiler Exit / Turbine Inlet · 4 = Turbine Exit / Condenser Inlet"
            )          
            with st.container(key="igrid_rk1"):
                rc1, rc2 = st.columns(2)
            with rc1:
                rk_Pboiler = unit_number_input(
                    "Boiler Pressure", "P",
                    min_value=1.0, max_value=218.0, value=80.0, step=1.0,
                    key="rk_Pboiler"
                )
            with rc2:
                rk_Tmain = unit_number_input(
                    "Turbine Inlet Temperature", "T",
                    min_value=374.0, max_value=650.0, value=540.0, step=5.0,
                    key="rk_Tmain_industrial",
                    help=(
                        "Actual main-steam temperature entering the turbine. "
                        "State 3 must be superheated; the simulator will not silently change this value."
                    )
                )
            with st.container(key="igrid_rk2"):
                rc3, rc4 = st.columns(2)
            with rc3:
                rk_Pcond = unit_number_input(
                    "Condenser Pressure", "P",
                    min_value=0.02, max_value=10.0, value=0.1, step=0.01,
                    key="rk_Pcond"
                )
            with rc4:
                rk_eta_turb = st.slider(
                    "Turbine Isentropic Efficiency", 0.5, 1.0, 1.0, 0.01,
                    key="rk_eta_turb"
                )
            with st.container(key="igrid_rk3"):
                rc5, rc6 = st.columns(2)
            with rc5:
                rk_eta_pump = st.slider(
                    "Pump Isentropic Efficiency", 0.5, 1.0, 1.0, 0.01,
                    key="rk_eta_pump"
                )
            eta_th = np.nan  
            if rk_Pcond >= rk_Pboiler:
                st.warning("Condenser Pressure must be lower than Boiler Pressure.")
            else:
                try:
                    P_boiler = rk_Pboiler * 1e5
                    P_cond = rk_Pcond * 1e5                    
                    h_1 = cached_propsi('H', 'P', P_cond, 'Q', 0, fluid)
                    s_1 = cached_propsi('S', 'P', P_cond, 'Q', 0, fluid)
                    T_1 = cached_propsi('T', 'P', P_cond, 'Q', 0, fluid)
                    x_1 = 0.0                   
                    h_2s = cached_propsi('H', 'P', P_boiler, 'S', s_1, fluid)
                    h_2 = h_1 + (h_2s - h_1) / rk_eta_pump
                    T_2 = cached_propsi('T', 'P', P_boiler, 'H', h_2, fluid)
                    s_2 = cached_propsi('S', 'P', P_boiler, 'H', h_2, fluid)
                    T_3 = rk_Tmain + 273.15
                    Tsat3 = cached_propsi('T', 'P', P_boiler, 'Q', 1, fluid)
                    if T_3 <= Tsat3:
                        raise ValueError(
                            f"State 3 must be superheated. At {rk_Pboiler:.1f} bar, "
                            f"saturation temperature is {Tsat3-273.15:.1f} °C. "
                            f"Enter a higher turbine inlet temperature."
                        )
                    h_3 = cached_propsi('H', 'P', P_boiler, 'T', T_3, fluid)
                    s_3 = cached_propsi('S', 'P', P_boiler, 'T', T_3, fluid)
                    h_4s = cached_propsi('H', 'P', P_cond, 'S', s_3, fluid)
                    h_4 = h_3 - rk_eta_turb * (h_3 - h_4s)
                    T_4 = cached_propsi('T', 'P', P_cond, 'H', h_4, fluid)
                    s_4 = cached_propsi('S', 'P', P_cond, 'H', h_4, fluid)
                    x_4 = np.nan
                    try:
                        q4 = cached_propsi('Q', 'P', P_cond, 'H', h_4, fluid)
                        if np.isfinite(q4) and 0.0 <= q4 <= 1.0:
                            x_4 = float(q4)
                    except Exception:
                        pass
                    if np.isfinite(x_4):
                        if x_4 < 0.95:
                            st.warning(
                                f"⚠️ Turbine exhaust dryness is x₄ = {x_4:.3f} "
                                f"({(1-x_4)*100:.1f}% moisture), below the selected design limit "
                                f"x ≥ 0.95. In a real plant this would be addressed with "
                                f"higher inlet/reheat temperature, different expansion staging, "
                                f"or a higher exhaust/intermediate pressure — not by silently changing your input."
                            )
                        else:
                            st.success(
                                f"✓ Turbine exhaust dryness x₄ = {x_4:.3f} "
                                f"({(1-x_4)*100:.1f}% moisture) satisfies the x ≥ 0.95 design check."
                            )
                    else:
                        try:
                            phase4 = PhaseSI('P', P_cond, 'T', T_4, fluid).lower()
                        except Exception:
                            phase4 = ''
                        if 'liquid' in phase4:
                            raise ValueError(
                                "The calculated turbine exhaust is liquid. This is not an acceptable "
                                "turbine exhaust condition for this model."
                            )
                    x_3 = np.nan  
                    Q_boiler = (h_3 - h_2) / 1000     
                    W_turbine = (h_3 - h_4) / 1000    
                    Q_condenser = (h_4 - h_1) / 1000  
                    W_pump = (h_2 - h_1) / 1000       
                    W_net = W_turbine - W_pump
                    eta_th = W_net / Q_boiler if Q_boiler > 0 else np.nan
                    bwr = W_pump / W_turbine if W_turbine > 0 else np.nan
                    rres1, rres2 = st.columns([1.2, 1])
                    with rres1:
                        phase_1 = "Saturated Liquid"
                        phase_2 = "Compressed/Subcooled Liquid"
                        phase_3 = "Superheated Vapor"
                        phase_4 = (
                            f"Wet Steam (x = {x_4:.3f})"
                            if np.isfinite(x_4)
                            else "Superheated Vapor"
                        )
                        state_rows = [
                            ["1 – Condenser Exit / Pump Inlet", fmt(conv(P_cond/1e5,'P'), 3), fmt(conv(T_1-273.15,'T'), 2), fmt(conv(h_1/1000,'H'), 2), fmt(conv(s_1/1000,'S'), 4), fmt(x_1, 3), phase_1],
                            ["2 – Pump Exit / Boiler Inlet", fmt(conv(P_boiler/1e5,'P'), 2), fmt(conv(T_2-273.15,'T'), 2), fmt(conv(h_2/1000,'H'), 2), fmt(conv(s_2/1000,'S'), 4), "—", phase_2],
                            ["3 – Boiler Exit / Turbine Inlet", fmt(conv(P_boiler/1e5,'P'), 2), fmt(conv(T_3-273.15,'T'), 2), fmt(conv(h_3/1000,'H'), 2), fmt(conv(s_3/1000,'S'), 4), "N/A", phase_3],
                            ["4 – Turbine Exit / Condenser Inlet", fmt(conv(P_cond/1e5,'P'), 3), fmt(conv(T_4-273.15,'T'), 2), fmt(conv(h_4/1000,'H'), 2), fmt(conv(s_4/1000,'S'), 4), fmt(x_4, 3) if np.isfinite(x_4) else "N/A", phase_4],
                        ]
                        df_rk = pd.DataFrame(
                            state_rows,
                            columns=["State", f"P ({disp_unit('P')})", f"T ({disp_unit('T')})", f"h ({disp_unit('H')})", f"s ({disp_unit('S')})", "Dry Fraction x", "Phase"]
                        )
                        show_state_table(df_rk)
                    with rres2:
                        st.markdown(f"""
                        <div class="info-box">
                        Q Boiler (2→3) = {Q_boiler:.1f} kJ/kg<br>
                        W Turbine (3→4) = {W_turbine:.1f} kJ/kg<br>
                        Q Condenser (4→1) = {Q_condenser:.1f} kJ/kg<br>
                        W Pump (1→2) = {W_pump:.1f} kJ/kg<br>
                        <hr style="border-color:#333;">
                        Net Work = {W_net:.1f} kJ/kg<br>
                        Thermal Efficiency = {eta_th*100:.2f} %<br>
                        Back Work Ratio = {bwr:.4f}
                        </div>
                        """, unsafe_allow_html=True)
                    s_boiler, T_boiler, h_boiler = build_isobar_path(P_boiler, T_2, T_3, fluid)
                    fig_rk_ts = go.Figure()
                    if dome is not None:
                        fig_rk_ts.add_trace(go.Scatter(
                            x=dome['sf'], y=dome['T'], mode='lines',
                            line=dict(color=tc()['dome_liq'], width=3), name='Sat Liquid'
                        ))
                        fig_rk_ts.add_trace(go.Scatter(
                            x=dome['sg'], y=dome['T'], mode='lines',
                            line=dict(color=tc()['dome_vap'], width=3), name='Sat Vapor'
                        ))
                    s1k, s2k, s3k, s4k = s_1/1000, s_2/1000, s_3/1000, s_4/1000
                    T1c, T2c, T3c, T4c = T_1-273.15, T_2-273.15, T_3-273.15, T_4-273.15
                    s_u_rk, t_u_rk = disp_unit('S'), disp_unit('T')
                    s1k, s2k, s3k, s4k = conv(s1k,'S'), conv(s2k,'S'), conv(s3k,'S'), conv(s4k,'S')
                    T1c, T2c, T3c, T4c = conv(T1c,'T'), conv(T2c,'T'), conv(T3c,'T'), conv(T4c,'T')
                    s_boiler = [conv(v, 'S') for v in s_boiler] if s_boiler else s_boiler
                    T_boiler = [conv(v, 'T') for v in T_boiler] if T_boiler else T_boiler
                    fig_rk_ts.add_trace(go.Scatter(
                        x=[s1k, s2k], y=[T1c, T2c], mode='lines',
                        line=dict(color=tc()['pump'], width=3), name='1→2 Pump',
                        hovertemplate=f"Pump (1→2)<br>s: %{{x:.4f}} {s_u_rk}<br>T: %{{y:.1f}} {t_u_rk}<extra></extra>"
                    ))
                    if s_boiler:
                        fig_rk_ts.add_trace(go.Scatter(
                            x=s_boiler,
                            y=T_boiler,
                            mode='lines',
                            line=dict(color=tc()['boiler'], width=4),
                            name='2→3 Boiler (Constant P)',
                            hovertemplate=(
                                f"<b>Boiler 2→3 — Constant Pressure</b>"
                                f"<br>s: %{{x:.4f}} {s_u_rk}"
                                f"<br>T: %{{y:.1f}} {t_u_rk}"
                                "<extra></extra>"
                            )
                        ))
                    else:
                        fig_rk_ts.add_trace(go.Scatter(
                            x=[s2k, s3k],
                            y=[T2c, T3c],
                            mode='lines',
                            line=dict(color=tc()['boiler'], width=4),
                            name='2→3 Boiler (Constant P)'
                        ))
                    turbine_hover = (
                        f"<b>Turbine 3→4</b>"
                        f"<br>s: %{{x:.4f}} {s_u_rk}"
                        f"<br>T: %{{y:.1f}} {t_u_rk}"
                        "<br>State 3: Superheated vapor"
                        + (
                            f"<br>State 4 dry fraction x: {x_4:.3f}"
                            if np.isfinite(x_4)
                            else "<br>State 4: Superheated vapor (x not defined)"
                        )
                        + "<extra></extra>"
                    )
                    fig_rk_ts.add_trace(go.Scatter(
                        x=[s3k, s4k], y=[T3c, T4c], mode='lines',
                        line=dict(color=tc()['turbine'], width=3), name='3→4 Turbine',
                        hovertemplate=turbine_hover
                    ))
                    fig_rk_ts.add_trace(go.Scatter(
                        x=[s4k, s1k], y=[T4c, T1c], mode='lines',
                        line=dict(color=tc()['condenser'], width=3), name='4→1 Condenser',
                        hovertemplate=f"Condenser (4→1)<br>s: %{{x:.4f}} {s_u_rk}<br>T: %{{y:.1f}} {t_u_rk}<extra></extra>"
                    ))
                    state_hover = [
                        (
                            f"<b>State 1 — Saturated Liquid</b>"
                            f"<br>s: %{{x:.4f}} {s_u_rk}"
                            f"<br>T: %{{y:.1f}} {t_u_rk}"
                            "<br>Dry fraction x: 0.000<extra></extra>"
                        ),
                        (
                            f"<b>State 2 — Pump Exit</b>"
                            f"<br>s: %{{x:.4f}} {s_u_rk}"
                            f"<br>T: %{{y:.1f}} {t_u_rk}"
                            "<br>Compressed/Subcooled Liquid<extra></extra>"
                        ),
                        (
                            f"<b>State 3 — Turbine Inlet</b>"
                            f"<br>s: %{{x:.4f}} {s_u_rk}"
                            f"<br>T: %{{y:.1f}} {t_u_rk}"
                            "<br>Superheated Vapor"
                            f"<br>Inlet temperature: {conv(T_3-273.15,'T'):.1f} {t_u_rk}"
                            "<br>Dry fraction x: N/A (superheated)"
                            "<extra></extra>"
                        ),
                        (
                            f"<b>State 4 — Turbine Exit</b>"
                            f"<br>s: %{{x:.4f}} {s_u_rk}"
                            f"<br>T: %{{y:.1f}} {t_u_rk}"
                            + (
                                f"<br>Dry fraction x: {x_4:.3f}"
                                f"<br>Moisture: {(1-x_4)*100:.2f}%"
                                if np.isfinite(x_4)
                                else "<br>Superheated Vapor<br>Dry fraction x: N/A"
                            )
                            + "<extra></extra>"
                        )
                    ]
                    fig_rk_ts.add_trace(go.Scatter(
                        x=[s1k, s2k, s3k, s4k],
                        y=[T1c, T2c, T3c, T4c],
                        mode='markers',
                        marker=dict(size=13, color=tc()['marker'], line=dict(color=tc()['marker_line'], width=2)),
                        name='State Points', showlegend=False,
                        hovertemplate=state_hover
                    ))
                    for sx, sy, label, ax, ay in [
                        (s1k, T1c, '1', -18, -20),
                        (s2k, T2c, '2', -18, 20),
                        (s3k, T3c, '3', 0, -18),
                        (s4k, T4c, '4', 0, 20),
                    ]:
                        fig_rk_ts.add_annotation(
                            x=sx, y=sy, text=label, showarrow=False,
                            xshift=ax, yshift=ay,
                            font=dict(color=tc()['label_text'], size=14)
                        )
                    mid_idx = len(s_boiler) // 2 if s_boiler else 0
                    boiler_ann_x = s_boiler[mid_idx] if s_boiler else (s2k + s3k) / 2
                    boiler_ann_y = T_boiler[mid_idx] if s_boiler else (T2c + T3c) / 2
                    fig_rk_ts.add_annotation(
                        x=boiler_ann_x, y=boiler_ann_y,
                        text=f"Q = {conv(Q_boiler,'H'):.0f} {disp_unit('H')}",
                        showarrow=True, arrowhead=5, ax=-40, ay=-40,
                        font=dict(color='#FF3CAC', size=12),
                        bgcolor='rgba(0,0,0,0.65)'
                    )
                    fig_rk_ts.add_annotation(x=(s3k+s4k)/2, y=(T3c+T4c)/2-40, text=f"W = {conv(W_turbine,'H'):.0f} {disp_unit('H')}",
                                              showarrow=True, arrowhead=5, ax=-60, ay=0,
                                              font=dict(color='orange', size=12), bgcolor='rgba(0,0,0,0.65)')
                    fig_rk_ts.add_annotation(x=(s4k+s1k)/2, y=(T4c+T1c)/2, text=f"Q = {conv(Q_condenser,'H'):.0f} {disp_unit('H')}",
                                              showarrow=True, arrowhead=5, ax=0, ay=-30,
                                              font=dict(color='#FF3CAC', size=12), bgcolor='rgba(0,0,0,0.65)')
                    fig_rk_ts.add_annotation(x=(s1k+s2k)/2, y=(T1c+T2c)/2, text=f"W = {conv(W_pump,'H'):.0f} {disp_unit('H')}",
                                              showarrow=True, arrowhead=5, ax=-60, ay=5,
                                              font=dict(color='#39FF14', size=12), bgcolor='rgba(0,0,0,0.65)')
                    if np.isfinite(x_4):
                        fig_rk_ts.add_annotation(
                            x=s4k, y=T4c,
                            text=f"x = {x_4:.3f} | moisture = {(1-x_4)*100:.1f}%",
                            showarrow=True, arrowhead=2, ax=55, ay=15,
                            font=dict(color='#FF3CAC', size=11),
                            bgcolor='rgba(0,0,0,0.65)'
                        )
                    rk_ts_layout = layout_common.copy()
                    rk_ts_layout.update(
                        title='T-s Diagram',
                        uirevision='rankine-ts',
                        xaxis=dict(title=axis_title('Entropy', 'S'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
                        yaxis=dict(title=axis_title('Temperature', 'T'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
                    )
                    fig_rk_ts.update_layout(**rk_ts_layout)
                    fig_rk_ph = go.Figure()
                    if dome is not None:
                        fig_rk_ph.add_trace(go.Scatter(
                            x=dome['hf'], y=dome['P'], mode='lines',
                            line=dict(color=tc()['dome_liq'], width=3), name='Sat Liquid'
                        ))
                        fig_rk_ph.add_trace(go.Scatter(
                            x=dome['hg'], y=dome['P'], mode='lines',
                            line=dict(color=tc()['dome_vap'], width=3), name='Sat Vapor'
                        ))
                    h1k, h2k, h3k, h4k = h_1/1000, h_2/1000, h_3/1000, h_4/1000
                    P_boiler_bar, P_cond_bar = P_boiler/1e5, P_cond/1e5
                    h_u_rk, p_u_rk = disp_unit('H'), disp_unit('P')
                    h1k, h2k, h3k, h4k = conv(h1k,'H'), conv(h2k,'H'), conv(h3k,'H'), conv(h4k,'H')
                    P_boiler_bar, P_cond_bar = conv(P_boiler_bar,'P'), conv(P_cond_bar,'P')
                    fig_rk_ph.add_trace(go.Scatter(
                        x=[h1k, h2k], y=[P_cond_bar, P_boiler_bar], mode='lines',
                        line=dict(color=tc()['pump'], width=3), name='1→2 Pump'
                    ))
                    fig_rk_ph.add_trace(go.Scatter(
                        x=[h2k, h3k], y=[P_boiler_bar, P_boiler_bar], mode='lines',
                        line=dict(color=tc()['state'], width=3), name='2→3 Boiler'
                    ))
                    fig_rk_ph.add_trace(go.Scatter(
                        x=[h3k, h4k], y=[P_boiler_bar, P_cond_bar], mode='lines',
                        line=dict(color=tc()['turbine'], width=3), name='3→4 Turbine'
                    ))
                    fig_rk_ph.add_trace(go.Scatter(
                        x=[h4k, h1k], y=[P_cond_bar, P_cond_bar], mode='lines',
                        line=dict(color=tc()['condenser'], width=3), name='4→1 Condenser'
                    ))
                    fig_rk_ph.add_trace(go.Scatter(
                        x=[h1k, h2k, h3k, h4k],
                        y=[P_cond_bar, P_boiler_bar, P_boiler_bar, P_cond_bar],
                        mode='markers',
                        marker=dict(size=13, color=tc()['marker'], line=dict(color=tc()['marker_line'], width=2)),
                        name='State Points', showlegend=False,
                        hovertemplate=(
                            f"<b>State</b><br>"
                            f"h: %{{x:.2f}} {h_u_rk}<br>"
                            f"P: %{{y:.2f}} {p_u_rk}<extra></extra>"
                        )
                    ))
                    for hx, py, label, ax, ay in [
                        (h1k, P_cond_bar, '1', -18, 18),
                        (h2k, P_boiler_bar, '2', -18, -18),
                        (h3k, P_boiler_bar, '3', 0, -18),
                        (h4k, P_cond_bar, '4', 0, 18),
                    ]:
                        fig_rk_ph.add_annotation(
                            x=hx, y=py, text=label, showarrow=False,
                            xshift=ax, yshift=ay,
                            font=dict(color=tc()['label_text'], size=14)
                        )
                    fig_rk_ph.add_annotation(x=(h2k+h3k)/2, y=P_boiler_bar, text=f"Q = {conv(Q_boiler,'H'):.0f} {disp_unit('H')}",
                                              showarrow=True, arrowhead=5, ax=0, ay=-35,
                                              font=dict(color='yellow', size=12), bgcolor='rgba(0,0,0,0.65)')
                    fig_rk_ph.add_annotation(x=(h3k+h4k)/2, y=(P_boiler_bar*P_cond_bar)**0.5+16, text=f"W = {conv(W_turbine,'H'):.0f} {disp_unit('H')}",
                                              showarrow=True, arrowhead=5, ax=-60, ay=-20,
                                              font=dict(color='orange', size=12), bgcolor='rgba(0,0,0,0.65)')
                    fig_rk_ph.add_annotation(x=(h4k+h1k)/2, y=P_cond_bar, text=f"Q = {conv(Q_condenser,'H'):.0f} {disp_unit('H')}",
                                              showarrow=True, arrowhead=5, ax=0, ay=-40,
                                              font=dict(color='#FF3CAC', size=12), bgcolor='rgba(0,0,0,0.65)')
                    fig_rk_ph.add_annotation(x=(h1k+h2k)/2, y=(P_boiler_bar*P_cond_bar)**0.5+40, text=f"W = {conv(W_pump,'H'):.0f} {disp_unit('H')}",
                                              showarrow=True, arrowhead=5, ax=-60, ay=-15,
                                              font=dict(color='#39FF14', size=12), bgcolor='rgba(0,0,0,0.65)')
                    rk_ph_layout = layout_common.copy()
                    rk_ph_layout.update(
                        title='P-h Diagram',
                        uirevision='rankine-ph',
                        xaxis=dict(title=axis_title('Enthalpy', 'H'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
                        yaxis=dict(title=axis_title('Pressure', 'P'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
                    )
                    fig_rk_ph.update_layout(**rk_ph_layout)
                    rk_plot_col1, rk_plot_col2 = st.columns(2)
                    with rk_plot_col1:
                        st.plotly_chart(fig_rk_ts, use_container_width=True, config=plot_config, key="fig_rk_ts")
                    with rk_plot_col2:
                        st.plotly_chart(fig_rk_ph, use_container_width=True, config=plot_config, key="fig_rk_ph")
                except Exception as e:
                    st.error(f"Could not solve the Rankine cycle for these inputs: {e}")
            st.divider()
            st.subheader("🔥 Reheat")
            reheat_on = st.checkbox(
                "Enable reheat (HP turbine → reheater → LP turbine)", value=False, key="rk_reheat_on"
            )
            if reheat_on and rk_Pcond < rk_Pboiler:
                with st.container(key="igrid_rh1"):
                    rh1, rh2 = st.columns(2)
                with rh1:
                    rk_Preheat = st.slider(
                        "Reheat Pressure (bar)", min_value=float(rk_Pcond * 1.05), max_value=float(rk_Pboiler * 0.95),
                        value=float(min(max(rk_Pboiler * 0.2, rk_Pcond * 1.1), rk_Pboiler * 0.95)),
                        step=0.5, key="rk_Preheat"
                    )
                with rh2:
                    rk_Treheat = unit_number_input(
                        "Reheat Outlet Temperature", "T", min_value=100.0, max_value=800.0,
                        value=float(rk_Tmain), step=5.0, key="rk_Treheat",
                        help="Steam is reheated at constant pressure back up to (typically) close to the boiler inlet temperature."
                    )

                try:
                    P_cond_h = rk_Pcond * 1e5
                    P_boil_h = rk_Pboiler * 1e5
                    P_rh_h = rk_Preheat * 1e5
                    T_main_h = rk_Tmain + 273.15
                    T_rh_h = rk_Treheat + 273.15
                    Tsat1h = cached_propsi('T', 'P', P_boil_h, 'Q', 1, fluid)
                    if T_main_h <= Tsat1h:
                        raise ValueError(f"HP turbine inlet must be superheated (Tsat = {Tsat1h-273.15:.1f} °C at {rk_Pboiler:.1f} bar).")
                    h_1h = cached_propsi('H', 'P', P_boil_h, 'T', T_main_h, fluid)
                    s_1h = cached_propsi('S', 'P', P_boil_h, 'T', T_main_h, fluid)
                    h_2sh = cached_propsi('H', 'P', P_rh_h, 'S', s_1h, fluid)
                    h_2h = h_1h - rk_eta_turb * (h_1h - h_2sh)
                    T_2h = cached_propsi('T', 'P', P_rh_h, 'H', h_2h, fluid)
                    s_2h = cached_propsi('S', 'P', P_rh_h, 'H', h_2h, fluid)
                    Tsat3h = cached_propsi('T', 'P', P_rh_h, 'Q', 1, fluid)
                    if T_rh_h <= Tsat3h:
                        raise ValueError(f"Reheat outlet must be superheated (Tsat = {Tsat3h-273.15:.1f} °C at {rk_Preheat:.1f} bar).")
                    h_3h = cached_propsi('H', 'P', P_rh_h, 'T', T_rh_h, fluid)
                    s_3h = cached_propsi('S', 'P', P_rh_h, 'T', T_rh_h, fluid)
                    h_4sh = cached_propsi('H', 'P', P_cond_h, 'S', s_3h, fluid)
                    h_4h = h_3h - rk_eta_turb * (h_3h - h_4sh)
                    T_4h = cached_propsi('T', 'P', P_cond_h, 'H', h_4h, fluid)
                    s_4h = cached_propsi('S', 'P', P_cond_h, 'H', h_4h, fluid)
                    try:
                        q4h = cached_propsi('Q', 'P', P_cond_h, 'H', h_4h, fluid)
                        phase4h = f"Wet Steam (x={q4h:.3f})" if 0 <= q4h <= 1 else "Superheated Vapor"
                    except Exception:
                        phase4h = "Superheated Vapor"

                    
                    h_5h = cached_propsi('H', 'P', P_cond_h, 'Q', 0, fluid)
                    s_5h = cached_propsi('S', 'P', P_cond_h, 'Q', 0, fluid)
                    T_5h = cached_propsi('T', 'P', P_cond_h, 'Q', 0, fluid)

                    
                    h_6sh = cached_propsi('H', 'P', P_boil_h, 'S', s_5h, fluid)
                    h_6h = h_5h + (h_6sh - h_5h) / rk_eta_pump
                    T_6h = cached_propsi('T', 'P', P_boil_h, 'H', h_6h, fluid)
                    s_6h = cached_propsi('S', 'P', P_boil_h, 'H', h_6h, fluid)

                    W_turb_h = (h_1h - h_2h) + (h_3h - h_4h)
                    W_pump_h = h_6h - h_5h
                    Q_boiler_h = (h_1h - h_6h) + (h_3h - h_2h)
                    Q_cond_h = h_4h - h_5h
                    W_net_h = W_turb_h - W_pump_h
                    eta_th_h = W_net_h / Q_boiler_h if Q_boiler_h > 0 else np.nan

                    rhres1, rhres2 = st.columns([1.25, 1])
                    with rhres1:
                        rows_h = [
                            ["1 – HP Turbine Inlet", fmt(conv(P_boil_h/1e5,'P'), 2), fmt(conv(T_main_h-273.15,'T'), 2), fmt(conv(h_1h/1000,'H'), 2), fmt(conv(s_1h/1000,'S'), 4), "Superheated Vapor"],
                            ["2 – HP Turbine Exit / Reheat In", fmt(conv(P_rh_h/1e5,'P'), 2), fmt(conv(T_2h-273.15,'T'), 2), fmt(conv(h_2h/1000,'H'), 2), fmt(conv(s_2h/1000,'S'), 4), "Vapor / Wet Steam"],
                            ["3 – LP Turbine Inlet (Reheated)", fmt(conv(P_rh_h/1e5,'P'), 2), fmt(conv(T_rh_h-273.15,'T'), 2), fmt(conv(h_3h/1000,'H'), 2), fmt(conv(s_3h/1000,'S'), 4), "Superheated Vapor"],
                            ["4 – LP Turbine Exit / Cond. In", fmt(conv(P_cond_h/1e5,'P'), 3), fmt(conv(T_4h-273.15,'T'), 2), fmt(conv(h_4h/1000,'H'), 2), fmt(conv(s_4h/1000,'S'), 4), phase4h],
                            ["5 – Condenser Exit", fmt(conv(P_cond_h/1e5,'P'), 3), fmt(conv(T_5h-273.15,'T'), 2), fmt(conv(h_5h/1000,'H'), 2), fmt(conv(s_5h/1000,'S'), 4), "Sat. Liquid"],
                            ["6 – Pump Exit / Boiler In", fmt(conv(P_boil_h/1e5,'P'), 2), fmt(conv(T_6h-273.15,'T'), 2), fmt(conv(h_6h/1000,'H'), 2), fmt(conv(s_6h/1000,'S'), 4), "Subcooled Liquid"],
                        ]
                        df_h = pd.DataFrame(rows_h, columns=["State", f"P ({disp_unit('P')})", f"T ({disp_unit('T')})", f"h ({disp_unit('H')})", f"s ({disp_unit('S')})", "Phase"])
                        show_state_table(df_h)

                    with rhres2:
                        delta_eta_h = (eta_th_h - eta_th) * 100 if is_valid_number(eta_th) else np.nan
                        st.markdown(f"""
                        <div class="info-box">
                        Turbine Work = {W_turb_h/1000:.1f} kJ/kg<br>
                        Pump Work = {W_pump_h/1000:.1f} kJ/kg<br>
                        Heat Added (Boiler + Reheat) = {Q_boiler_h/1000:.1f} kJ/kg<br>
                        Heat Rejected (Condenser) = {Q_cond_h/1000:.1f} kJ/kg<br>
                        <hr style="border-color:#333;">
                        Net Work = {W_net_h/1000:.1f} kJ/kg<br>
                        <b>Thermal Efficiency = {eta_th_h*100:.2f}%</b><br>
                        {"Δ vs non-reheat = " + format(delta_eta_h, "+.2f") + " pts" if is_valid_number(delta_eta_h) else ""}
                        </div>
                        """, unsafe_allow_html=True)

                    
                    fig_rh = go.Figure()
                    if dome is not None:
                        fig_rh.add_trace(go.Scatter(x=conv(np.array(dome['sf']),'S'), y=conv(np.array(dome['T']),'T'), mode='lines',
                                                     line=dict(color=tc()['dome_liq'], width=3), name='Sat Liquid'))
                        fig_rh.add_trace(go.Scatter(x=conv(np.array(dome['sg']),'S'), y=conv(np.array(dome['T']),'T'), mode='lines',
                                                     line=dict(color=tc()['dome_vap'], width=3), name='Sat Vapor'))

                    s_u_rh, t_u_rh = disp_unit('S'), disp_unit('T')
                    pts = [(conv(s_5h/1000,'S'), conv(T_5h-273.15,'T'), '5'), (conv(s_6h/1000,'S'), conv(T_6h-273.15,'T'), '6'),
                           (conv(s_1h/1000,'S'), conv(T_main_h-273.15,'T'), '1'), (conv(s_2h/1000,'S'), conv(T_2h-273.15,'T'), '2'),
                           (conv(s_3h/1000,'S'), conv(T_rh_h-273.15,'T'), '3'), (conv(s_4h/1000,'S'), conv(T_4h-273.15,'T'), '4')]
                    seg_colors = [
                        (tc()['pump'], '5→6 Pump'), (tc()['boiler'], '6→1 Boiler'), (tc()['turbine'], '1→2 HP Turbine'),
                        (tc()['reheat'], '2→3 Reheat'), (tc()['turbine'], '3→4 LP Turbine'), (tc()['condenser'], '4→5 Condenser')
                    ]
                    isobar_legs = {
                        1: (P_boil_h, T_6h, T_main_h),   
                    }
                    for i in range(len(pts)):
                        s0, T0, _ = pts[i]
                        s1p, T1p, _ = pts[(i + 1) % len(pts)]
                        color, name = seg_colors[i]

                        if i in isobar_legs:
                            P_leg, T_start_leg, T_end_leg = isobar_legs[i]
                            s_leg, T_leg, _ = build_isobar_path(P_leg, T_start_leg, T_end_leg, fluid)
                            if s_leg:
                                s_leg = [conv(v, 'S') for v in s_leg]
                                T_leg = [conv(v, 'T') for v in T_leg]
                                
                                
                                s_leg[0], T_leg[0] = s0, T0
                                s_leg[-1], T_leg[-1] = s1p, T1p
                                fig_rh.add_trace(go.Scatter(x=s_leg, y=T_leg,
                                                             mode='lines', line=dict(color=color, width=3), name=name))
                                continue

                        fig_rh.add_trace(go.Scatter(x=[s0, s1p], y=[T0, T1p],
                                                     mode='lines', line=dict(color=color, width=3), name=name))

                    fig_rh.add_trace(go.Scatter(
                        x=[p[0] for p in pts], y=[p[1] for p in pts],
                        mode='markers+text', marker=dict(size=12, color=tc()['marker'], line=dict(color=tc()['marker_line'], width=1.5)),
                        text=[p[2] for p in pts], textposition='top center', textfont=dict(color=tc()['label_text'], size=13), showlegend=False,
                        hovertemplate=f"s: %{{x:.4f}} {s_u_rh}<br>T: %{{y:.1f}} {t_u_rh}<extra></extra>"
                    ))

                    rh_layout = layout_common.copy()
                    rh_layout.update(
                        title='Reheat Rankine Cycle — T-s Diagram',
                        uirevision='rankine-reheat-ts',
                        xaxis=dict(title=axis_title('Entropy', 'S'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
                        yaxis=dict(title=axis_title('Temperature', 'T'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
                    )
                    fig_rh.update_layout(**rh_layout)
                    st.plotly_chart(fig_rh, use_container_width=True, config=plot_config, key="fig_rh")

                except Exception as e:
                    st.error(f"Could not solve the reheat Rankine cycle: {e}")
            elif reheat_on:
                st.warning("Condenser pressure must be lower than boiler pressure to enable reheat.")
            st.divider()
            st.subheader("🔁 Regeneration")

            regen_mode = st.radio(
                "How many times do you want to regenerate?",
                ["No regeneration (normal cycle)", "1 Feedwater Heater", "2 Feedwater Heaters", "3 Feedwater Heaters"],
                index=0, horizontal=True, key="rk_regen_mode"
            )
            N_fwh = {"No regeneration (normal cycle)": 0, "1 Feedwater Heater": 1,
                     "2 Feedwater Heaters": 2, "3 Feedwater Heaters": 3}[regen_mode]

            if N_fwh == 0:
                st.caption("Regeneration is off — the ideal/practical cycle above is the one in effect.")
            elif rk_Pcond >= rk_Pboiler:
                st.warning("Condenser pressure must be lower than boiler pressure to enable regeneration.")
            else:
                try:
                    P_cond_r = rk_Pcond * 1e5
                    P_boil_r = rk_Pboiler * 1e5
                    T_main_r = rk_Tmain + 273.15
                    N = N_fwh

                    
                    P_stages = [P_cond_r * (P_boil_r / P_cond_r) ** (k / (N + 1)) for k in range(1, N + 1)]

                    
                    Tsat_in = cached_propsi('T', 'P', P_boil_r, 'Q', 1, fluid)
                    if T_main_r <= Tsat_in:
                        raise ValueError(
                            f"Turbine inlet must be superheated. At {rk_Pboiler:.1f} bar, saturation "
                            f"temperature is {Tsat_in - 273.15:.1f} °C. Increase the turbine inlet temperature."
                        )
                    h_in = cached_propsi('H', 'P', P_boil_r, 'T', T_main_r, fluid)
                    s_in = cached_propsi('S', 'P', P_boil_r, 'T', T_main_r, fluid)

                    
                    expansion_pressures = list(reversed(P_stages)) + [P_cond_r]
                    turbine_states = []
                    h_prev, s_prev = h_in, s_in
                    for Pext in expansion_pressures:
                        h_s = cached_propsi('H', 'P', Pext, 'S', s_prev, fluid)
                        h_act = h_prev - rk_eta_turb * (h_prev - h_s)
                        T_act = cached_propsi('T', 'P', Pext, 'H', h_act, fluid)
                        s_act = cached_propsi('S', 'P', Pext, 'H', h_act, fluid)
                        turbine_states.append(dict(P=Pext, h=h_act, T=T_act, s=s_act))
                        h_prev, s_prev = h_act, s_act

                    
                    y_list = [None] * N          
                    T_cum = 0.0
                    for idx in range(N - 1, -1, -1):
                        P_k = P_stages[idx]
                        h_extract_k = turbine_states[N - 1 - idx]['h']
                        h_satliq_k = cached_propsi('H', 'P', P_k, 'Q', 0, fluid)

                        P_prev = P_stages[idx - 1] if idx > 0 else P_cond_r
                        h_prev_satliq = cached_propsi('H', 'P', P_prev, 'Q', 0, fluid)
                        s_prev_satliq = cached_propsi('S', 'P', P_prev, 'Q', 0, fluid)
                        h_pump_s = cached_propsi('H', 'P', P_k, 'S', s_prev_satliq, fluid)
                        h_k_in = h_prev_satliq + (h_pump_s - h_prev_satliq) / rk_eta_pump

                        y_k = (1 - T_cum) * (h_satliq_k - h_k_in) / (h_extract_k - h_k_in)
                        y_list[idx] = y_k
                        T_cum += y_k

                    y_total = sum(y_list)
                    if not (0.0 < y_total < 1.0) or any(y <= 0 for y in y_list):
                        raise ValueError(
                            f"Extraction fractions are outside a physical range (y_total={y_total:.3f}). "
                            "Try a lower turbine inlet temperature / different pressures."
                        )

                    
                    h_top_satliq = cached_propsi('H', 'P', P_stages[-1], 'Q', 0, fluid)
                    s_top_satliq = cached_propsi('S', 'P', P_stages[-1], 'Q', 0, fluid)
                    h_boiler_in_s = cached_propsi('H', 'P', P_boil_r, 'S', s_top_satliq, fluid)
                    h_boiler_in = h_top_satliq + (h_boiler_in_s - h_top_satliq) / rk_eta_pump

                    Q_boiler_r = h_in - h_boiler_in

                    
                    flow = 1.0
                    W_turb_r = (h_in - turbine_states[0]['h']) * flow
                    for i in range(N):
                        flow -= y_list[N - 1 - i]
                        W_turb_r += (turbine_states[i]['h'] - turbine_states[i + 1]['h']) * flow
                    flow_to_condenser = flow  

                    
                    h_cond_satliq = cached_propsi('H', 'P', P_cond_r, 'Q', 0, fluid)
                    s_cond_satliq = cached_propsi('S', 'P', P_cond_r, 'Q', 0, fluid)
                    h_pump0_s = cached_propsi('H', 'P', P_stages[0], 'S', s_cond_satliq, fluid)
                    h_pump0 = h_cond_satliq + (h_pump0_s - h_cond_satliq) / rk_eta_pump
                    W_pump_r = (h_pump0 - h_cond_satliq) * flow_to_condenser

                    flow_after_fwh = [1 - sum(y_list[k + 1:]) for k in range(N)]
                    intermediate_pump_h = {}
                    for k in range(N - 1):
                        Pk, Pk1 = P_stages[k], P_stages[k + 1]
                        h_k_satliq = cached_propsi('H', 'P', Pk, 'Q', 0, fluid)
                        s_k_satliq = cached_propsi('S', 'P', Pk, 'Q', 0, fluid)
                        h_kp_s = cached_propsi('H', 'P', Pk1, 'S', s_k_satliq, fluid)
                        h_kp = h_k_satliq + (h_kp_s - h_k_satliq) / rk_eta_pump
                        intermediate_pump_h[k] = h_kp
                        W_pump_r += (h_kp - h_k_satliq) * flow_after_fwh[k]

                    W_pump_r += (h_boiler_in - h_top_satliq) * 1.0

                    W_net_r = W_turb_r - W_pump_r
                    eta_th_r = W_net_r / Q_boiler_r if Q_boiler_r > 0 else np.nan
                    Q_cond_r = flow_to_condenser * (turbine_states[-1]['h'] - h_cond_satliq)

                    rgres1, rgres2 = st.columns([1.35, 1])
                    with rgres1:
                        rows = [["1 – Condenser Exit", fmt(conv(P_cond_r / 1e5, 'P'), 3),
                                 fmt(conv(cached_propsi('T', 'P', P_cond_r, 'Q', 0, fluid) - 273.15, 'T'), 2),
                                 fmt(conv(h_cond_satliq / 1000, 'H'), 2), fmt(conv(s_cond_satliq / 1000, 'S'), 4), "Sat. Liquid"]]
                        rows.append(["2 – Pump I Exit / FWH1 In", fmt(conv(P_stages[0] / 1e5, 'P'), 3),
                                     fmt(conv(cached_propsi('T', 'P', P_stages[0], 'H', h_pump0, fluid) - 273.15, 'T'), 2),
                                     fmt(conv(h_pump0 / 1000, 'H'), 2), "-", "Subcooled Liquid"])
                        for k in range(N):
                            Pk = P_stages[k]
                            Tk = cached_propsi('T', 'P', Pk, 'Q', 0, fluid) - 273.15
                            hk = cached_propsi('H', 'P', Pk, 'Q', 0, fluid) / 1000
                            sk = cached_propsi('S', 'P', Pk, 'Q', 0, fluid) / 1000
                            rows.append([f"FWH{k+1} Exit (sat. liquid)", fmt(conv(Pk / 1e5, 'P'), 3), fmt(conv(Tk, 'T'), 2), fmt(conv(hk, 'H'), 2), fmt(conv(sk, 'S'), 4), "Sat. Liquid"])
                            if k < N - 1:
                                hkp = intermediate_pump_h[k] / 1000
                                Tkp = cached_propsi('T', 'P', P_stages[k + 1], 'H', intermediate_pump_h[k], fluid) - 273.15
                                rows.append([f"Pump {k+2} Exit / FWH{k+2} In", fmt(conv(P_stages[k+1]/1e5, 'P'), 3), fmt(conv(Tkp, 'T'), 2), fmt(conv(hkp, 'H'), 2), "-", "Subcooled Liquid"])
                        rows.append(["Feed Pump Exit / Boiler In", fmt(conv(P_boil_r / 1e5, 'P'), 2),
                                     fmt(conv(cached_propsi('T', 'P', P_boil_r, 'H', h_boiler_in, fluid) - 273.15, 'T'), 2),
                                     fmt(conv(h_boiler_in / 1000, 'H'), 2), "-", "Subcooled Liquid"])
                        rows.append(["Turbine Inlet", fmt(conv(P_boil_r / 1e5, 'P'), 2), fmt(conv(T_main_r - 273.15, 'T'), 2),
                                     fmt(conv(h_in / 1000, 'H'), 2), fmt(conv(s_in / 1000, 'S'), 4), "Superheated Vapor"])
                        for i in range(N):
                            ts = turbine_states[i]
                            rows.append([f"Extraction {N - i} (y = {y_list[N-1-i]:.4f})", fmt(conv(ts['P'] / 1e5, 'P'), 3),
                                         fmt(conv(ts['T'] - 273.15, 'T'), 2), fmt(conv(ts['h'] / 1000, 'H'), 2), fmt(conv(ts['s'] / 1000, 'S'), 4), "Vapor / Wet Steam"])
                        ts_exit = turbine_states[-1]
                        try:
                            q_exit = cached_propsi('Q', 'P', P_cond_r, 'H', ts_exit['h'], fluid)
                            phase_exit = f"Wet Steam (x={q_exit:.3f})" if 0 <= q_exit <= 1 else "Superheated Vapor"
                        except Exception:
                            phase_exit = "Superheated Vapor"
                        rows.append(["Turbine Exit / Condenser In", fmt(conv(P_cond_r / 1e5, 'P'), 3), fmt(conv(ts_exit['T'] - 273.15, 'T'), 2),
                                     fmt(conv(ts_exit['h'] / 1000, 'H'), 2), fmt(conv(ts_exit['s'] / 1000, 'S'), 4), phase_exit])

                        df_rg = pd.DataFrame(rows, columns=["State", f"P ({disp_unit('P')})", f"T ({disp_unit('T')})", f"h ({disp_unit('H')})", f"s ({disp_unit('S')})", "Phase"])
                        show_state_table(df_rg)

                    with rgres2:
                        delta_eta = (eta_th_r - eta_th) * 100 if is_valid_number(eta_th) else np.nan
                        y_str = " + ".join(f"y{k+1}={y_list[k]:.4f}" for k in range(N))
                        st.markdown(f"""
                        <div class="info-box">
                        {y_str}<br>Total Extracted = {y_total:.4f}<br>
                        Turbine Work = {W_turb_r/1000:.1f} kJ/kg<br>
                        Pump Work = {W_pump_r/1000:.1f} kJ/kg<br>
                        Heat Added (Boiler) = {Q_boiler_r/1000:.1f} kJ/kg<br>
                        Heat Rejected (Condenser) = {Q_cond_r/1000:.1f} kJ/kg<br>
                        <hr style="border-color:#333;">
                        Net Work = {W_net_r/1000:.1f} kJ/kg<br>
                        <b>Thermal Efficiency = {eta_th_r*100:.2f}%</b><br>
                        {"Δ vs non-regenerative = " + format(delta_eta, "+.2f") + " pts" if is_valid_number(delta_eta) else ""}
                        </div>
                        """, unsafe_allow_html=True)
                    fig_rg = go.Figure()

                    if dome is not None:
                        fig_rg.add_trace(go.Scatter(x=conv(np.array(dome['sf']),'S'), y=conv(np.array(dome['T']),'T'), mode='lines',
                                                     line=dict(color=tc()['dome_liq'], width=3), name='Sat Liquid'))
                        fig_rg.add_trace(go.Scatter(x=conv(np.array(dome['sg']),'S'), y=conv(np.array(dome['T']),'T'), mode='lines',
                                                     line=dict(color=tc()['dome_vap'], width=3), name='Sat Vapor'))

                    
                    Tsat_boiler = cached_propsi('T', 'P', P_boil_r, 'Q', 0, fluid) - 273.15
                    s_satliq_boiler = cached_propsi('S', 'P', P_boil_r, 'Q', 0, fluid) / 1000
                    s_satvap_boiler = cached_propsi('S', 'P', P_boil_r, 'Q', 1, fluid) / 1000
                    T_boilerin = cached_propsi('T', 'P', P_boil_r, 'H', h_boiler_in, fluid) - 273.15
                    s_boilerin = cached_propsi('S', 'P', P_boil_r, 'H', h_boiler_in, fluid) / 1000
                    boiler_s = [s_boilerin, s_satliq_boiler, s_satvap_boiler, s_in / 1000]
                    boiler_T = [T_boilerin, Tsat_boiler, Tsat_boiler, T_main_r - 273.15]
                    fig_rg.add_trace(go.Scatter(x=boiler_s, y=boiler_T, mode='lines',
                                                 line=dict(color=tc()['boiler'], width=4), name='Boiler (Preheat + Boil + Superheat)'))

                    
                    red_s, red_T, red_lbl = [], [], []
                    red_s.append(s_cond_satliq / 1000); red_T.append(cached_propsi('T', 'P', P_cond_r, 'Q', 0, fluid) - 273.15); red_lbl.append('1')
                    red_s.append(cached_propsi('S', 'P', P_stages[0], 'H', h_pump0, fluid) / 1000); red_T.append(cached_propsi('T', 'P', P_stages[0], 'H', h_pump0, fluid) - 273.15); red_lbl.append('2')

                    lbl_n = 3
                    fwh_label_positions = []
                    for k in range(N):
                        Pk = P_stages[k]
                        red_s.append(cached_propsi('S', 'P', Pk, 'Q', 0, fluid) / 1000)
                        red_T.append(cached_propsi('T', 'P', Pk, 'Q', 0, fluid) - 273.15)
                        red_lbl.append(str(lbl_n)); fwh_label_positions.append(len(red_s) - 1)
                        lbl_n += 1
                        if k < N - 1:
                            red_s.append(cached_propsi('S', 'P', P_stages[k+1], 'H', intermediate_pump_h[k], fluid) / 1000)
                            red_T.append(cached_propsi('T', 'P', P_stages[k+1], 'H', intermediate_pump_h[k], fluid) - 273.15)
                            red_lbl.append(str(lbl_n)); lbl_n += 1

                    red_s.append(s_boilerin); red_T.append(T_boilerin); red_lbl.append(str(lbl_n)); lbl_n += 1
                    red_s.append(s_in / 1000); red_T.append(T_main_r - 273.15); red_lbl.append(str(lbl_n)); lbl_n += 1
                    turbine_inlet_idx = len(red_s) - 1

                    extraction_idx = []
                    for i in range(N):
                        ts = turbine_states[i]
                        red_s.append(ts['s'] / 1000); red_T.append(ts['T'] - 273.15)
                        red_lbl.append(str(lbl_n)); extraction_idx.append(len(red_s) - 1); lbl_n += 1

                    red_s.append(ts_exit['s'] / 1000); red_T.append(ts_exit['T'] - 273.15)
                    red_lbl.append(str(lbl_n)); condenser_in_idx = len(red_s) - 1

                    
                    s_u_rg, t_u_rg = disp_unit('S'), disp_unit('T')
                    red_s = [conv(v, 'S') for v in red_s]
                    red_T = [conv(v, 'T') for v in red_T]
                    boiler_s = [conv(v, 'S') for v in boiler_s]
                    boiler_T = [conv(v, 'T') for v in boiler_T]
                    Tsat_boiler = conv(Tsat_boiler, 'T')

                    
                    main_path_idx = [0, 1] + [2 + 2*k if k == 0 else 2 + 2*k for k in range(0, 1)]
                    fig_rg.add_trace(go.Scatter(x=[red_s[0], red_s[1]], y=[red_T[0], red_T[1]],
                                                 mode='lines', line=dict(color=tc()['pump'], width=3), name='Pump I', showlegend=False))
                    for k in range(N):
                        idx_fwh = fwh_label_positions[k]
                        prev_idx = 1 if k == 0 else fwh_label_positions[k-1] + 1
                        fig_rg.add_trace(go.Scatter(x=[red_s[prev_idx], red_s[idx_fwh]], y=[red_T[prev_idx], red_T[idx_fwh]],
                                                     mode='lines', line=dict(color=tc()['fwh'], width=3, dash='dot'),
                                                     name=f'FWH{k+1} Mixing', showlegend=False))
                        if k < N - 1:
                            fig_rg.add_trace(go.Scatter(x=[red_s[idx_fwh], red_s[idx_fwh+1]], y=[red_T[idx_fwh], red_T[idx_fwh+1]],
                                                         mode='lines', line=dict(color=tc()['pump'], width=3), name=f'Pump {k+2}', showlegend=False))
                    fig_rg.add_trace(go.Scatter(x=[red_s[fwh_label_positions[-1] if N > 0 else 1], boiler_s[0]],
                                                 y=[red_T[fwh_label_positions[-1] if N > 0 else 1], boiler_T[0]],
                                                 mode='lines', line=dict(color=tc()['pump'], width=3), name='Feed Pump', showlegend=False))

                    turbine_path_x = [red_s[turbine_inlet_idx]] + [red_s[i] for i in extraction_idx] + [red_s[condenser_in_idx]]
                    turbine_path_y = [red_T[turbine_inlet_idx]] + [red_T[i] for i in extraction_idx] + [red_T[condenser_in_idx]]
                    fig_rg.add_trace(go.Scatter(x=turbine_path_x, y=turbine_path_y, mode='lines',
                                                 line=dict(color=tc()['turbine'], width=3), name='Turbine Expansion'))

                    fig_rg.add_trace(go.Scatter(x=[red_s[condenser_in_idx], red_s[0]], y=[red_T[condenser_in_idx], red_T[0]],
                                                 mode='lines', line=dict(color=tc()['condenser'], width=3, dash='dash'), name='Condenser'))

                    for i, idx_e in enumerate(extraction_idx):
                        idx_fwh = fwh_label_positions[N - 1 - i]
                        fig_rg.add_trace(go.Scatter(x=[red_s[idx_e], red_s[idx_fwh]], y=[red_T[idx_e], red_T[idx_fwh]],
                                                     mode='lines', line=dict(color=tc()['extraction'], width=2, dash='dot'),
                                                     name=f'Extraction {N-i} → FWH{N-i}', showlegend=(i == 0)))

                    fig_rg.add_trace(go.Scatter(x=red_s, y=red_T, mode='markers+text',
                                                 marker=dict(size=11, color=tc()['marker'], line=dict(color=tc()['marker_line'], width=1.2)),
                                                 text=red_lbl, textposition='top center', textfont=dict(color=tc()['label_text'], size=13),
                                                 showlegend=False, hovertemplate=f"s: %{{x:.4f}} {s_u_rg}<br>T: %{{y:.1f}} {t_u_rg}<extra></extra>"))

                    
                    y_label = "y" if N == 1 else "Σy = " + f"{y_total:.3f}"
                    fig_rg.add_annotation(x=(red_s[0] + red_s[fwh_label_positions[0]]) / 2 if N > 0 else red_s[0],
                                           y=(min(red_T) + Tsat_boiler) / 2,
                                           text=y_label, showarrow=False, font=dict(color=tc()['label_text'], size=15))
                    fig_rg.add_annotation(x=(red_s[condenser_in_idx] + red_s[0]) / 2,
                                           y=min(red_T) - 8,
                                           text=f"1-y = {1-y_total:.3f}", showarrow=False,
                                           font=dict(color=tc()['label_text'], size=15))

                    rg_layout = layout_common.copy()
                    rg_layout.update(
                        title=f'Regenerative Rankine Cycle — {N} Feedwater Heater{"s" if N != 1 else ""} — T-s Diagram',
                        uirevision='rankine-regen-ts',
                        xaxis=dict(title=axis_title('Entropy', 'S'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
                        yaxis=dict(title=axis_title('Temperature', 'T'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
                    )
                    fig_rg.update_layout(**rg_layout)
                    st.plotly_chart(fig_rg, use_container_width=True, config=plot_config, key="fig_rg")

                except Exception as e:
                    st.error(f"Could not solve the regenerative Rankine cycle: {e}")
    with cycle_tab2:
        st.subheader("Brayton Cycle — Open-Cycle Gas Turbine")

        
        with st.container(key="igrid_br1"):
            bc1, bc2 = st.columns(2)
        with bc1:
            br_Pamb = unit_number_input(
                "Ambient Pressure", "P", min_value=0.5, max_value=2.0,
                value=1.013, step=0.001, format="%.3f", key="br_Pamb_ind"
            )
        with bc2:
            br_Tamb = unit_number_input(
                "Ambient / Compressor Inlet Temp", "T", min_value=-60.0, max_value=80.0,
                value=15.0, step=1.0, key="br_Tamb_ind"
            )

        with st.container(key="igrid_br2"):
            bc3, bc4 = st.columns(2)
        with bc3:
            br_PR = st.number_input(
                "Compressor Pressure Ratio", min_value=2.0, max_value=50.0,
                value=15.0, step=0.5, key="br_PR_ind",
                help="P2/P1. Modern gas turbines commonly operate at substantial pressure ratios."
            )
        with bc4:
            br_TIT = unit_number_input(
                "Turbine Inlet Temperature / TIT", "T", min_value=700.0, max_value=1800.0,
                value=1350.0, step=10.0, key="br_TIT_ind",
                help="Hot-gas turbine inlet temperature after the combustor."
            )

        with st.container(key="igrid_br3"):
            bc5, bc6 = st.columns(2)
        with bc5:
            br_dP_comb = st.slider(
                "Combustor Pressure Loss (%)", 0.0, 12.0, 4.0, 0.5,
                key="br_dP_comb_ind"
            )
        with bc6:
            br_dP_intake = st.slider(
                "Inlet / Filter Pressure Loss (%)", 0.0, 5.0, 1.0, 0.1,
                key="br_dP_intake_ind"
            )

        with st.container(key="igrid_br4"):
            bc7, bc8 = st.columns(2)
        with bc7:
            br_Pexh = unit_number_input(
                "Exhaust Back Pressure (above ambient)", "P", min_value=0.0, max_value=1.0,
                value=0.05, step=0.01, key="br_Pexh_ind"
            )
        with bc8:
            br_eta_comp = st.slider(
                "Compressor Isentropic Efficiency", 0.70, 0.95, 0.88, 0.01,
                key="br_eta_comp_ind"
            )

        with st.container(key="igrid_br5"):
            bc9, bc10 = st.columns(2)
        with bc9:
            br_eta_turb = st.slider(
                "Turbine Isentropic Efficiency", 0.80, 0.98, 0.90, 0.01,
                key="br_eta_turb_ind"
            )
        with bc10:
            br_eta_mech = st.slider(
                "Mechanical / Shaft Efficiency", 0.90, 0.99, 0.98, 0.005,
                key="br_eta_mech_ind"
            )

        with st.container(key="igrid_br6"):
            bc11, bc12 = st.columns(2)
        with bc11:
            br_eta_gen = st.slider(
                "Generator Efficiency", 0.90, 0.99, 0.97, 0.005,
                key="br_eta_gen_ind"
            )

        st.info(
            "1→2 compression, 2→3 combustion/heat addition "
            "with combustor pressure loss, 3→4 turbine expansion, 4→1 exhaust/heat rejection. "
        )

        try:
            AIR = "Air"

            P_amb = br_Pamb * 1e5
            P1b = P_amb * (1.0 - br_dP_intake / 100.0)
            P2b = P1b * br_PR
            P3b = P2b * (1.0 - br_dP_comb / 100.0)
            P4b = P_amb + br_Pexh * 1e5
            T1b = br_Tamb + 273.15
            T3b = br_TIT + 273.15

            if P2b <= P3b or P3b <= P4b:
                raise ValueError(
                    "Invalid pressure configuration: turbine inlet pressure must be "
                    "higher than exhaust pressure."
                )
            h1b = cached_propsi("H", "P", P1b, "T", T1b, AIR)
            s1b = cached_propsi("S", "P", P1b, "T", T1b, AIR)
            h2sb = cached_propsi("H", "P", P2b, "S", s1b, AIR)
            h2b = h1b + (h2sb - h1b) / br_eta_comp
            T2b = cached_propsi("T", "P", P2b, "H", h2b, AIR)
            s2b = cached_propsi("S", "P", P2b, "H", h2b, AIR)
            h3b = cached_propsi("H", "P", P3b, "T", T3b, AIR)
            s3b = cached_propsi("S", "P", P3b, "T", T3b, AIR)
            h4sb = cached_propsi("H", "P", P4b, "S", s3b, AIR)
            h4b = h3b - br_eta_turb * (h3b - h4sb)
            T4b = cached_propsi("T", "P", P4b, "H", h4b, AIR)
            s4b = cached_propsi("S", "P", P4b, "H", h4b, AIR)

            
            phases_ok = True
            phase_names = []
            for Pchk, Tchk in [(P1b, T1b), (P2b, T2b), (P3b, T3b), (P4b, T4b)]:
                ph = PhaseSI("P", Pchk, "T", Tchk, AIR)
                phase_names.append(ph)
                ph_low = ph.lower()
                if "gas" not in ph_low and "supercritical" not in ph_low:
                    phases_ok = False

            if not phases_ok:
                raise ValueError(
                    "A Brayton gas-turbine state left the gas/supercritical region. "
                    "Check the pressure ratio, ambient condition and temperatures."
                )
            W_compb = (h2b - h1b) / 1000.0
            W_turbb = (h3b - h4b) / 1000.0
            Q_inb = (h3b - h2b) / 1000.0
            Q_outb = (h4b - h1b) / 1000.0

            W_net_gross = W_turbb - W_compb
            W_net_shaft = W_net_gross * br_eta_mech
            W_electric = W_net_shaft * br_eta_gen
            eta_thb = W_electric / Q_inb if Q_inb > 0 else np.nan
            bwrb = W_compb / W_turbb if W_turbb > 0 else np.nan
            heat_rate = 3600.0 / eta_thb if eta_thb > 0 else np.nan
            bres1, bres2 = st.columns([1.25, 1])

            with bres1:
                p_ub, t_ub, h_ub, s_ub = disp_unit('P'), disp_unit('T'), disp_unit('H'), disp_unit('S')
                state_rows_b = [
                    ["1 — Compressor Inlet", conv(P1b/1e5,'P'), conv(T1b-273.15,'T'), conv(h1b/1000,'H'), conv(s1b/1000,'S'), "Gas"],
                    ["2s — Ideal Compressor Exit", conv(P2b/1e5,'P'), conv(cached_propsi("T","P",P2b,"H",h2sb,AIR)-273.15,'T'), conv(h2sb/1000,'H'), conv(s1b/1000,'S'), "Gas"],
                    ["2 — Actual Compressor Exit", conv(P2b/1e5,'P'), conv(T2b-273.15,'T'), conv(h2b/1000,'H'), conv(s2b/1000,'S'), "Gas"],
                    ["3 — Turbine Inlet / TIT", conv(P3b/1e5,'P'), conv(T3b-273.15,'T'), conv(h3b/1000,'H'), conv(s3b/1000,'S'), "Gas"],
                    ["4s — Ideal Turbine Exit", conv(P4b/1e5,'P'), conv(cached_propsi("T","P",P4b,"H",h4sb,AIR)-273.15,'T'), conv(h4sb/1000,'H'), conv(s3b/1000,'S'), "Gas"],
                    ["4 — Actual Turbine Exit", conv(P4b/1e5,'P'), conv(T4b-273.15,'T'), conv(h4b/1000,'H'), conv(s4b/1000,'S'), "Gas"],
                ]
                df_br = pd.DataFrame(
                    state_rows_b,
                    columns=["State", f"P ({p_ub})", f"T ({t_ub})", f"h ({h_ub})", f"s ({s_ub})", "Phase"]
                )
                show_state_table(
                    df_br.style.format({
                        f"P ({p_ub})": "{:.3f}",
                        f"T ({t_ub})": "{:.2f}",
                        f"h ({h_ub})": "{:.2f}",
                        f"s ({s_ub})": "{:.4f}"
                    })
                )

            with bres2:
                st.markdown(f"""
                <div class="info-box">
                Compressor Work = {W_compb:.1f} kJ/kg<br>
                Turbine Work = {W_turbb:.1f} kJ/kg<br>
                Gross Net Work = {W_net_gross:.1f} kJ/kg<br>
                Electric Net Work = {W_electric:.1f} kJ/kg<br>
                Heat Added = {Q_inb:.1f} kJ/kg<br>
                Heat Rejected = {Q_outb:.1f} kJ/kg<br>
                <hr style="border-color:#333;">
                <b>Electrical Thermal Efficiency = {eta_thb*100:.2f}%</b><br>
                Back Work Ratio = {bwrb:.4f}<br>
                Heat Rate = {heat_rate:.1f} kJ/kWh
                </div>
                """, unsafe_allow_html=True)

                st.caption(
                    f"Pressure ratio = {br_PR:.2f} | "
                    f"P₂ = {P2b/1e5:.2f} bar | P₃ = {P3b/1e5:.2f} bar | "
                    f"P₄ = {P4b/1e5:.2f} bar"
                )
            fig_br = go.Figure()

            s_u_br, t_u_br, h_u_br = disp_unit('S'), disp_unit('T'), disp_unit('H')
            s1k, s2k, s3k, s4k = conv(s1b/1000,'S'), conv(s2b/1000,'S'), conv(s3b/1000,'S'), conv(s4b/1000,'S')
            T1k, T2k, T3k, T4k = conv(T1b-273.15,'T'), conv(T2b-273.15,'T'), conv(T3b-273.15,'T'), conv(T4b-273.15,'T')

            cycle_s = [s1k, s2k, s3k, s4k, s1k]
            cycle_T = [T1k, T2k, T3k, T4k, T1k]

            fig_br.add_trace(go.Scatter(
                x=cycle_s, y=cycle_T,
                mode="lines+markers+text",
                line=dict(color=tc()['turbine'], width=4),
                marker=dict(size=12, color=tc()['state'], line=dict(color=tc()['marker_line'], width=1.5)),
                text=["1", "2", "3", "4", ""],
                textposition="top center",
                textfont=dict(color=tc()['label_text'], size=13),
                name="Brayton Cycle",
                hovertemplate=(
                    f"<b>Brayton State</b><br>"
                    f"s = %{{x:.4f}} {s_u_br}<br>"
                    f"T = %{{y:.1f}} {t_u_br}<extra></extra>"
                )
            ))

            
            fig_br.add_trace(go.Scatter(
                x=[s1k, s1k], y=[T1k, conv(cached_propsi("T","P",P2b,"H",h2sb,AIR)-273.15,'T')],
                mode="lines", line=dict(color=tc()['pump'], width=2, dash="dash"),
                name="Ideal Compression"
            ))
            fig_br.add_trace(go.Scatter(
                x=[s3k, s3k], y=[T3k, conv(cached_propsi("T","P",P4b,"H",h4sb,AIR)-273.15,'T')],
                mode="lines", line=dict(color=tc()['supercrit'], width=2, dash="dash"),
                name="Ideal Expansion"
            ))

            
            fig_br.add_annotation(
                x=(s1k+s2k)/2, y=(T1k+T2k)/2,
                text=f"Wc = {conv(W_compb,'H'):.0f} {h_u_br}",
                showarrow=True, arrowhead=2, ax=-45, ay=25,
                bgcolor="rgba(0,0,0,0.65)"
            )
            fig_br.add_annotation(
                x=(s2k+s3k)/2, y=(T2k+T3k)/2,
                text=f"Qin = {conv(Q_inb,'H'):.0f} {h_u_br}",
                showarrow=True, arrowhead=2, ax=45, ay=-30,
                bgcolor="rgba(0,0,0,0.65)"
            )
            fig_br.add_annotation(
                x=(s3k+s4k)/2, y=(T3k+T4k)/2,
                text=f"Wt = {conv(W_turbb,'H'):.0f} {h_u_br}",
                showarrow=True, arrowhead=2, ax=55, ay=20,
                bgcolor="rgba(0,0,0,0.65)"
            )

            br_layout = layout_common.copy()
            br_layout.update(
                title="Brayton Cycle — T-s Diagram",
                uirevision="Brayton-ts",
                xaxis=dict(title=axis_title("Entropy", "S"), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
                yaxis=dict(title=axis_title("Temperature", "T"), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
            )
            fig_br.update_layout(**br_layout)
            st.plotly_chart(fig_br, use_container_width=True, config=plot_config, key="fig_br")

            st.success(
                "✓ Gas-turbine checks passed: all four actual states remain in the gas phase."
            )

        except Exception as e:
            st.error(f"Could not solve the Brayton cycle: {e}")
if st.session_state.app_view == "cycles":
    render_topbar("Power Cycle Lab")
    render_power_cycle_analysis()
    render_footer()
    st.stop()

render_topbar("Fluid Property Explorer")

st.subheader("Inputs")

# Critical temperature/pressure block — right after the "Inputs" heading,
# before mode selection. fmt_canon() keeps Tc/Pc in sync with whatever T/P
# unit was last chosen (persisted in session_state), so this still reflects
# the current unit choice even though it now renders before that dropdown.
try:
    _tcrit_c = PropsSI('Tcrit', fluid) - 273.15
    _pcrit_bar = PropsSI('pcrit', fluid) / 100000
    _tcrit_disp, _tcrit_u = fmt_canon(_tcrit_c, 'T', 2)
    _pcrit_disp, _pcrit_u = fmt_canon(_pcrit_bar, 'P', 2)
    st.markdown(
        '<div class="small-box critical-box">'
        f'<b>Active Fluid:</b> {fluid_display}<br>'
        f'<b>Critical Point:</b> Tc = {_tcrit_disp} {_tcrit_u} &nbsp;|&nbsp; '
        f'Pc = {_pcrit_disp} {_pcrit_u}</div>',
        unsafe_allow_html=True
    )
except Exception:
    st.markdown(
        f'<div class="small-box critical-box"><b>Active Fluid:</b> {fluid_display}</div>',
        unsafe_allow_html=True
    )

mode = st.selectbox(
    "🔎 Select Properties To Compute",
    [
        "Saturation Properties at T",
        "Saturation Properties at P",
        "Pressure and Temperature",
        "Pressure and Sp. Enthalpy",
        "Pressure and Sp. Entropy",
        "Pressure and Sp. Volume",
        "Temperature and Sp. Entropy",
        "Temperature and Sp. Volume"
    ],
    key="mode_select"
)

col1, col2 = st.columns([1,2])
with col1:

    # ---- Step 1: the property inputs/units for the selected mode, in
    # their existing grid layout — unchanged width/layout from before. ----
    quality_slider_visible = False
    if mode == "Saturation Properties at T":
        with st.container(key="igrid_exp_satT"):
            _sat_t_c1, _sat_t_c2 = st.columns(2)

        with _sat_t_c1:
            T_input = unit_number_input(
                "Temperature", "T",
                min_value=float(limits["T_min"]),
                max_value=float(limits["T_max"]),
                value=float(max(25.0, limits["T_min"])),
                step=1.0,
                key="exp_T_1"
            )

        input1 = 'T'
        val1 = T_input + 273.15
    elif mode == "Saturation Properties at P":

        with st.container(key="igrid_exp_satP"):
            _sat_p_c1, _sat_p_c2 = st.columns(2)

        with _sat_p_c1:
            P_input = unit_number_input(
                "Pressure", "P",
                min_value=float(limits["P_min"]),
                max_value=float(limits["P_max"]),
                value=float(max(1.0, limits["P_min"])),
                step=0.1,
                key="exp_P_1"
            )

        input1 = 'P'
        val1 = P_input * 100000
    elif mode == "Pressure and Temperature":

        c1, c2 = st.container(key="igrid_exp_pt").columns(2)

        with c1:

            P_input = unit_number_input(
                "Pressure", "P",
                min_value=float(limits["P_min"]),
                max_value=float(limits["P_max"]),
                value=float(max(1.0, limits["P_min"])),
                step=0.1,
                key="exp_P_2"
            )

        with c2:

            T_input = unit_number_input(
                "Temperature", "T",
                min_value=float(limits["T_min"]),
                max_value=float(limits["T_max"]),
                value=float(max(25.0, limits["T_min"])),
                step=1.0,
                key="exp_T_2"
            )

        input1 = 'P'
        val1 = P_input * 100000

        input2 = 'T'
        val2 = T_input + 273.15
    elif mode == "Pressure and Sp. Enthalpy":

        c1, c2 = st.container(key="igrid_exp_ph").columns(2)

        with c1:

            P_input = unit_number_input(
                "Pressure", "P",
                min_value=float(limits["P_min"]),
                max_value=float(limits["P_max"]),
                value=float(max(1.0, limits["P_min"])),
                step=0.1,
                key="exp_P_3"
            )

        with c2:

            H_input = unit_number_input(
                "Sp. Enthalpy", "H",
                min_value=float(limits["H_min"]),
                max_value=float(limits["H_max"]),
                value=float(max(300.0, limits["H_min"])),
                step=10.0,
                key="exp_H_1"
            )

        input1 = 'P'
        val1 = P_input * 100000

        input2 = 'H'
        val2 = H_input * 1000
    elif mode == "Pressure and Sp. Entropy":

        c1, c2 = st.container(key="igrid_exp_ps").columns(2)

        with c1:

            P_input = unit_number_input(
                "Pressure", "P",
                min_value=float(limits["P_min"]),
                max_value=float(limits["P_max"]),
                value=float(max(1.0, limits["P_min"])),
                step=0.1,
                key="exp_P_4"
            )

        with c2:

            S_input = unit_number_input(
                "Sp. Entropy", "S",
                min_value=float(limits["S_min"]),
                max_value=float(limits["S_max"]),
                value=float(max(1.0, limits["S_min"])),
                step=0.1,
                key="exp_S_1"
            )

        input1 = 'P'
        val1 = P_input * 100000

        input2 = 'S'
        val2 = S_input * 1000
    elif mode == "Pressure and Sp. Volume":

        c1, c2 = st.container(key="igrid_exp_pv").columns(2)

        with c1:

            P_input = unit_number_input(
                "Pressure", "P",
                min_value=float(limits["P_min"]),
                max_value=float(limits["P_max"]),
                value=float(max(1.0, limits["P_min"])),
                step=0.1,
                key="exp_P_5"
            )

        with c2:

            V_input = unit_number_input(
                "Sp. Volume", "V",
                min_value=float(limits["V_min"]),
                max_value=float(limits["V_max"]),
                value=float(max(0.1, limits["V_min"])),
                step=0.01,
                key="exp_V_1"
            )

        input1 = 'P'
        val1 = P_input * 100000

        input2 = 'D'
        val2 = 1 / V_input
    elif mode == "Temperature and Sp. Entropy":

        c1, c2 = st.container(key="igrid_exp_ts").columns(2)

        with c1:

            T_input = unit_number_input(
                "Temperature", "T",
                min_value=float(limits["T_min"]),
                max_value=float(limits["T_max"]),
                value=float(max(25.0, limits["T_min"])),
                step=1.0,
                key="exp_T_3"
            )

        with c2:

            S_input = unit_number_input(
                "Sp. Entropy", "S",
                min_value=float(limits["S_min"]),
                max_value=float(limits["S_max"]),
                value=float(max(1.0, limits["S_min"])),
                step=0.1,
                key="exp_S_2"
            )

        input1 = 'T'
        val1 = T_input + 273.15

        input2 = 'S'
        val2 = S_input * 1000
    elif mode == "Temperature and Sp. Volume":

        c1, c2 = st.container(key="igrid_exp_tv").columns(2)

        with c1:

            T_input = unit_number_input(
                "Temperature", "T",
                min_value=float(limits["T_min"]),
                max_value=float(limits["T_max"]),
                value=float(max(25.0, limits["T_min"])),
                step=1.0,
                key="exp_T_4"
            )

        with c2:

            V_input = unit_number_input(
                "Sp. Volume", "V",
                min_value=float(limits["V_min"]),
                max_value=float(limits["V_max"]),
                value=float(max(0.1, limits["V_min"])),
                step=0.01,
                key="exp_V_2"
            )

        input1 = 'T'
        val1 = T_input + 273.15

        input2 = 'D'
        val2 = 1 / V_input

    # ---- Step 2: quality checkbox, then the Quality (x) slider right
    # below it. Only the two saturation modes actually use quality as
    # their second input — for every other mode this just sets the
    # want_quality gate used later (liquid/vapor % box, mixture warning). ----
    if is_two_phase_fluid:
        want_quality = st.checkbox(
            "Quality Calculation",
            value=True,
            key="quality_check"
        )
    else:
        want_quality = False

    if mode == "Saturation Properties at T":
        if want_quality and is_two_phase_fluid:
            quality_slider_visible = True
            quality = st.slider("Quality (x)", 0.0, 1.0, 0.5, 0.01)
            input2 = 'Q'
            val2 = quality
        else:
            input2 = 'Q'
            val2 = 0
    elif mode == "Saturation Properties at P":
        if want_quality and is_two_phase_fluid:
            quality_slider_visible = True
            quality = st.slider("Quality (x)", 0.0, 1.0, 0.5, 0.01)
            input2 = 'Q'
            val2 = quality
        else:
            input2 = 'Q'
            val2 = 0

with col1:

    quality_warning_placeholder = st.empty()

    slider_placeholder = st.empty()

    quality_box_placeholder = st.empty()
try:

    PropsSI(
        'D',
        input1,
        val1,
        input2,
        val2,
        fluid
    )

except:
    if fluid == "CO2":

        try:

            Ptriple = PropsSI(
                'ptriple',
                fluid
            ) / 100000

            
            if input1 == 'P':

                P_bar = val1 / 100000

            elif input2 == 'P':

                P_bar = val2 / 100000

            else:

                P_bar = None

            
            if P_bar is not None and P_bar < Ptriple:

                st.warning(
                    "CO₂ below triple-point pressure.\n\n"
                    "Solid + Vapor region detected "
                    "(dry ice sublimation region).\n\n"
                    "Liquid phase does not exist here."
                )

                st.stop()

        except:
            pass

    st.error(
        f"State outside thermodynamic limits for {fluid_display}"
    )

    st.stop()
manual_quality_mode = False
manual_quality = np.nan
quality = np.nan

if is_two_phase_fluid:

    try:

        if 'P' in [input1, input2]:

            P_ref = (

                val1
                if input1 == 'P'
                else val2

            )

            hf_ref = PropsSI(
                'H',
                'P',
                P_ref,
                'Q',
                0,
                fluid
            )

            hg_ref = PropsSI(
                'H',
                'P',
                P_ref,
                'Q',
                1,
                fluid
            )

            sf_ref = PropsSI(
                'S',
                'P',
                P_ref,
                'Q',
                0,
                fluid
            )

            sg_ref = PropsSI(
                'S',
                'P',
                P_ref,
                'Q',
                1,
                fluid
            )
            vf_ref = 1 / PropsSI(
                'D',
                'P',
                P_ref,
                'Q',
                0,
                fluid
            )
            vg_ref = 1 / PropsSI(
                'D',
                'P',
                P_ref,
                'Q',
                1,
                fluid
            )
            Tsat_ref = PropsSI(
                'T',
                'P',
                P_ref,
                'Q',
                0,
                fluid
            )
            if mode == "Pressure and Temperature":
                T_actual = (
                    val1
                    if input1 == 'T'
                    else val2
                )
                tol = 0.05
                if abs(T_actual - Tsat_ref) <= tol:
                    manual_quality_mode = True
                    try:
                           quality = PropsSI(
                            'Q',
                            'P',
                               P_ref,
                               'T',
                               T_actual,
                               fluid
                           )
                    except:
                           quality = 0.5
            elif mode == "Pressure and Sp. Enthalpy":
                if hf_ref <= val2 <= hg_ref:
                    manual_quality_mode = True
            elif mode == "Pressure and Sp. Entropy":
                if sf_ref <= val2 <= sg_ref:
                    manual_quality_mode = True
            elif mode == "Pressure and Sp. Volume":
                V_actual = 1 / val2
                if vf_ref <= V_actual <= vg_ref:
                    manual_quality_mode = True
        elif 'T' in [input1, input2]:
            T_ref = (
                val1
                if input1 == 'T'
                else val2
            )
            sf_ref = PropsSI(
                'S',
                'T',
                T_ref,
                'Q',
                0,
                fluid
            )
            sg_ref = PropsSI(
                'S',
                'T',
                T_ref,
                'Q',
                1,
                fluid
            )
            vf_ref = 1 / PropsSI(
                'D',
                'T',
                T_ref,
                'Q',
                0,
                fluid
            )
            vg_ref = 1 / PropsSI(
                'D',
                'T',
                T_ref,
                'Q',
                1,
                fluid
            )
            if mode == "Temperature and Sp. Entropy":
                if sf_ref <= val2 <= sg_ref:
                    manual_quality_mode = True
            elif mode == "Temperature and Sp. Volume":
                V_actual = 1 / val2
                if vf_ref <= V_actual <= vg_ref:
                    manual_quality_mode = True
    except:
        pass
manual_quality = np.nan
with quality_warning_placeholder:
    if manual_quality_mode and want_quality:
        st.warning(
            "Mixture region detected. "
            "Adjust quality manually."
        )
with slider_placeholder:
    if manual_quality_mode and want_quality:
        auto_quality = quality
        if not np.isfinite(auto_quality):
            auto_quality = 0.5
        try:
            q_guess = PropsSI(
                'Q',
                input1,
                val1,
                input2,
                val2,
                fluid
            )
            if np.isfinite(q_guess):
                if 0 <= q_guess <= 1:
                    auto_quality = float(q_guess)
        except:
            pass
        auto_quality = min(
            1.0,
            max(
                0.0,
                float(auto_quality)
            )
        )
        quality_key = (
            f"{fluid}_"
            f"{mode}_"
            f"{round(val1,3)}_"
            f"{round(val2,6)}"
        )
        manual_quality = st.slider(
            "Quality (x)",
            min_value=0.0,
            max_value=1.0,
            value=auto_quality,
            step=0.01,
            key=quality_key
        )
state_original = solve_state(
    input1,
    val1,
    input2,
    val2,
    fluid
)
state = state_original
quality = np.nan
try:
    q_calc = PropsSI(
        'Q',
        input1,
        val1,
        input2,
        val2,
        fluid
    )
    if np.isfinite(q_calc):
        if 0 <= q_calc <= 1:
            quality = q_calc
except:
    pass
if (
    manual_quality_mode
    and np.isfinite(manual_quality)
):
    try:
        mixture_state = None
        if 'P' in [input1, input2]:
            P_ref = (
                val1
                if input1 == 'P'
                else val2
            )
            mixture_state = solve_state(
                'P',
                P_ref,
                'Q',
                manual_quality,
                fluid                   
            )
        elif 'T' in [input1, input2]:
            T_ref = (
                val1
                if input1 == 'T'
                else val2
            )
            mixture_state = solve_state(
                'T',
                T_ref,
                'Q',
                manual_quality,
                fluid
            )
        if mixture_state:
            valid = all(
                np.isfinite(
                    mixture_state.get(
                        k,
                        np.nan
                    )
                )
                for k in
                [
                    'P',
                    'T',
                    'H',
                    'S',
                    'D',
                    'V'
                ]
            )
            if valid:
                state = mixture_state
                quality = manual_quality
    except:
        state = state_original
if not np.isfinite(
    state.get(
        'P',
        np.nan
    )
):
    state = state_original
Tsat = np.nan
Psat = np.nan
try:
    Tsat = PropsSI(
        'T',
        'P',
        state['P'],
        'Q',
        0,
        fluid
    ) - 273.15
except:
    pass
try:
    Psat = PropsSI(
        'P',
        'T',
        state['T'],
        'Q',
        0,
        fluid
    ) / 100000
except:
    pass
phase = detect_phase(
    state,
    quality,
    Tsat,
    fluid_display
)
vf = vg = hf = hg = sf = sg = uf = ug = np.nan
if is_two_phase_fluid:
    try:
        if 'P' in [input1, input2]:
            refP = state['P']
            vf = 1 / sat_prop('D', 'P', refP, 0, fluid)
            vg = 1 / sat_prop('D', 'P', refP, 1, fluid)
            hf = sat_prop('H', 'P', refP, 0, fluid) / 1000
            hg = sat_prop('H', 'P', refP, 1, fluid) / 1000
            sf = sat_prop('S', 'P', refP, 0, fluid) / 1000
            sg = sat_prop('S', 'P', refP, 1, fluid) / 1000
            uf = sat_prop('U', 'P', refP, 0, fluid) / 1000
            ug = sat_prop('U', 'P', refP, 1, fluid) / 1000
        else:
            refT = state['T']
            vf = 1 / sat_prop('D', 'T', refT, 0, fluid)
            vg = 1 / sat_prop('D', 'T', refT, 1, fluid)
            hf = sat_prop('H', 'T', refT, 0, fluid) / 1000
            hg = sat_prop('H', 'T', refT, 1, fluid) / 1000
            sf = sat_prop('S', 'T', refT, 0, fluid) / 1000
            sg = sat_prop('S', 'T', refT, 1, fluid) / 1000
            uf = sat_prop('U', 'T', refT, 0, fluid) / 1000
            ug = sat_prop('U', 'T', refT, 1, fluid) / 1000
    except:
        pass
with quality_box_placeholder:
    if want_quality and not np.isnan(quality):
        if 0 <= quality <= 1:
            liquid_percent = (1-quality)*100
            vapor_percent = quality*100
            st.markdown(
                f"""
                <div class="info-box">
                Liquid : {liquid_percent:.2f}% \n
                Vapor : {vapor_percent:.2f}%
                </div>
                """,
                unsafe_allow_html=True
            )
with col2:
    st.subheader("Thermodynamic Properties")
    p_val, p_u = fmt_canon(state['P'] / 100000, 'P')
    t_val, t_u = fmt_canon(state['T'] - 273.15, 'T')
    tsat_val, tsat_u = fmt_canon(Tsat, 'T')
    v_val, v_u = fmt_canon(state['V'], 'V')
    h_val, h_u = fmt_canon(state['H'] / 1000, 'H')
    s_val, s_u = fmt_canon(state['S'] / 1000, 'S')
    rows = [
        [f'Pressure ({p_u})', fmt(p_val)],
        [f'Temperature ({t_u})', fmt(t_val)],
        [f'Saturation Temp ({tsat_u})', fmt(tsat_val)],
        [f'Specific Volume ({v_u})', fmt(v_val, 7)],
        [f'Specific Enthalpy ({h_u})', fmt(h_val)],
        [f'Specific Entropy ({s_u})', fmt(s_val)],
        ['Phase', phase]
    ]
    if want_quality and not np.isnan(quality):
        u_val, u_u = fmt_canon(state['U'] / 1000, 'H')
        rows.extend([
            ['Density (kg/m³)', fmt(state['D'])],
            [f'Internal Energy ({u_u})', fmt(u_val)],
            ['Quality (x)', fmt(quality)]
        ])
    elif ( not want_quality and is_two_phase_fluid and np.isfinite(vf) and np.isfinite(vg)):
        show_sat = False
        try:
            if mode == "Pressure and Temperature":
                T_actual = (
                   val1 if input1=='T'
                   else val2
                )
                TsatK = Tsat + 273.15
                show_sat = abs(
                    T_actual - TsatK
                ) <= 0.05
            else:
                if np.isfinite(state['V']):
                    show_sat = (
                        vf <= state['V'] <= vg
                    )
        except:
             pass
        if show_sat:
            vf_val, vf_u = fmt_canon(vf, 'V')
            vg_val, vg_u = fmt_canon(vg, 'V')
            hf_val, hf_u = fmt_canon(hf, 'H')
            hg_val, hg_u = fmt_canon(hg, 'H')
            sf_val, sf_u = fmt_canon(sf, 'S')
            sg_val, sg_u = fmt_canon(sg, 'S')
            rows.extend([
                [f'Sat. Liquid Vol. vf ({vf_u})', fmt(vf_val, 7)],
                [f'Sat. Vapor Vol. vg ({vg_u})', fmt(vg_val, 7)],
                [f'Sat. Liquid Enthalpy hf ({hf_u})', fmt(hf_val)],
                [f'Sat. Vapor Enthalpy hg ({hg_u})', fmt(hg_val)],
                [f'Sat. Liquid Entropy sf ({sf_u})', fmt(sf_val)],
                [f'Sat. Vapor Entropy sg ({sg_u})', fmt(sg_val)]
            ])
    df = pd.DataFrame(rows, columns=['Property', 'Value'])
    show_state_table(df)
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(
        excel_buffer,
        engine='openpyxl'
    ) as writer:
        df.to_excel(
            writer,
            sheet_name='Thermo Properties',
            index=False
        )
    excel_data = excel_buffer.getvalue()
    st.download_button(
        label="📥 Download Properties (Excel)",
        data=excel_data,
        file_name=(
            f"{fluid_display}_"
            f"{mode.replace(' ','_')}_"
            "Properties.xlsx"
        ),
        mime=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        use_container_width=True
    )
P_range = np.logspace(np.log10(limits["P_min"]), np.log10(limits["P_max"]), 100)
Tmin, Tmax = get_plot_temperature_range(fluid_display)
T_eval_range = np.linspace(Tmin, Tmax, 100)
# Hashable copies of the eval ranges so st.cache_data can key on them below.
T_tuple = tuple(float(t) for t in T_eval_range)
P_tuple = tuple(float(p) for p in P_range)

def add_state_marker(fig, x, y):
    # NOTE: this file intentionally uses go.Scatter (SVG) everywhere below,
    # not go.Scattergl (WebGL). The 6 diagrams used to use Scattergl for a
    # perf boost, but each one opens its own WebGL context, and 6 open at
    # once. Mobile browsers cap concurrent WebGL contexts (often well under
    # 10) and evict page-wide under memory pressure, which is what caused
    # charts to flicker on load and then all go blank together after a
    # fullscreen toggle. These curves are only ~100-600 points each — plain
    # SVG Scatter has no perceptible performance cost here and no context
    # limit to hit.
    if not is_valid_number(x) or not is_valid_number(y):
        return
    fig.add_trace(go.Scatter(
        x=[x], y=[y], mode='markers',
        marker=dict(size=15, color=tc()['state'], symbol='circle', line=dict(color=tc()['marker_line'], width=2.5)),
        name='State Point',
        hovertemplate="State Point<br>X: %{x:.4f}<br>Y: %{y:.4f}<extra></extra>"
    ))
@st.cache_data(show_spinner=False)
def generate_Pv_isotherm(fluid, temperature_C, Pmin, Pmax):
    P_eval = np.logspace(np.log10(max(Pmin, 1e-4)), np.log10(Pmax), 80)
    vols, pres = [], []
    for p_bar in P_eval:
        try:
            D = cached_props('D', 'T', temperature_C + 273.15, 'P', p_bar * 100000, fluid)
            if D > 0:
                vols.append(1.0 / D)
                pres.append(p_bar)
        except:
            pass
    return vols, pres

@st.cache_data(show_spinner=False)
def gen_isobar_ST(fluid, P_pa, T_tuple):
    """Entropy (kJ/kg-K) and temperature (°C) along a fixed-pressure line."""
    S_out, T_out = [], []
    for T_k in T_tuple:
        S = cached_props('S', 'P', P_pa, 'T', T_k, fluid) / 1000
        if is_valid_number(S):
            S_out.append(S)
            T_out.append(T_k - 273.15)
    return S_out, T_out

@st.cache_data(show_spinner=False)
def gen_isobar_VT(fluid, P_pa, T_tuple):
    """Specific volume (via density) and temperature (°C) along a fixed-pressure line."""
    V_out, T_out = [], []
    for T_k in T_tuple:
        D = cached_props('D', 'P', P_pa, 'T', T_k, fluid)
        if D and D > 0:
            V_out.append(1.0 / D)
            T_out.append(T_k - 273.15)
    return V_out, T_out

@st.cache_data(show_spinner=False)
def gen_isobar_HT(fluid, P_pa, T_tuple):
    """Enthalpy (kJ/kg) and temperature (°C) along a fixed-pressure line."""
    H_out, T_out = [], []
    for T_k in T_tuple:
        H = cached_props('H', 'P', P_pa, 'T', T_k, fluid) / 1000
        if is_valid_number(H):
            H_out.append(H)
            T_out.append(T_k - 273.15)
    return H_out, T_out

@st.cache_data(show_spinner=False)
def gen_isobar_SH(fluid, P_pa, T_tuple):
    """Entropy (kJ/kg-K) and enthalpy (kJ/kg) along a fixed-pressure line (Mollier)."""
    S_out, H_out = [], []
    for T_k in T_tuple:
        S = cached_props('S', 'P', P_pa, 'T', T_k, fluid) / 1000
        H = cached_props('H', 'P', P_pa, 'T', T_k, fluid) / 1000
        if is_valid_number(S) and is_valid_number(H):
            S_out.append(S)
            H_out.append(H)
    return S_out, H_out

@st.cache_data(show_spinner=False)
def gen_isotherm_HP(fluid, T_k, P_tuple):
    """Enthalpy (kJ/kg) as a function of pressure (bar) at a fixed temperature (K)."""
    H_out, P_out = [], []
    for p_bar in P_tuple:
        H = cached_props('H', 'T', T_k, 'P', p_bar * 100000, fluid) / 1000
        if is_valid_number(H):
            H_out.append(H)
            P_out.append(p_bar)
    return H_out, P_out

@st.cache_data(show_spinner=False)
def gen_isotherm_SH(fluid, T_k, P_tuple):
    """Entropy (kJ/kg-K) and enthalpy (kJ/kg) as a function of pressure (bar) at a fixed temperature (K)."""
    S_out, H_out = [], []
    for p_bar in P_tuple:
        S = cached_props('S', 'T', T_k, 'P', p_bar * 100000, fluid) / 1000
        H = cached_props('H', 'T', T_k, 'P', p_bar * 100000, fluid) / 1000
        if is_valid_number(S) and is_valid_number(H):
            S_out.append(S)
            H_out.append(H)
    return S_out, H_out

g1, g2 = st.container(key="steam_graph_row1").columns(2)
with g1:
    fig1 = go.Figure()
    v_u = disp_unit('V')
    p_u = disp_unit('P')
    t_u = disp_unit('T')
    temperatures = np.linspace((state['T'] - 273.15) - 80, (state['T'] - 273.15) + 120, 6)
    for T_c in temperatures:
        vols, pres = generate_Pv_isotherm(fluid, T_c, limits["P_min"], limits["P_max"])
        if vols:
            T_disp = conv(T_c, 'T')
            fig1.add_trace(go.Scatter(
                x=conv(np.array(vols), 'V'), y=conv(np.array(pres), 'P'), mode='lines',
                line=dict(color=tc()['isotherm'], width=2), showlegend=False,
                hovertemplate=f"<b>Isotherm ({T_disp:.0f}{t_u})</b><br>v: %{{x:.4f}} {v_u}<br>P: %{{y:.2f}} {p_u}<extra></extra>"
            ))
    if dome is not None:
        v_out, p_out = generate_Pv_isotherm(fluid, max(dome['T']) + 15.0, limits["P_min"], limits["P_max"])
        fig1.add_trace(go.Scatter(
            x=conv(np.array(v_out), 'V'), y=conv(np.array(p_out), 'P'), mode='lines', line=dict(color=tc()['supercrit'], width=1.5, dash='dot'), name='Supercritical Border',
            hovertemplate=f"<b>Supercritical Border</b><br>v: %{{x:.4f}} {v_u}<br>P: %{{y:.2f}} {p_u}<extra></extra>"
        ))
    v_state, p_state = generate_Pv_isotherm(fluid, state['T']-273.15, limits["P_min"], limits["P_max"])
    T_state_disp = conv(state['T']-273.15, 'T')
    fig1.add_trace(go.Scatter(
        x=conv(np.array(v_state), 'V'), y=conv(np.array(p_state), 'P'), mode='lines', line=dict(color=tc()['state'], width=3), name='State Isotherm (T)',
        hovertemplate=f"<b>State Isotherm ({T_state_disp:.1f}{t_u})</b><br>v: %{{x:.4f}} {v_u}<br>P: %{{y:.2f}} {p_u}<extra></extra>"
    ))    
    if dome is not None:
        fig1.add_trace(go.Scatter(
            x=conv(np.array(dome['vf']), 'V'), y=conv(np.array(dome['P']), 'P'), mode='lines', line=dict(color=tc()['dome_liq'], width=3.5), name='Sat Liquid',
            hovertemplate=f"<b>Saturated Liquid Curve</b><br>v_f: %{{x:.4f}} {v_u}<br>P: %{{y:.2f}} {p_u}<extra></extra>"
        ))
        fig1.add_trace(go.Scatter(
            x=conv(np.array(dome['vg']), 'V'), y=conv(np.array(dome['P']), 'P'), mode='lines', line=dict(color=tc()['dome_vap'], width=3.5), name='Sat Vapor',
            hovertemplate=f"<b>Saturated Vapor Curve</b><br>v_g: %{{x:.4f}} {v_u}<br>P: %{{y:.2f}} {p_u}<extra></extra>"
        ))
    add_state_marker(fig1, conv(state['V'], 'V'), conv(state['P']/100000, 'P'))
    pv_layout = layout_common_grid.copy()
    pv_layout.update(
        title='P-v Diagram',
        uirevision='fig1_pv',
        xaxis=dict(type='log', title=axis_title('Specific Volume', 'V'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
        yaxis=dict(type='log', title=axis_title('Pressure', 'P'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
    )
    fig1.update_layout(**pv_layout)    
    st.plotly_chart(fig1, use_container_width=True, config=plot_config, key="fig1_pv")
with g2:
    fig2 = go.Figure()
    s_u = disp_unit('S')
    t_u2 = disp_unit('T')
    p_u2 = disp_unit('P')
    pressures = np.logspace(np.log10(limits["P_min"]), np.log10(limits["P_max"]), 6)
    for P_bar in pressures:
        ent, temps = gen_isobar_ST(fluid, P_bar * 100000, T_tuple)
        if ent:
            P_disp = conv(P_bar, 'P')
            fig2.add_trace(go.Scatter(
                x=conv(np.array(ent), 'S'), y=conv(np.array(temps), 'T'), mode='lines',
                line=dict(color=tc()['isobar'], width=2),
                showlegend=False,
                hovertemplate=f"<b>Isobar ({P_disp:.1f} {p_u2})</b><br>s: %{{x:.3f}} {s_u}<br>T: %{{y:.1f}} {t_u2}<extra></extra>"
            ))
    ent_state, temps_state = gen_isobar_ST(fluid, state['P'], T_tuple)
    if ent_state:
        P_state_disp = conv(state['P']/100000, 'P')
        fig2.add_trace(go.Scatter(
            x=conv(np.array(ent_state), 'S'), y=conv(np.array(temps_state), 'T'), mode='lines',
            line=dict(color=tc()['state'], width=3),
            name=f"State Isobar ({P_state_disp:.2f} {p_u2})",
            hovertemplate=f"<b>State Isobar ({P_state_disp:.2f} {p_u2})</b><br>s: %{{x:.3f}} {s_u}<br>T: %{{y:.1f}} {t_u2}<extra></extra>"
        ))
    if dome is not None:
        fig2.add_trace(go.Scatter(
            x=conv(np.array(dome['sf']), 'S'), y=conv(np.array(dome['T']), 'T'), mode='lines', line=dict(color=tc()['dome_liq'], width=3.5), showlegend=False,
            hovertemplate=f"<b>Sat Liquid Boundary</b><br>s_f: %{{x:.3f}} {s_u}<br>T: %{{y:.1f}} {t_u2}<extra></extra>"
        ))
        fig2.add_trace(go.Scatter(
            x=conv(np.array(dome['sg']), 'S'), y=conv(np.array(dome['T']), 'T'), mode='lines', line=dict(color=tc()['dome_vap'], width=3.5), showlegend=False,
            hovertemplate=f"<b>Sat Vapor Boundary</b><br>s_g: %{{x:.3f}} {s_u}<br>T: %{{y:.1f}} {t_u2}<extra></extra>"
        ))
    add_state_marker(fig2, conv(state['S']/1000, 'S'), conv(state['T']-273.15, 'T'))
    ts_layout = layout_common_grid.copy()
    ts_layout.update(
        title='T-s Diagram',
        uirevision='fig2_ts',
        xaxis=dict(type='linear', title=axis_title('Entropy', 'S'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
        yaxis=dict(type='linear', title=axis_title('Temperature', 'T'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
    )
    fig2.update_layout(**ts_layout)
    st.plotly_chart(fig2, use_container_width=True, config=plot_config, key="fig2_ts")
g3, g4 = st.container(key="steam_graph_row2").columns(2)
with g3:
    fig3 = go.Figure()
    v_u3 = disp_unit('V')
    t_u3 = disp_unit('T')
    p_u3 = disp_unit('P')
    for P_bar in pressures:
        vols, temps = gen_isobar_VT(fluid, P_bar * 100000, T_tuple)
        if vols:
            P_disp3 = conv(P_bar, 'P')
            fig3.add_trace(go.Scatter(
                x=conv(np.array(vols), 'V'), y=conv(np.array(temps), 'T'), mode='lines',
                line=dict(color=tc()['isobar'], width=2),
                showlegend=False,
                hovertemplate=f"<b>Isobar ({P_disp3:.1f} {p_u3})</b><br>v: %{{x:.4f}} {v_u3}<br>T: %{{y:.1f}} {t_u3}<extra></extra>"
            ))
    v_state, temps_state = gen_isobar_VT(fluid, state['P'], T_tuple)
    if v_state:
        P_state_disp3 = conv(state['P']/100000, 'P')
        fig3.add_trace(go.Scatter(
            x=conv(np.array(v_state), 'V'), y=conv(np.array(temps_state), 'T'), mode='lines',
            line=dict(color=tc()['state'], width=3),
            name=f"State Isobar ({P_state_disp3:.2f} {p_u3})",
            hovertemplate=f"<b>State Isobar ({P_state_disp3:.2f} {p_u3})</b><br>v: %{{x:.4f}} {v_u3}<br>T: %{{y:.1f}} {t_u3}<extra></extra>"
        ))
    if dome is not None:
        fig3.add_trace(go.Scatter(
            x=conv(np.array(dome['vf']), 'V'), y=conv(np.array(dome['T']), 'T'), mode='lines', line=dict(color=tc()['dome_liq'], width=3.5), showlegend=False,
            hovertemplate=f"<b>Sat Liquid Boundary</b><br>v_f: %{{x:.4f}} {v_u3}<br>T: %{{y:.1f}} {t_u3}<extra></extra>"
        ))
        fig3.add_trace(go.Scatter(
            x=conv(np.array(dome['vg']), 'V'), y=conv(np.array(dome['T']), 'T'), mode='lines', line=dict(color=tc()['dome_vap'], width=3.5), showlegend=False,
            hovertemplate=f"<b>Sat Vapor Boundary</b><br>v_g: %{{x:.4f}} {v_u3}<br>T: %{{y:.1f}} {t_u3}<extra></extra>"
        ))
    add_state_marker(fig3, conv(state['V'], 'V'), conv(state['T']-273.15, 'T'))
    tv_layout = layout_common_grid.copy()
    tv_layout.update(
        title='T-v Diagram',
        uirevision='fig3_tv',
        xaxis=dict(type='log', title=axis_title('Specific Volume', 'V'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
        yaxis=dict(type='linear',title=axis_title('Temperature', 'T'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
    )
    fig3.update_layout(**tv_layout)
    st.plotly_chart(fig3, use_container_width=True, config=plot_config, key="fig3_tv")
with g4:
    fig4 = go.Figure()
    h_u4 = disp_unit('H')
    p_u4 = disp_unit('P')
    t_u4 = disp_unit('T')
    for T_c in temperatures:
        ent, pres = gen_isotherm_HP(fluid, T_c + 273.15, P_tuple)
        if ent:
            T_disp4 = conv(T_c, 'T')
            fig4.add_trace(go.Scatter(
                x=conv(np.array(ent), 'H'), y=conv(np.array(pres), 'P'), mode='lines',
                line=dict(color=tc()['isotherm'], width=2),
                showlegend=False,
                hovertemplate=f"<b>Isotherm ({T_disp4:.0f}{t_u4})</b><br>h: %{{x:.1f}} {h_u4}<br>P: %{{y:.2f}} {p_u4}<extra></extra>"
            ))
    ent_state, pres_state = gen_isotherm_HP(fluid, state['T'], P_tuple)
    if ent_state:
        T_state_disp4 = conv(state['T']-273.15, 'T')
        fig4.add_trace(go.Scatter(
            x=conv(np.array(ent_state), 'H'), y=conv(np.array(pres_state), 'P'), mode='lines',
            line=dict(color=tc()['state'], width=3),
            name=f"State Isotherm ({T_state_disp4:.1f} {t_u4})",
            hovertemplate=f"<b>State Isotherm ({T_state_disp4:.1f} {t_u4})</b><br>h: %{{x:.1f}} {h_u4}<br>P: %{{y:.2f}} {p_u4}<extra></extra>"
        ))    
    if dome is not None:
        fig4.add_trace(go.Scatter(
            x=conv(np.array(dome['hf']), 'H'), y=conv(np.array(dome['P']), 'P'), mode='lines', line=dict(color=tc()['dome_liq'], width=3.5), showlegend=False,
            hovertemplate=f"<b>Sat Liquid Boundary</b><br>h_f: %{{x:.1f}} {h_u4}<br>P: %{{y:.2f}} {p_u4}<extra></extra>"
        ))
        fig4.add_trace(go.Scatter(
            x=conv(np.array(dome['hg']), 'H'), y=conv(np.array(dome['P']), 'P'), mode='lines', line=dict(color=tc()['dome_vap'], width=3.5), showlegend=False,
            hovertemplate=f"<b>Sat Vapor Boundary</b><br>h_g: %{{x:.1f}} {h_u4}<br>P: %{{y:.2f}} {p_u4}<extra></extra>"
        ))
    add_state_marker(fig4, conv(state['H']/1000, 'H'), conv(state['P']/100000, 'P'))    
    ph_layout = layout_common_grid.copy()
    ph_layout.update(
        title='P-h Diagram',
        uirevision='fig4_ph',
        xaxis=dict(title=axis_title('Enthalpy', 'H'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
        yaxis=dict(type='log', title=axis_title('Pressure', 'P'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
    )
    fig4.update_layout(**ph_layout)
    
    st.plotly_chart(fig4, use_container_width=True, config=plot_config, key="fig4_ph")
g5, g6 = st.container(key="steam_graph_row3").columns(2)
with g5:
    fig5 = go.Figure()
    h_u5 = disp_unit('H')
    t_u5 = disp_unit('T')
    p_u5 = disp_unit('P')   
    for P_bar in pressures:
        Hs, Ts = gen_isobar_HT(fluid, P_bar * 100000, T_tuple)
        if Hs:
            P_disp5 = conv(P_bar, 'P')
            fig5.add_trace(go.Scatter(
                x=conv(np.array(Hs), 'H'), y=conv(np.array(Ts), 'T'), mode='lines',
                line=dict(color=tc()['isobar'], width=2),
                showlegend=False,
                hovertemplate=f"<b>Isobar ({P_disp5:.1f} {p_u5})</b><br>h: %{{x:.1f}} {h_u5}<br>T: %{{y:.1f}} {t_u5}<extra></extra>"
            ))   
    Hs_state, Ts_state = gen_isobar_HT(fluid, state['P'], T_tuple)
    if Hs_state:
        P_state_disp5 = conv(state['P']/100000, 'P')
        fig5.add_trace(go.Scatter(
            x=conv(np.array(Hs_state), 'H'), y=conv(np.array(Ts_state), 'T'), mode='lines',
            line=dict(color=tc()['state'], width=3),
            name=f"State Isobar ({P_state_disp5:.2f} {p_u5})",
            hovertemplate=f"<b>State Isobar ({P_state_disp5:.2f} {p_u5})</b><br>h: %{{x:.1f}} {h_u5}<br>T: %{{y:.1f}} {t_u5}<extra></extra>"
        ))   
    if dome is not None:
        fig5.add_trace(go.Scatter(
            x=conv(np.array(dome['hf']), 'H'), y=conv(np.array(dome['T']), 'T'), mode='lines', line=dict(color=tc()['dome_liq'], width=3.5), showlegend=False,
            hovertemplate=f"<b>Sat Liquid Boundary</b><br>h_f: %{{x:.1f}} {h_u5}<br>T: %{{y:.1f}} {t_u5}<extra></extra>"
        ))
        fig5.add_trace(go.Scatter(
            x=conv(np.array(dome['hg']), 'H'), y=conv(np.array(dome['T']), 'T'), mode='lines', line=dict(color=tc()['dome_vap'], width=3.5), showlegend=False,
            hovertemplate=f"<b>Sat Vapor Boundary</b><br>h_g: %{{x:.1f}} {h_u5}<br>T: %{{y:.1f}} {t_u5}<extra></extra>"
        ))
    add_state_marker(fig5, conv(state['H']/1000, 'H'), conv(state['T']-273.15, 'T'))
    th_layout = layout_common_grid.copy()
    th_layout.update(
        title='T-h Diagram',
        uirevision='fig5_th',
        xaxis=dict(title=axis_title('Enthalpy', 'H'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
        yaxis=dict(title=axis_title('Temperature', 'T'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
    )
    fig5.update_layout(**th_layout)
    st.plotly_chart(fig5, use_container_width=True, config=plot_config, key="fig5_th")
with g6:
    fig6 = go.Figure()
    s_u6 = disp_unit('S')
    h_u6 = disp_unit('H')
    t_u6 = disp_unit('T')
    p_u6 = disp_unit('P')
    for P_bar in pressures:
        Ss, Hs = gen_isobar_SH(fluid, P_bar * 100000, T_tuple)
        if Ss:
            P_disp6 = conv(P_bar, 'P')
            fig6.add_trace(go.Scatter(
                x=conv(np.array(Ss), 'S'), y=conv(np.array(Hs), 'H'), mode='lines',
                line=dict(color=tc()['isobar'], width=2),
                showlegend=False,
                hovertemplate=f"<b>Isobar ({P_disp6:.1f} {p_u6})</b><br>s: %{{x:.3f}} {s_u6}<br>h: %{{y:.1f}} {h_u6}<extra></extra>"
            )) 
    for T_c in temperatures:
        Ss, Hs = gen_isotherm_SH(fluid, T_c + 273.15, P_tuple)
        if Ss:
            T_disp6 = conv(T_c, 'T')
            fig6.add_trace(go.Scatter(
                x=conv(np.array(Ss), 'S'), y=conv(np.array(Hs), 'H'), mode='lines',
                line=dict(color='rgba(239, 68, 68, 0.5)', width=2, dash='dot'),
                showlegend=False,
                hovertemplate=f"<b>Isotherm ({T_disp6:.0f}{t_u6})</b><br>s: %{{x:.3f}} {s_u6}<br>h: %{{y:.1f}} {h_u6}<extra></extra>"
            ))
    if dome is not None:
        Ss_out, Hs_out = gen_isotherm_SH(fluid, max(dome['T']) + 273.15 + 20.0, P_tuple)
        if Ss_out:
            fig6.add_trace(go.Scatter(
                x=conv(np.array(Ss_out), 'S'), y=conv(np.array(Hs_out), 'H'), mode='lines',
                line=dict(color=tc()['supercrit'], width=2, dash='dot'),
                name='Border Outside Dome',
                hovertemplate=f"<b>Border Outside Dome</b><br>s: %{{x:.3f}} {s_u6}<br>h: %{{y:.1f}} {h_u6}<extra></extra>"
            )) 
    Ss_state, Hs_state = gen_isobar_SH(fluid, state['P'], T_tuple)
    if Ss_state:
        P_state_disp6 = conv(state['P']/100000, 'P')
        fig6.add_trace(go.Scatter(
            x=conv(np.array(Ss_state), 'S'), y=conv(np.array(Hs_state), 'H'), mode='lines',
            line=dict(color=tc()['state'], width=3),
            name=f"State Isobar ({P_state_disp6:.2f} {p_u6})",
            hovertemplate=f"<b>State Isobar ({P_state_disp6:.2f} {p_u6})</b><br>s: %{{x:.3f}} {s_u6}<br>h: %{{y:.1f}} {h_u6}<extra></extra>"
        ))
    if dome is not None:
        fig6.add_trace(go.Scatter(
            x=conv(np.array(dome['sf']), 'S'), y=conv(np.array(dome['hf']), 'H'), mode='lines', line=dict(color=tc()['dome_liq'], width=3.5), name='Sat Liquid',
            hovertemplate=f"<b>Sat Liquid Boundary</b><br>s_f: %{{x:.3f}} {s_u6}<br>h_f: %{{y:.1f}} {h_u6}<extra></extra>"
        ))
        fig6.add_trace(go.Scatter(
            x=conv(np.array(dome['sg']), 'S'), y=conv(np.array(dome['hg']), 'H'), mode='lines', line=dict(color=tc()['dome_vap'], width=3.5), name='Sat Vapor',
            hovertemplate=f"<b>Sat Vapor Boundary</b><br>s_g: %{{x:.3f}} {s_u6}<br>h_g: %{{y:.1f}} {h_u6}<extra></extra>"
        ))
    add_state_marker(fig6, conv(state['S']/1000, 'S'), conv(state['H']/1000, 'H'))
    h_s_layout = layout_common_grid.copy()
    h_s_layout.update(
        title='Mollier Diagram (h-s)',
        uirevision='fig6_hs',
        xaxis=dict(title=axis_title('Entropy', 'S'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text'])),
        yaxis=dict(title=axis_title('Enthalpy', 'H'), showgrid=True, gridcolor=tc()['grid'], showline=True, linecolor=tc()['label_text'], mirror=True, tickfont=dict(color=tc()['label_text']), title_font=dict(color=tc()['label_text']))
    )
    fig6.update_layout(**h_s_layout)
    st.plotly_chart(fig6, use_container_width=True, config=plot_config, key="fig6_hs")
render_footer()
