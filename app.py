"""
Consultoria App - Main Streamlit Application

A financial advisor app for consolidating and analyzing customer positions
across multiple brokers (XP, BTG, IBKR).
"""
import startup  # noqa: F401  Must be first — installs finlib if needed

import streamlit as st
import pandas as pd
import numpy as np
from unidecode import unidecode

# Page configuration — must be the first Streamlit rendering command
st.set_page_config(
    page_title="Consultoria - Análise de Carteiras",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

startup.check_auth()

from config import ASSET_CLASS_NAMES, SUBCLASS_NAMES, CHART_COLORS
from data_loader import DataLoader
from brokers import PositionsFetcher

@st.cache_resource
def get_data_loader():
    """Get cached data loader instance."""
    return DataLoader()


@st.cache_resource
def get_positions_fetcher():
    """Get cached positions fetcher instance."""
    return PositionsFetcher()


def format_currency(value: float, prefix: str = "R$") -> str:
    """Format value as Brazilian currency."""
    if pd.isna(value):
        return "-"
    return f"{prefix} {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_percentage(value: float) -> str:
    """Format value as percentage."""
    if pd.isna(value):
        return "-"
    return f"{value:.2%}".replace(".", ",")


def main():
    """Main application."""   
    # Load base data
    loader = get_data_loader()
    customers = loader.load_customers()
    relations = loader.load_relations()
    targets = loader.load_targets()
    
    if customers.empty:
        st.error("Não foi possível carregar os dados de clientes. Verifique a configuração.")
        return
    
    # Show overview
    show_overview(customers, relations, targets, loader)


def show_overview(customers: pd.DataFrame, relations: pd.DataFrame, targets: pd.DataFrame, loader: DataLoader):
    """Show overview page."""
    st.markdown('<p class="main-header">📊 Visão Geral</p>', unsafe_allow_html=True)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Clientes", len(customers))
    
    with col2:
        xp_clients = customers['xp_id'].notna().sum()
        st.metric("Clientes XP", xp_clients)
    
    with col3:
        btg_clients = customers['btg_id'].notna().sum() if 'btg_id' in customers.columns else 0
        st.metric("Clientes BTG", btg_clients)
    
    with col4:
        ibkr_clients = customers['ibkr_id'].notna().sum() if 'ibkr_id' in customers.columns else 0
        st.metric("Clientes IBKR", ibkr_clients)
    
    st.divider()
    
    # Load all positions button
    if st.button("📥 Carregar Todas as Posições", type="primary"):
        with st.spinner("Carregando posições..."):
            positions_by_customer = {}
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, customer in customers.iterrows():
                status_text.text(f"Carregando posições de {customer['name']}...")
                try:
                    positions = loader.load_customer_positions(customer)
                    if positions is not None and not positions.empty:
                        positions_by_customer[customer['name']] = positions
                except Exception as e:
                    st.warning(f"Erro ao carregar posições de {customer['name']}: {e}")
                
                progress_bar.progress((i + 1) / len(customers), text=f"{i + 1}/{len(customers)}")
            
            progress_bar.empty()
            status_text.empty()
            
            # Store in session state
            st.session_state['all_positions'] = positions_by_customer
            st.success(f"✅ Posições carregadas para {len(positions_by_customer)} cliente(s)")
            st.rerun()
    
        
    # Calculate totals if positions are loaded
    customer_totals = None
    if 'all_positions' in st.session_state:
        totals_list = []
        for name, positions in st.session_state['all_positions'].items():
            total_gross = positions['valor_bruto'].sum()
            total_net = positions['valor_liquido'].sum()
            totals_list.append({
                'name': name,
                'patrimonio_bruto': total_gross,
                'patrimonio_liquido': total_net
            })
        
        if totals_list:
            customer_totals = pd.DataFrame(totals_list)
            
        #     # Display aggregated metrics
        #     col1, col2, col3, col4 = st.columns(4)
        #     with col1:
        #         total_clients = len(customer_totals)
        #         st.metric("Clientes com Posições", total_clients)
        #     with col2:
        #         total_gross = customer_totals['patrimonio_bruto'].sum()
        #         st.metric("Patrimônio Total Bruto", format_currency(total_gross))
        #     with col3:
        #         total_net = customer_totals['patrimonio_liquido'].sum()
        #         st.metric("Patrimônio Total Líquido", format_currency(total_net))
        #     with col4:
        #         # Calculate total monthly payment (will be computed after merge)
        #         st.metric("Consultoria Mensais Totais", "-")
            
    # st.divider()
    
    # Format customer table
    base_cols = ['name', 'xp_id', 'btg_id', 'ibkr_id', 'start_date', 'tax', 'monthly_min']
    display_customers = customers[base_cols].copy()
    
    # Merge with totals if available
    if customer_totals is not None:
        display_customers = display_customers.merge(
            customer_totals[['name', 'patrimonio_bruto', 'patrimonio_liquido']], 
            on='name', 
            how='left'
        )
        
        # Calculate monthly payment: max(tax * gross_worth, monthly_min)
        display_customers['consultoria_mensal'] = display_customers.apply(
            lambda row: max(
                row['tax'] * row['patrimonio_bruto'] / 12 if pd.notna(row['tax']) and pd.notna(row['patrimonio_bruto']) else 0,
                row['monthly_min'] if pd.notna(row['monthly_min']) else 0
            ) if pd.notna(row['patrimonio_bruto']) else np.nan,
            axis=1
        )
        
        # Update the total monthly payment metric
        total_monthly = display_customers['consultoria_mensal'].sum()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            total_clients = len(customer_totals)
            st.metric("Clientes com Posições", total_clients)
        with col2:
            total_gross = customer_totals['patrimonio_bruto'].sum()
            st.metric("Patrimônio Total Bruto", format_currency(total_gross))
        with col3:
            total_net = customer_totals['patrimonio_liquido'].sum()
            st.metric("Patrimônio Total Líquido", format_currency(total_net))
        with col4:
            st.metric("Consultoria Mensal Total", format_currency(total_monthly))
        
        st.divider()
        
        display_customers.columns = ['Nome', 'XP ID', 'BTG ID', 'IBKR ID', 'Data Início', 'Taxa %', 'Mínimo Mensal', 'Patrimônio Bruto', 'Patrimônio Líquido', 'Consultoria Mensal']
    else:
        display_customers.columns = ['Nome', 'XP ID', 'BTG ID', 'IBKR ID', 'Data Início', 'Taxa %', 'Mínimo Mensal']
    
    # Customer list
    st.subheader("Lista de Clientes")
    
    st.dataframe(
        display_customers.style.format(
            subset=['Patrimônio Bruto', 'Patrimônio Líquido', 'Consultoria Mensal'] if customer_totals is not None else [],
            formatter=format_currency,
        ).format(
            subset=['Taxa %'],
            formatter=lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-"
        ).format(
            subset=['Mínimo Mensal'],
            formatter=lambda x: format_currency(x) if pd.notna(x) else "-"
        ).format(
            subset=['XP ID', 'BTG ID'],
            formatter=lambda x: int(x) if pd.notna(x) else None
        ),
        width='stretch',
        hide_index=True,
    )
    
    # Asset relations summary
    st.markdown("---")
    st.subheader("Relações de Ativos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Distribuição por Classe**")
        if not relations.empty and 'classe' in relations.columns:
            class_counts = relations['classe'].value_counts()
            st.bar_chart(class_counts)
    
    with col2:
        st.write("**Distribuição por Corretora**")
        if not relations.empty and 'corretora' in relations.columns:
            broker_counts = relations['corretora'].value_counts()
            st.bar_chart(broker_counts)


if __name__ == "__main__":
    main()

