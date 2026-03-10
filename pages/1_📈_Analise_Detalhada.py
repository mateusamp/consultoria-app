"""
Detailed portfolio analysis page with advanced visualizations.
Consolidated single-client analysis with multiple tabs.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import startup  # noqa: F401  Must be first — installs finlib if needed
import streamlit as st
import pandas as pd

from config import GOOGLE_SHEETS_ID, SHEET_ID_RELATIONS
from data_loader import DataLoader, normalize_text, suggest_rebalancing, calculate_allocation_diff, merge_positions_with_relations
from brokers import PositionsFetcher
from visualizations import (
    create_allocation_pie_chart,
    create_allocation_comparison_chart,
    create_asset_treemap,
    create_broker_distribution_chart
)


st.set_page_config(
    page_title="Análise Detalhada - Consultoria",
    page_icon="📈",
    layout="wide"
)

startup.check_auth()


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
    st.title("📈 Análise Detalhada de Carteira")
    
    # Initialize
    loader = DataLoader()
    customers = loader.load_customers()
    relations = loader.load_relations()
    targets = loader.load_targets()
    
    if customers.empty:
        st.error("Não foi possível carregar os dados.")
        return
    
    # Customer selector
    customer_names = customers['name'].dropna().sort_values().tolist()
    selected_name = st.selectbox(label="Selecione o cliente", options=customer_names, index=None)
    
    if not selected_name:
        return
    
    customer = customers[customers['name'] == selected_name].iloc[0]
    
    # Customer info header
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("XP ID", int(customer['xp_id']) if pd.notna(customer['xp_id']) else "-")
    with col2:
        btg_id = customer.get('btg_id')
        st.metric("BTG ID", int(btg_id) if pd.notna(btg_id) else "-")
    with col3:
        ibkr_id = customer.get('ibkr_id')
        st.metric("IBKR ID", ibkr_id if pd.notna(ibkr_id) else "-")
    with col4:
        positions_key = f'positions_{selected_name}'
        if st.button("🔄 Atualizar Posições", type="primary") or positions_key not in st.session_state:
            with st.spinner("Carregando posições..."):
                positions = loader.load_customer_positions(customer)
                targets = loader.load_targets()
                
                if positions is not None:
                    st.session_state[positions_key] = positions
                else:
                    st.warning("Nenhuma posição encontrada para este cliente.")
    
    st.divider()
    
    # If we have positions, show tabs
    positions = st.session_state[positions_key]

    if st.toggle("Excluir ativos do Banco Master", key=f"exclude_master_{selected_name}"):
        positions = positions[~(positions.nome.str.lower().str.contains('master') & positions.codigo_ativo.str.startswith('CDB'))]
    
    # Merge with relations
    positions_with_class = merge_positions_with_relations(
        positions, relations, fill_unclassified=False
    )
    
    # Check for unclassified assets
    unclassified = positions_with_class[positions_with_class['classe'].isna()]
    if not unclassified.empty:
        unique_codes = [str(code) for code in unclassified['codigo_ativo'].unique() if pd.notna(code)]
        st.warning(f"⚠️ {len(unclassified)} ativo(s) não classificado(s): {', '.join(unique_codes)}")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            with st.expander("📋 Preview dos ativos não classificados"):
                unique_unclassified = unclassified.drop_duplicates(subset=['codigo_ativo'])
                preview_cols = ['codigo_ativo', 'nome', 'corretora', 'key_xp']
                available_preview = [c for c in preview_cols if c in unique_unclassified.columns]
                st.dataframe(unique_unclassified[available_preview], hide_index=True)
        
        with col2:
            if st.button("➕ Adicionar à Relations"):
                unique_unclassified = unclassified.drop_duplicates(subset=['codigo_ativo'])
                assets_to_add = []
                for _, row in unique_unclassified.iterrows():
                    asset = {
                        'codigo_ativo': row.get('codigo_ativo', ''),
                        'corretora': row.get('corretora', ''),
                        'key_xp': row.get('key_xp', ''),
                        'nome': row.get('nome', ''),
                        'categoria': row.get('categoria', ''),
                        'indexador': row.get('indexador', '')
                    }
                    assets_to_add.append(asset)
                
                if loader.append_to_relations(assets_to_add):
                    st.success(f"✅ {len(assets_to_add)} ativo(s) adicionado(s)!")
                    st.cache_data.clear()
                else:
                    st.error("❌ Erro ao adicionar ativos.")
        
        sheets_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/edit#gid={SHEET_ID_RELATIONS}"  # Replace gid with actual sheet ID for Relations
        st.markdown(f"🔗 [Abrir planilha Relations]({sheets_url})")
    
    # Prepare enriched positions for display
    positions_enriched = merge_positions_with_relations(
        positions, relations, fill_unclassified=True
    )
    positions_enriched['nome'] = positions_enriched['nome'].fillna(positions_enriched['codigo_ativo'])
    positions_enriched['classe'] = positions_enriched['classe'].replace('', 'não_classificado')
    positions_enriched['subclasse'] = positions_enriched['subclasse'].replace('', 'não_classificado')
    
    total_value = positions_enriched['valor_liquido'].sum()
    total_gross_value = positions_enriched['valor_bruto'].sum()
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs([
        "📊 Posições",
        "🔄 Rebalanceamento",
        "🥧 Visualizações"
    ])
    
    with tab1:
        show_positions_tab(positions_enriched, positions, relations, total_value, total_gross_value, selected_name, targets, loader)
    
    with tab2:
        show_rebalancing_tab(selected_name, positions, relations, targets, loader, total_value)
    
    with tab3:
        show_visualizations_tab(positions_enriched, total_value, customers, selected_name, targets, loader)


def show_positions_tab(positions_enriched: pd.DataFrame, positions: pd.DataFrame, 
                       relations: pd.DataFrame, total_value: float, total_gross_value: float,
                       selected_name: str, targets: pd.DataFrame, loader: DataLoader):
    """Show positions table, comparison with target, and detailed breakdown."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Patrimônio Total Bruto", format_currency(total_gross_value))
    with col2:
        st.metric("Patrimônio Total Líquido", format_currency(total_value))
        n_assets = len(positions_enriched)
    with col3:
        st.metric("Total de Ativos", n_assets)
    with col4:
        n_brokers = positions_enriched['corretora'].nunique()
        st.metric("Corretoras", n_brokers)
    
    # Comparison with target allocation
    st.markdown("---")
    st.subheader("Comparação Atual vs Alvo")
    
    customer_targets = loader.get_customer_targets(selected_name, targets)
    
    if not customer_targets.empty:
        positions_with_class = merge_positions_with_relations(
            positions, relations, fill_unclassified=True
        )
        
        # Normalize class names
        for col in ['classe', 'subclasse']:
            if col in positions_with_class.columns:
                positions_with_class[col] = positions_with_class[col].apply(normalize_text)
        
        # Calculate allocation difference
        diff = calculate_allocation_diff(positions_with_class, customer_targets.copy(), total_value)
        
        # Add valor_atual column if not present
        if 'valor_atual' not in diff.columns:
            diff['valor_atual'] = diff['pct_atual'] * total_value
        
        # Add actual values to comparison
        comparison_display = diff[['classe', 'subclasse', 'target', 'pct_atual', 'valor_atual', 'diferenca_pct', 'diferenca_valor']].copy()
        comparison_display.columns = ['Classe', 'Subclasse', 'Alvo %', 'Atual %', 'Valor Atual', 'Diferença %', 'Diferença R$']
        
        # for col in ['Alvo %', 'Atual %', 'Diferença %']:
        #     comparison_display[col] = comparison_display[col].apply(format_percentage)
        # for col in ['Valor Atual', 'Diferença R$']:
        #     comparison_display[col] = comparison_display[col].apply(format_currency)
        
        st.dataframe(
            comparison_display.style.format(
                subset=['Valor Atual', 'Diferença R$'],
                formatter=format_currency,
        ).format(
                subset=['Alvo %', 'Atual %', 'Diferença %'],
                formatter=format_percentage,
        ),
            width='stretch',
            height='content',
            hide_index=True
            )
    else:
        st.info("Sem alocação alvo definida para este cliente.")
    
    # Detailed breakdown by class
    st.divider()
    st.subheader("Detalhamento por Classe e Subclasse")
    
    for classe in sorted(positions_enriched['classe'].unique()):
        class_data = positions_enriched[positions_enriched['classe'] == classe]
        class_total_net = class_data['valor_liquido'].sum()
        class_total_gross = class_data['valor_bruto'].sum()
        class_pct = class_total_net / total_value * 100
        
        with st.expander(f"**{classe.upper()}** - {format_currency(class_total_net)} ({class_pct:.1f}%)"):
            display_cols = ['nome', 'codigo_ativo', 'valor_bruto', 'valor_liquido', 'subclasse', 'corretora']
            available_cols = [c for c in display_cols if c in class_data.columns]
            
            display_df = class_data[available_cols].copy()
            
            # Format currency columns
            for col in ['valor_bruto', 'valor_liquido']:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(format_currency)
            
            display_df.columns = ['Nome', 'Código', 'Valor Bruto', 'Valor Líquido', 'Subclasse', 'Corretora'][:len(available_cols)]
            
            st.dataframe(display_df, width='stretch', hide_index=True)

def show_visualizations_tab(positions_enriched: pd.DataFrame, total_value: float, 
                            customers: pd.DataFrame, selected_name: str, 
                            targets: pd.DataFrame, loader: DataLoader):
    """Show visualization charts."""
    st.subheader("Visualizações Interativas")
    
    subtab1, subtab2, subtab3, subtab4 = st.tabs([
        "🥧 Alocação",
        "📊 Comparativo",
        "🌳 Treemap",
        "🏦 Por Corretora"
    ])
    
    with subtab1:
        allocation = positions_enriched.groupby('classe')['valor_liquido'].sum()
        fig = create_allocation_pie_chart(allocation)
        st.plotly_chart(fig, width='stretch')
    
    with subtab2:
        customer_targets = loader.get_customer_targets(selected_name, targets)
        
        if not customer_targets.empty:
            allocation = positions_enriched.groupby('classe')['valor_liquido'].sum()
            current_pct = (allocation / total_value)
            target_pct = customer_targets.groupby('classe')['target'].sum() / 100
            
            fig = create_allocation_comparison_chart(current_pct, target_pct)
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Sem alocação alvo definida para este cliente.")
    
    with subtab3:
        fig = create_asset_treemap(positions_enriched)
        st.plotly_chart(fig, width='stretch')
    
    with subtab4:
        fig = create_broker_distribution_chart(positions_enriched)
        st.plotly_chart(fig, width='stretch')

def show_rebalancing_tab(selected_name: str, positions: pd.DataFrame,
                         relations: pd.DataFrame, targets: pd.DataFrame,
                         loader: DataLoader, total_value: float):
    """Show rebalancing suggestions."""
    customer_targets = loader.get_customer_targets(selected_name, targets)
    
    if customer_targets.empty:
        st.warning(f"Não foi encontrada uma alocação alvo para {selected_name}.")
        return
    
    st.subheader("Sugestão de Rebalanceamento")
    
    positions_with_class = merge_positions_with_relations(
        positions, relations, fill_unclassified=True
    )
    
    # Normalize class names
    for col in ['classe', 'subclasse']:
        if col in positions_with_class.columns:
            positions_with_class[col] = positions_with_class[col].apply(normalize_text)
    
    # Investment amount input
    col1, col2 = st.columns(2)
    
    with col1:
        amount_to_invest = st.number_input(
            "Valor a investir (R$)",
            min_value=0.0,
            value=10000.0,
            step=1000.0,
            format="%.2f"
        )
    
    with col2:
        n_suggestions = st.slider(
            "Número de sugestões",
            min_value=1,
            max_value=5,
            value=3
        )
    
    # Calculate suggestions
    diff = calculate_allocation_diff(positions_with_class, customer_targets.copy(), total_value)
    suggestions = suggest_rebalancing(diff, amount_to_invest, n_suggestions)
    
    if suggestions.empty:
        st.success("🎉 Carteira está balanceada! Não há sugestões de rebalanceamento.")
    else:
        st.divider()
        
        suggestions_display = suggestions.copy()
        suggestions_display.columns = ['Classe', 'Subclasse', 'Gap no Portfólio', 'Sugestão de Aporte']
        suggestions_display['Gap no Portfólio'] = suggestions_display['Gap no Portfólio'].apply(format_currency)
        suggestions_display['Sugestão de Aporte'] = suggestions_display['Sugestão de Aporte'].apply(format_currency)
        
        st.dataframe(suggestions_display, width='stretch', hide_index=True)





if __name__ == "__main__":
    main()
