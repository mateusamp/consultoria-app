"""
Startup module for Consultoria App.

Handles private dependency installation and authentication.
Must be imported before any modules that depend on finlib.
"""
import subprocess
import sys


def install_finlib():
    """Install finlib from private GitHub repo if not already installed.

    Uses no Streamlit rendering commands so it can run before st.set_page_config.
    """
    try:
        import finlib  # noqa: F401
    except ImportError:
        import streamlit as st

        token = st.secrets.get("GITHUB_TOKEN", "")
        if not token:
            raise RuntimeError(
                "GITHUB_TOKEN not found in Streamlit secrets. "
                "Cannot install finlib."
            )
        subprocess.check_call(
            [
                sys.executable, "-m", "pip", "install",
                f"git+https://{token}@github.com/mateusamp/finlib.git",
            ],
            stdout=subprocess.DEVNULL,
        )
        st.rerun()


def check_auth():
    """Gate the app behind a simple password check.

    Call this AFTER st.set_page_config.
    """
    import streamlit as st

    if st.session_state.get("authenticated"):
        return

    st.title("Login")
    password = st.text_input("Password", type="password")
    if password:
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


# Run finlib installation on module import (before anything else imports finlib)
install_finlib()
