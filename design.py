"""Graham Nessler design system integration for Receipt Ranger.

Loads bundled CSS overrides and exposes helpers for rendering brand assets
(receipt logo, sun/moon icons) and theme-toggling.
"""

from __future__ import annotations

import os

import streamlit as st

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_ASSETS_DIR = os.path.join(_PROJECT_ROOT, "assets")

_OVERRIDES_CSS_PATH = os.path.join(_ASSETS_DIR, "streamlit_overrides.css")
_LOGO_SVG_PATH = os.path.join(_ASSETS_DIR, "logo-receipt.svg")


def _load_overrides_css() -> str:
    with open(_OVERRIDES_CSS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _load_logo_svg() -> str:
    with open(_LOGO_SVG_PATH, "r", encoding="utf-8") as f:
        return f.read()


def get_logo_svg() -> str:
    """Return the inline receipt-logo SVG."""
    return _load_logo_svg()


def get_logo_path() -> str:
    """Return the absolute path to the receipt-logo SVG (for st.set_page_config)."""
    return _LOGO_SVG_PATH


# Theme variables are the ONLY source-of-truth for theme-dependent values;
# the static CSS file does not declare them. We inject the appropriate set
# BEFORE the static CSS so there's no shadowing battle.
_DARK_THEME_VARS = """
:root, html, .stApp {
  --bg:            #0A0A0A;
  --bg-elev-1:     #171717;
  --bg-elev-2:     #262626;
  --bg-tint-red:   rgba(220, 38, 38, 0.10);

  --fg:            #F5F5F5;
  --fg-muted:      #A3A3A3;
  --fg-dim:        #737373;
  --fg-link:       #F87171;
  --fg-link-hover: #D1D5DB;

  --border:        #262626;
  --border-strong: #404040;

  --action-primary-bg:       #F5F5F5;
  --action-primary-bg-hover: #D1D5DB;
  --action-primary-fg:       #0A0A0A;

  --success-bg:     rgba(20, 83, 45, 0.35);
  --success-border: rgba(21, 128, 61, 0.6);
  --success-fg:     #BBF7D0;

  --warning-bg:     rgba(120, 53, 15, 0.35);
  --warning-border: rgba(217, 119, 6, 0.6);
  --warning-fg:     #FCD34D;

  --error-fg:       #F87171;

  --info-bg:        rgba(37, 99, 235, 0.10);
  --info-fg:        #93C5FD;

  color-scheme: dark;
}
"""

_LIGHT_THEME_VARS = """
:root, html, .stApp {
  /* Off-white canvas (silver-100) keeps the screen from being blinding while
     letting cards and the sidebar elevate to pure white. */
  --bg:            #F5F5F5;
  --bg-elev-1:     #FFFFFF;
  --bg-elev-2:     #EAEAEA;
  --bg-tint-red:   rgba(220, 38, 38, 0.06);

  --fg:            #0A0A0A;
  --fg-muted:      #4B5563;
  --fg-dim:        #6B7280;
  --fg-link:       #B91C1C;
  --fg-link-hover: #4B5563;

  --border:        #E5E7EB;
  --border-strong: #D1D5DB;

  --action-primary-bg:       #0A0A0A;
  --action-primary-bg-hover: #1F2937;
  --action-primary-fg:       #FFFFFF;

  --success-bg:     #DCFCE7;
  --success-border: #86EFAC;
  --success-fg:     #166534;

  --warning-bg:     #FEF3C7;
  --warning-border: #FCD34D;
  --warning-fg:     #92400E;

  --error-fg:       #991B1B;

  --info-bg:        #DBEAFE;
  --info-fg:        #1E40AF;

  color-scheme: light;
}
"""


def init_theme() -> None:
    """Ensure session state has a theme key. Defaults to dark."""
    if "theme" not in st.session_state:
        st.session_state.theme = "dark"


def current_theme() -> str:
    return st.session_state.get("theme", "dark")


def toggle_theme() -> None:
    """Flip the active theme between dark and light."""
    st.session_state.theme = "light" if current_theme() == "dark" else "dark"


def inject_design_system() -> None:
    """Inject the GN design-system CSS for the current theme."""
    vars_css = _LIGHT_THEME_VARS if current_theme() == "light" else _DARK_THEME_VARS
    base_css = _load_overrides_css()
    st.markdown(
        f"<style>{vars_css}\n{base_css}</style>",
        unsafe_allow_html=True,
    )
