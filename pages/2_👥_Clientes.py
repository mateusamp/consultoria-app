"""
Customer management page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import startup  # noqa: F401  Must be first — installs finlib if needed
import streamlit as st
import pandas as pd

from data_loader import DataLoader


st.set_page_config(
    page_title="Clientes - Consultoria",
    page_icon="👥",
    layout="wide"
)

startup.check_auth()


def format_currency(value):
    """Format value as Brazilian currency."""
    if pd.isna(value) or value == '':
        return "-"
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(value)


def main():
    st.title("👥 Gestão de Clientes")
    
    loader = DataLoader()
    customers = loader.load_customers()
    
    if customers.empty:
        st.error("Não foi possível carregar os clientes.")
        return
    
    st.markdown("---")
    
    # Search and filter
    col1, col2 = st.columns(2)
    
    with col1:
        search = st.text_input("🔍 Buscar cliente")
    
    with col2:
        show_inactive = st.checkbox("Mostrar clientes sem ID XP")
    
    # Apply filters
    filtered = customers.copy()
    
    if search:
        filtered = filtered[
            filtered['name'].str.contains(search, case=False, na=False)
        ]
    
    if not show_inactive:
        filtered = filtered[filtered['xp_id'].notna()]
    
    # Display
    st.subheader(f"Clientes ({len(filtered)})")
    
    # Format for display
    display_df = filtered.copy()
    
    if 'last_value' in display_df.columns:
        display_df['last_value'] = display_df['last_value'].apply(format_currency)
    
    if 'tax' in display_df.columns:
        display_df['tax'] = display_df['tax'].apply(
            lambda x: f"{float(x)*100:.2f}%".replace(".", ",") if pd.notna(x) and x != '' else "-"
        )
    
    display_cols = ['name', 'xp_id', 'btg_id', 'ibkr_id', 'tax', 'start_date', 'last_value']
    available_cols = [c for c in display_cols if c in display_df.columns]
    
    st.dataframe(
        display_df[available_cols],
        width='stretch',
        hide_index=True,
        column_config={
            'name': st.column_config.TextColumn('Nome', width='large'),
            'xp_id': st.column_config.NumberColumn('XP ID', format='%d'),
            'btg_id': st.column_config.NumberColumn('BTG ID', format='%d'),
            'ibkr_id': st.column_config.TextColumn('IBKR ID'),
            'tax': st.column_config.TextColumn('Taxa'),
            'start_date': st.column_config.DateColumn('Início'),
            'last_value': st.column_config.TextColumn('Último Valor'),
        }
    )
    
    # Statistics
    st.markdown("---")
    st.subheader("📊 Estatísticas")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Clientes", len(customers))
    
    with col2:
        xp_count = customers['xp_id'].notna().sum()
        st.metric("Clientes XP", xp_count)
    
    with col3:
        btg_count = customers['btg_id'].notna().sum() if 'btg_id' in customers.columns else 0
        st.metric("Clientes BTG", btg_count)
    
    with col4:
        ibkr_count = customers['ibkr_id'].notna().sum() if 'ibkr_id' in customers.columns else 0
        st.metric("Clientes IBKR", ibkr_count)
    
    # Recent customers
    if 'start_date' in customers.columns:
        st.markdown("---")
        st.subheader("🆕 Clientes Recentes")
        
        recent = customers.dropna(subset=['start_date']).copy()
        recent = recent.sort_values('start_date', ascending=False).head(10)
        
        st.dataframe(
            recent[['name', 'start_date']].rename(columns={'name': 'Nome', 'start_date': 'Data Início'}),
            hide_index=True,
            width='stretch'
        )
    
    # Target allocations
    st.markdown("---")
    st.subheader("🎯 Alocações Alvo Disponíveis")
    
    targets = loader.load_targets()
    
    # Count targets per customer
    if not targets.empty:
        targets_summary = targets.groupby('nome').size().reset_index(name='Quantidade de Alvos')
        targets_summary.columns = ['Cliente', 'Quantidade de Alvos']
        st.dataframe(targets_summary, hide_index=True, width='stretch')
    else:
        st.info("Nenhuma alocação alvo cadastrada.")


if __name__ == "__main__":
    main()
