"""
Visualization utilities for the Consultoria App.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional

from config import CHART_COLORS, ASSET_CLASS_NAMES


def create_allocation_pie_chart(
    allocation: pd.Series,
    title: str = "Alocação por Classe"
) -> go.Figure:
    """
    Create a pie chart for allocation breakdown.
    
    Parameters
    ----------
    allocation : pd.Series
        Allocation values indexed by class name
    title : str
        Chart title
        
    Returns
    -------
    go.Figure
        Plotly figure
    """
    # Map colors
    colors = [CHART_COLORS.get(cls, '#95A5A6') for cls in allocation.index]
    
    # Map display names
    labels = [ASSET_CLASS_NAMES.get(cls, cls) for cls in allocation.index]
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=allocation.values,
        marker_colors=colors,
        hole=0.4,
        textinfo='label+percent',
        textposition='outside'
    )])
    
    fig.update_layout(
        title=title,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(t=50, b=50, l=50, r=50)
    )
    
    return fig


def create_allocation_comparison_chart(
    current: pd.Series,
    target: pd.Series,
    title: str = "Atual vs Alvo"
) -> go.Figure:
    """
    Create a comparison bar chart for current vs target allocation.
    
    Parameters
    ----------
    current : pd.Series
        Current allocation percentages
    target : pd.Series
        Target allocation percentages
    title : str
        Chart title
        
    Returns
    -------
    go.Figure
        Plotly figure
    """
    # Combine indices
    all_classes = current.index.union(target.index)
    
    current = current.reindex(all_classes, fill_value=0)
    target = target.reindex(all_classes, fill_value=0)
    
    labels = [ASSET_CLASS_NAMES.get(cls, cls) for cls in all_classes]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Atual',
        x=labels,
        y=current.values * 100,
        marker_color='#3498DB'
    ))
    
    fig.add_trace(go.Bar(
        name='Alvo',
        x=labels,
        y=target.values * 100,
        marker_color='#E74C3C',
        opacity=0.7
    ))
    
    fig.update_layout(
        title=title,
        barmode='group',
        yaxis_title='Percentual (%)',
        xaxis_title='Classe de Ativos',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


def create_portfolio_evolution_chart(
    evolution: pd.DataFrame,
    title: str = "Evolução do Patrimônio"
) -> go.Figure:
    """
    Create a line chart for portfolio evolution over time.
    
    Parameters
    ----------
    evolution : pd.DataFrame
        Portfolio values over time (index=date, columns=customers or total)
    title : str
        Chart title
        
    Returns
    -------
    go.Figure
        Plotly figure
    """
    fig = px.line(
        evolution,
        x=evolution.index,
        y=evolution.columns,
        title=title
    )
    
    fig.update_layout(
        xaxis_title='Data',
        yaxis_title='Valor (R$)',
        legend_title='',
        hovermode='x unified'
    )
    
    # Format y-axis as currency
    fig.update_yaxes(tickprefix='R$ ', tickformat=',.0f')
    
    return fig


def create_rebalancing_waterfall(
    suggestions: pd.DataFrame,
    current_allocation: pd.Series,
    title: str = "Impacto do Rebalanceamento"
) -> go.Figure:
    """
    Create a waterfall chart showing rebalancing impact.
    
    Parameters
    ----------
    suggestions : pd.DataFrame
        Rebalancing suggestions
    current_allocation : pd.Series
        Current allocation values
    title : str
        Chart title
        
    Returns
    -------
    go.Figure
        Plotly figure
    """
    fig = go.Figure(go.Waterfall(
        name="Rebalanceamento",
        orientation="v",
        measure=["relative"] * len(suggestions) + ["total"],
        x=list(suggestions['subclasse']) + ["Total"],
        y=list(suggestions['sugestao_valor']) + [suggestions['sugestao_valor'].sum()],
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#2ECC71"}},
        decreasing={"marker": {"color": "#E74C3C"}},
        totals={"marker": {"color": "#3498DB"}}
    ))
    
    fig.update_layout(
        title=title,
        yaxis_title="Valor (R$)",
        showlegend=False
    )
    
    return fig


def create_asset_treemap(
    positions: pd.DataFrame,
    value_col: str = 'valor_liquido',
    title: str = "Composição da Carteira"
) -> go.Figure:
    """
    Create a treemap visualization of portfolio composition.
    
    Parameters
    ----------
    positions : pd.DataFrame
        Position data with classe, subclasse, and value columns
    value_col : str
        Column name for values
    title : str
        Chart title
        
    Returns
    -------
    go.Figure
        Plotly figure
    """
    # Prepare data
    treemap_data = positions.groupby(['classe', 'subclasse', 'nome'])[value_col].sum().reset_index()
    treemap_data = treemap_data[treemap_data[value_col] > 0]
    
    fig = px.treemap(
        treemap_data,
        path=['classe', 'subclasse', 'nome'],
        values=value_col,
        title=title,
        color='classe',
        color_discrete_map=CHART_COLORS
    )
    
    fig.update_traces(
        textinfo='label+value+percent root',
        texttemplate='%{label}<br>R$ %{value:,.2f}<br>%{percentRoot:.1%}'
    )
    
    fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    
    return fig


def create_broker_distribution_chart(
    positions: pd.DataFrame,
    value_col: str = 'valor_liquido',
    title: str = "Distribuição por Corretora"
) -> go.Figure:
    """
    Create a chart showing distribution across brokers.
    
    Parameters
    ----------
    positions : pd.DataFrame
        Position data with corretora column
    value_col : str
        Column name for values
    title : str
        Chart title
        
    Returns
    -------
    go.Figure
        Plotly figure
    """
    broker_totals = positions.groupby('corretora')[value_col].sum()
    
    broker_colors = {
        'XP': '#FFD700',
        'BTG': '#003366',
        'IBKR': '#E31937'
    }
    
    colors = [broker_colors.get(b, '#95A5A6') for b in broker_totals.index]
    
    fig = go.Figure(data=[go.Pie(
        labels=broker_totals.index,
        values=broker_totals.values,
        marker_colors=colors,
        hole=0.3,
        textinfo='label+percent+value',
        texttemplate='%{label}<br>R$ %{value:,.2f}<br>%{percent}'
    )])
    
    fig.update_layout(
        title=title,
        showlegend=True
    )
    
    return fig
