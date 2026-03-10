"""
Startup module for Consultoria App.

Handles private dependency installation and authentication.
Must be imported before any modules that depend on finlib.
"""
import os
import subprocess
import sys

_FINLIB_TARGET = "/tmp/finlib_packages"


def install_finlib():
    """Install finlib from private GitHub repo if not already installed.

    Installs to /tmp/finlib_packages with --no-deps (transitive deps like
    pandas are already in the venv via requirements.txt) to avoid shadowing
    venv packages. Uses --upgrade so reinstalls on cold starts work cleanly.
    """
    if _FINLIB_TARGET not in sys.path:
        sys.path.insert(0, _FINLIB_TARGET)

    try:
        import finlib  # noqa: F401
        return
    except ImportError:
        pass

    import importlib
    import streamlit as st

    token = st.secrets.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN not found in Streamlit secrets. "
            "Cannot install finlib."
        )
    os.makedirs(_FINLIB_TARGET, exist_ok=True)
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install",
            "--target", _FINLIB_TARGET,
            "--no-deps",
            "--upgrade",
            f"git+https://{token}@github.com/mateusamp/finlib.git",
        ],
        stdout=subprocess.DEVNULL,
    )
    # Clear cached import failures so Python finds the newly installed package
    sys.modules.pop("finlib", None)
    importlib.invalidate_caches()
    import finlib  # noqa: F401


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
