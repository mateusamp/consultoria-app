"""
Configuration settings for the Consultoria App.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Base paths
BASE_DIR = Path(__file__).parent

# Google Sheets configuration
GOOGLE_SHEETS_ID = "1HlKyfENVqKnLmSKLdtHnI7DW6IqAhXH9BgUQSwIK8Tg"
SHEET_ID_CUSTOMERS = "1768766570"
SHEET_ID_RELATIONS = "1095801197"
SHEET_ID_TARGETS = "1439111469"

# IBKR Flex Query configuration
try:
    import streamlit as st
    IBKR_TOKEN = st.secrets.get("IBKR_FLEX_TOKEN", os.getenv("IBKR_FLEX_TOKEN"))
except Exception:
    IBKR_TOKEN = os.getenv("IBKR_FLEX_TOKEN")

IBKR_FLEX_QUERIES = {
    "nav": 1076691,
    "positions": 1145252,
    "trades": 1145281,
    "cash": 1147795,
}

# Asset class display names (Portuguese)
ASSET_CLASS_NAMES = {
    "inflacao": "Inflação",
    "pre": "Pré-fixado",
    "pos_fixado": "Pós-fixado",
    "caixa": "Caixa",
    "renda_variavel": "Renda Variável",
    "internacional": "Internacional",
}

SUBCLASS_NAMES = {
    "emissao_bancaria": "Emissão Bancária",
    "credito_privado": "Crédito Privado",
    "tesouro": "Tesouro",
    "nacional": "Nacional",
    "caixa": "Caixa",
    "renda_variavel": "Renda Variável",
}

# Styling
CHART_COLORS = {
    "inflacao": "#E74C3C",
    "pre": "#3498DB",
    "pos_fixado": "#2ECC71",
    "caixa": "#95A5A6",
    "renda_variavel": "#9B59B6",
    "internacional": "#F39C12",
}
