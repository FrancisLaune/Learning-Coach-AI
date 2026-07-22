"""Global Streamlit page configuration and styles."""

from __future__ import annotations

import streamlit as st

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
</style>
"""


def configure_page() -> None:
    """Apply the existing page metadata without changing the rendered UI."""
    st.set_page_config(
        page_title="Objectif Brevet 2027 – V7.0",
        page_icon="🎓",
        layout="wide",
    )


def render_global_styles() -> None:
    """Render the existing global CSS."""
    st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)
