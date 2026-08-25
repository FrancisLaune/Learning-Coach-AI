"""Global Streamlit page configuration and styles."""

from __future__ import annotations

import streamlit as st

from core.version import __version__

GLOBAL_STYLES = """
<style>
.block-container {padding-top:1.3rem;padding-bottom:3rem;}
.hero {
  padding:1.4rem 1.6rem;border-radius:18px;
  background:linear-gradient(135deg,#edf4ff,#fafcff);
  border:1px solid #dce7f5;margin-bottom:1rem;
}
.card {
  padding:1rem;border:1px solid #e2e8f0;border-radius:14px;
  background:white;margin-bottom:.7rem;
}
.small {color:#64748b;font-size:.9rem}
*:focus-visible {outline:3px solid #1d4ed8;outline-offset:3px;}
/* Action buttons — 3D light blue, readable dark text */
div[data-testid="stButton"] > button,
div[data-testid="stFormSubmitButton"] > button {
  border: 1px solid #7dd3fc !important;
  border-radius: 12px !important;
  background: linear-gradient(180deg, #e0f2fe 0%, #7dd3fc 55%, #38bdf8 100%) !important;
  color: #0c4a6e !important;
  font-weight: 700 !important;
  box-shadow: 0 4px 0 #0284c7, 0 8px 16px rgba(14,165,233,.22) !important;
  transition: transform .08s ease, box-shadow .08s ease, filter .08s ease !important;
}
div[data-testid="stButton"] > button:hover,
div[data-testid="stFormSubmitButton"] > button:hover {
  filter: brightness(1.04) !important;
  color: #082f49 !important;
}
div[data-testid="stButton"] > button:active,
div[data-testid="stFormSubmitButton"] > button:active {
  transform: translateY(2px) !important;
  box-shadow: 0 2px 0 #0284c7, 0 4px 10px rgba(14,165,233,.2) !important;
}
div[data-testid="stButton"] > button p,
div[data-testid="stFormSubmitButton"] > button p {
  color: #0c4a6e !important;
  font-weight: 700 !important;
}
@media (max-width: 900px) {
  .block-container {padding-left:1rem;padding-right:1rem;}
  [data-testid="stHorizontalBlock"] {flex-wrap:wrap;}
  [data-testid="column"] {min-width:16rem;}
}
@media (prefers-contrast: more) {
  .card,.hero {border:2px solid currentColor;background:white;}
}
</style>
"""


def configure_page() -> None:
    """Apply the existing page metadata without changing the rendered UI."""
    st.set_page_config(
        page_title=f"Learning Coach AI {__version__}",
        page_icon="🎓",
        layout="wide",
    )


def render_global_styles() -> None:
    """Render the existing global CSS."""
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)
