"""
Data loading and management module.

Handles loading customer data, asset relations, and target allocations
from Google Sheets or local Excel file.
"""
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import pandas as pd
import numpy as np
import streamlit as st
from unidecode import unidecode
from brokers import PositionsFetcher

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

from config import GOOGLE_SHEETS_ID


class DataLoader:
    """
    Loads and manages data from Google Sheets.
    """
    
    def __init__(self):
        """
        Initialize the data loader.
        """
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread is required. Install with: pip install gspread google-auth")
        self._gspread_client = None
        self._sheet = None
        
    def _get_gspread_client(self):
        """Get or create gspread client."""
        if self._gspread_client is None:
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            creds = Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]),
                scopes=scope,
            )
            self._gspread_client = gspread.authorize(creds)
            self._sheet = self._gspread_client.open_by_key(GOOGLE_SHEETS_ID)
        return self._gspread_client
    
    def _load_from_gsheets(self, worksheet_name: str) -> pd.DataFrame:
        """Load data from a Google Sheets worksheet."""
        self._get_gspread_client()
        if self._sheet is None:
            raise ValueError("Google Sheets not available")
        
        ws = self._sheet.worksheet(worksheet_name)
        data = ws.get_all_values()
        
        if len(data) < 2:
            return pd.DataFrame()
        
        df = pd.DataFrame(data[1:], columns=data[0])
        return df.replace('', np.nan)
    
    @staticmethod
    def _parse_brazilian_number(value: str) -> float:
        """Parse Brazilian number format (comma as decimal, dot as thousands)."""
        if pd.isna(value) or value == '':
            return np.nan
        if not isinstance(value, str):
            return float(value)
        # Remove currency symbols and spaces
        value = value.replace('R$', '').replace('%', '').strip()
        # Remove thousand separators (dots)
        value = value.replace('.', '')
        # Replace decimal separator (comma) with dot
        value = value.replace(',', '.')
        try:
            return float(value)
        except ValueError:
            return np.nan
    
    @st.cache_data(ttl=3600)
    def load_customers(_self) -> pd.DataFrame:
        """
        Load customer data.
        
        Returns
        -------
        pd.DataFrame
            Customer data with columns: nome, xp, ibkr, btg, taxa, minimo_mensal,
            cpf, ultimo_valor, data_inicial, endereco
        """
        try:
            df = _self._load_from_gsheets('customers')
            
            # Map Portuguese column names to English for internal use
            column_map = {
                'nome': 'name',
                'xp': 'xp_id',
                'ibkr': 'ibkr_id',
                'btg': 'btg_id',
                'taxa': 'tax',
                'minimo_mensal': 'monthly_min',
                'cpf': 'cpf',
                'ultimo_valor': 'last_value',
                'data_inicial': 'start_date',
                'endereco': 'address'
            }
            df = df.rename(columns=column_map)
            
            # Convert types with Brazilian format
            for col in ['xp_id', 'btg_id']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            if 'start_date' in df.columns:
                df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
            
            if 'tax' in df.columns:
                df['tax'] = df['tax'].apply(_self._parse_brazilian_number)
            
            if 'last_value' in df.columns:
                df['last_value'] = df['last_value'].apply(_self._parse_brazilian_number)
            
            if 'monthly_min' in df.columns:
                df['monthly_min'] = df['monthly_min'].apply(_self._parse_brazilian_number)
            
            return df
            
        except Exception as e:
            st.error(f"Error loading customers: {e}")
            return pd.DataFrame()
    
    def load_relations(_self) -> pd.DataFrame:
        """
        Load asset-to-class relations.
        
        Returns
        -------
        pd.DataFrame
            Relations with columns: classe, subclasse, codigo_ativo, corretora,
            key_xp, nome, categoria, indexador
        """
        try:
            df = _self._load_from_gsheets('relations')
            return df
            
        except Exception as e:
            st.error(f"Error loading relations: {e}")
            return pd.DataFrame()
    
    def append_to_relations(self, assets_data: List[Dict]) -> bool:
        """
        Append new assets to the relations sheet.
        
        Parameters
        ----------
        assets_data : list of dict
            List of assets with keys: codigo_ativo, corretora, key_xp, nome
            
        Returns
        -------
        bool
            True if successful
        """
        try:
            self._get_gspread_client()
            ws = self._sheet.worksheet('relations')
            
            # Helper function to convert NaN to empty string
            def clean_value(val):
                if pd.isna(val) or val is None:
                    return ''
                return str(val)
            
            # Prepare rows to append (classe and subclasse will be empty for user to fill)
            rows_to_append = []
            for asset in assets_data:
                row = [
                    '',  # classe - to be filled by user
                    '',  # subclasse - to be filled by user
                    clean_value(asset.get('codigo_ativo', '')),
                    clean_value(asset.get('corretora', '')),
                    clean_value(asset.get('key_xp', '')),
                    clean_value(asset.get('nome', '')),
                    clean_value(asset.get('categoria', '')),
                    clean_value(asset.get('indexador', ''))
                ]
                rows_to_append.append(row)
            
            # Append rows
            ws.append_rows(rows_to_append)
            return True
            
        except Exception as e:
            st.error(f"Error appending to relations: {e}")
            return False
    
    def load_targets(_self) -> pd.DataFrame:
        """
        Load all target allocations.
        
        Returns
        -------
        pd.DataFrame
            Target allocations with columns: nome, classe, subclasse, target
        """
        try:
            df = _self._load_from_gsheets('targets')
            
            # Parse target percentage (Brazilian format)
            if 'target' in df.columns:
                df['target'] = df['target'].apply(_self._parse_brazilian_number) / 100  # Convert from percentage to decimal
            
            return df
            
        except Exception as e:
            st.error(f"Error loading targets: {e}")
            return pd.DataFrame()
    
    def get_customer_targets(self, customer_name: str, targets_df: pd.DataFrame) -> pd.DataFrame:
        """
        Get target allocation for a specific customer.
        
        Parameters
        ----------
        customer_name : str
            Customer name
        targets_df : pd.DataFrame
            All targets dataframe
            
        Returns
        -------
        pd.DataFrame
            Customer's target allocation
        """
        return targets_df[targets_df['nome'] == customer_name].copy()
    
    def get_customers_with_targets(self, targets_df: pd.DataFrame) -> List[str]:
        """Get list of customers who have target allocations."""
        if targets_df.empty or 'nome' not in targets_df.columns:
            return []
        return targets_df['nome'].unique().tolist()
    
    def load_customer_positions(self, customer: dict) -> pd.DataFrame:
        """
        Load cached positions for a specific customer from Streamlit session state.
        
        Parameters
        ----------
        customer : dict
            Customer name
            
        Returns
        -------
        pd.DataFrame
            Customer's positions dataframe
        """
        fetcher = PositionsFetcher()
        positions = []
                        
        if pd.notna(customer['xp_id']):
            xp_pos = fetcher.get_xp_positions(int(customer['xp_id']))
            if not xp_pos.empty:
                positions.append(xp_pos)
        
        if pd.notna(customer.get('btg_id')):
            btg_pos = fetcher.get_btg_positions(int(customer['btg_id']))
            if not btg_pos.empty:
                positions.append(btg_pos)
        
        if pd.notna(customer.get('ibkr_id')):
            ibkr_pos = fetcher.get_ibkr_positions(customer['ibkr_id'])
            if not ibkr_pos.empty:
                positions.append(ibkr_pos)
        
        if positions:
            all_positions = pd.concat(positions, ignore_index=True)
            return all_positions
        else:
            return None


def merge_positions_with_relations(
    positions: pd.DataFrame,
    relations: pd.DataFrame,
    fill_unclassified: bool = True
) -> pd.DataFrame:
    """
    Merge positions with relations, handling unclassified assets consistently.
    
    Parameters
    ----------
    positions : pd.DataFrame
        Positions dataframe with at least 'codigo_ativo' column
    relations : pd.DataFrame
        Relations dataframe with 'codigo_ativo', 'classe', 'subclasse' columns
    fill_unclassified : bool, optional
        If True, fill NaN classe/subclasse with empty string for display.
        If False, leave as NaN (useful for detecting unclassified assets).
        Default is True.
        
    Returns
    -------
    pd.DataFrame
        Merged dataframe with consistent handling of unclassified assets
    """
    # Select only needed columns from relations to avoid conflicts
    relations_cols = ['codigo_ativo', 'nome', 'classe', 'subclasse']
    available_relations_cols = [c for c in relations_cols if c in relations.columns]
    
    # Merge on codigo_ativo
    merged = positions.merge(
        relations[available_relations_cols],
        on=['codigo_ativo', 'nome'],
        how='left'
    )
    
    if fill_unclassified:
        # Fill NaN values with empty string for display
        for col in ['classe', 'subclasse']:
            if col in merged.columns:
                merged[col] = merged[col].fillna('').astype(str)
    
    return merged


def normalize_text(text: str) -> str:
    """Normalize text for comparison (remove accents, lowercase, etc.)."""
    if pd.isna(text):
        return ""
    return unidecode(str(text)).lower().replace(' ', '_').replace('-', '_').replace(',', '')


def calculate_allocation_diff(
    current_position: pd.DataFrame,
    target_allocation: pd.DataFrame,
    total_value: float
) -> pd.DataFrame:
    """
    Calculate the difference between current and target allocation.
    
    Parameters
    ----------
    current_position : pd.DataFrame
        Current position with columns including 'classe', 'subclasse', 'valor_liquido'
    target_allocation : pd.DataFrame
        Target allocation with columns: classe, subclasse, target
    total_value : float
        Total portfolio value
        
    Returns
    -------
    pd.DataFrame
        Allocation comparison with current %, target %, and difference
    """
    # Group current position by class and subclass
    current_by_subclass = current_position.groupby(
        ['classe', 'subclasse']
    )['valor_liquido'].sum().reset_index()
    
    # Create target values
    target_allocation = target_allocation.copy()
    target_allocation['valor_target'] = target_allocation['target'] * total_value
    
    # Merge current with target
    comparison = target_allocation.merge(
        current_by_subclass,
        on=['classe', 'subclasse'],
        how='outer'
    ).fillna(0)
    
    comparison['pct_atual'] = comparison['valor_liquido'] / total_value if total_value > 0 else 0
    comparison['diferenca_valor'] = comparison['valor_target'] - comparison['valor_liquido']
    comparison['diferenca_pct'] = comparison['target'] - comparison['pct_atual']
    
    return comparison


def suggest_rebalancing(
    allocation_diff: pd.DataFrame,
    amount_to_invest: float = 0,
    n_suggestions: int = 3
) -> pd.DataFrame:
    """
    Suggest rebalancing based on allocation differences.
    
    Parameters
    ----------
    allocation_diff : pd.DataFrame
        Output from calculate_allocation_diff
    amount_to_invest : float
        New money to invest
    n_suggestions : int
        Number of suggestions to return
        
    Returns
    -------
    pd.DataFrame
        Suggested allocations for the new investment
    """
    # Filter to classes that are underweight (excluding cash)
    underweight = allocation_diff[
        (allocation_diff['diferenca_valor'] > 0) & 
        (allocation_diff['classe'] != 'caixa')
    ].copy()
    
    if len(underweight) == 0:
        return pd.DataFrame()
    
    # Get top N underweight positions
    top_underweight = underweight.nlargest(n_suggestions, 'diferenca_valor')
    
    # Distribute new investment proportionally
    total_underweight = top_underweight['diferenca_valor'].sum()
    top_underweight['sugestao_valor'] = (
        top_underweight['diferenca_valor'] / total_underweight * amount_to_invest
    )
    
    return top_underweight[['classe', 'subclasse', 'diferenca_valor', 'sugestao_valor']]
