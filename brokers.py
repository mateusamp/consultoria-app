"""
Broker API clients for fetching positions from XP, BTG, and IBKR.

This module provides a unified interface to fetch customer positions
from different brokers.
"""
import re
import time
from typing import Dict, List, Optional, Union
from datetime import datetime
from io import StringIO

import pandas as pd
import numpy as np
import requests
import streamlit as st


from finlib.clients.xp import XPAPIClient
from finlib.clients.btg import BTGAPIClient
from finlib.clients.anbima import ANBIMAClient

from config import IBKR_TOKEN, IBKR_FLEX_QUERIES


def parse_brazilian_number(value) -> float:
    """Parse Brazilian number format (comma as decimal, dot as thousands)."""
    if pd.isna(value) or value == '':
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return 0.0
    # Remove currency symbols and spaces
    value = value.replace('R$', '').replace('%', '').strip()
    # Remove thousand separators (dots)
    value = value.replace('.', '')
    # Replace decimal separator (comma) with dot
    value = value.replace(',', '.')
    try:
        return float(value)
    except ValueError:
        return 0.0


class IBKRClient:
    """
    Interactive Brokers client using Flex Query API.
    """
    
    # Rate limits for initial request
    FIRST_RATE_LIMIT_CALLS = 1
    FIRST_RATE_LIMIT_PERIOD = 1.1  # seconds
    SECOND_RATE_LIMIT_CALLS = 10
    SECOND_RATE_LIMIT_PERIOD = 70  # seconds
    
    def __init__(self, token: str = None):
        """
        Initialize IBKR client.
        
        Parameters
        ----------
        token : str, optional
            Flex Query token. Uses environment variable if not provided.
        """
        self.token = token or IBKR_TOKEN
    
    def _send_request(self, query_id: int, max_retries: int = 70, retry_delay: float = 1.0) -> str:
        """
        Send initial flex query request (rate limited).
        
        Parameters
        ----------
        query_id : int
            Flex Query ID
            
        Returns
        -------
        str
            Reference code for retrieving the statement
            
        Raises
        ------
        ValueError
            If reference code cannot be extracted from response
        """
        url = 'https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/SendRequest'
        params = {'t': self.token, 'q': query_id, 'v': 3}
        
        for _ in range(max_retries):
            response = requests.get(url, params=params)
            response.raise_for_status()

            if 'ErrorCode' not in response.text:
                break
            
            time.sleep(retry_delay)
        else:
            raise TimeoutError("Flex query request timed out")
        
        # Extract reference code
        match = re.search(r'<ReferenceCode>(\d+)</ReferenceCode>', response.text)
        if not match:
            raise ValueError(f"Could not extract reference code from response: {response.text}")
        
        return match.group(1)
    
    def flex_query(
        self,
        query_id: int,
        parse_dates: List[str] = None,
        output: str = 'pandas',
        max_retries: int = 70,
        retry_delay: float = 1.0
    ) -> Union[pd.DataFrame, str]:
        """
        Execute a Flex Query and return results.
        
        Parameters
        ----------
        query_id : int
            Flex Query ID
        parse_dates : list, optional
            Columns to parse as dates
        output : str
            Output format: 'pandas' or 'csv'
        max_retries : int
            Maximum number of retries while waiting for statement
        retry_delay : float
            Delay between retries in seconds
            
        Returns
        -------
        pd.DataFrame or str
            Query results
        """
        # Request statement (rate limited)
        reference_code = self._send_request(query_id, max_retries=max_retries, retry_delay=retry_delay)
        
        # Fetch statement with retries
        get_url = f'https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService/GetStatement'
        get_params = {'t': self.token, 'q': reference_code, 'v': 3}
        
        for _ in range(max_retries):
            response = requests.get(get_url, params=get_params)
            response.raise_for_status()
            
            if 'ErrorCode' not in response.text and 'Statement generation in progress' not in response.text:
                break
            
            time.sleep(retry_delay)
        else:
            raise TimeoutError("Statement generation timed out")
        
        if output == 'pandas':
            df = pd.read_csv(StringIO(response.text), parse_dates=parse_dates)
            return df
        elif output == 'csv':
            return response.text
        else:
            raise ValueError(f"Invalid output format: {output}")
    
    def get_positions(self, exchange_rate: float = None) -> pd.DataFrame:
        """
        Get current positions for all accounts.
        
        Parameters
        ----------
        exchange_rate : float, optional
            USD/BRL exchange rate. If not provided, values stay in USD.
            
        Returns
        -------
        pd.DataFrame
            Positions with columns: account_id, symbol, value, quantity
        
        Notes
        -----
        TODO: Verify that the flex query returns the expected columns.
        The column names are set blindly without checking the actual columns
        returned by the API. This may fail if the query structure changes.
        """
        df = self.flex_query(IBKR_FLEX_QUERIES['positions'])
        
        # TODO: Check actual column names from flex query response
        # Expected columns from flex query: ClientAccountID, Symbol, MarkValue, Position
        df.columns = ['account_id', 'symbol', 'value', 'quantity']
        
        if exchange_rate:
            df['value'] *= exchange_rate
        
        return df
    
    def get_cash_balances(self, exchange_rate: float = None) -> pd.DataFrame:
        """
        Get cash balances for all accounts.
        
        Parameters
        ----------
        exchange_rate : float, optional
            USD/BRL exchange rate.
            
        Returns
        -------
        pd.DataFrame
            Cash balances with columns: account_id, value
        """
        df = self.flex_query(IBKR_FLEX_QUERIES['cash'])
        df = df[df.CurrencyPrimary == 'BASE_SUMMARY'][['ClientAccountID', 'EndingCash']]
        df.columns = ['account_id', 'value']
        
        if exchange_rate:
            df['value'] *= exchange_rate
        
        return df
    
    def get_nav_history(self, years: List[int] = None) -> pd.DataFrame:
        """
        Get NAV history for all accounts.
        
        Parameters
        ----------
        years : list, optional
            Years to fetch. Defaults to current year.
            
        Returns
        -------
        pd.DataFrame
            NAV history pivoted by account
        """
        if years is None:
            years = [datetime.now().year]
        
        # This would typically read from cached files
        # For live data, you'd need to call the flex query
        nav = self.flex_query(IBKR_FLEX_QUERIES['nav'])
        nav = nav[nav.ne(nav.columns)].dropna(how='all')
        nav = nav.drop_duplicates(['ReportDate', 'ClientAccountID'], keep='last')
        nav = nav.pivot(index='ReportDate', columns='ClientAccountID', values='Total').astype(float)
        nav.index = pd.to_datetime(nav.index)
        
        return nav


class PositionsFetcher:
    """
    Unified interface for fetching positions from all brokers.
    """
    
    def __init__(
        self,
        xp_client: 'XPAPIClient' = None,
        btg_client: 'BTGAPIClient' = None,
        ibkr_client: IBKRClient = None
    ):
        """
        Initialize the positions fetcher.
        
        Parameters
        ----------
        xp_client : XPAPIClient, optional
            XP API client
        btg_client : BTGAPIClient, optional
            BTG API client
        ibkr_client : IBKRClient, optional
            IBKR client
        """
        self.xp_client = xp_client
        self.btg_client = btg_client
        self.ibkr_client = ibkr_client or IBKRClient()
        self._exchange_rate = None
    
    @property
    def exchange_rate(self) -> float:
        """Get current USD/BRL exchange rate."""
        if self._exchange_rate is None:
            # Try to fetch from BCB or use a default
            try:
                # BCB API for USD/BRL
                url = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/1?formato=json'
                response = requests.get(url, timeout=10)
                data = response.json()
                self._exchange_rate = float(data[0]['valor'])
            except Exception:
                self._exchange_rate = 6.0  # Default fallback
        return self._exchange_rate
    
    def _process_xp_position(self, position_data: Dict, customer_code: int) -> pd.DataFrame:
        """
        Process XP position data into a standardized format.
        
        This replicates the get_positions function from the notebook.
        """
        p = position_data.get('posicao_detalhada', position_data)
        rows = []
        
        # Cash balance
        if 'financeiro' in p:
            valor = p['financeiro'].get('valor_disponivel', 0)
            rows.append({
                'nome': 'Saldo',
                'valor_bruto': valor,
                'valor_liquido': valor,
                'key_xp': 'financeiro',
                'codigo_ativo': 'SALDO'
            })
        
        # Stocks
        if 'acoes' in p and 'itens' in p['acoes'] and p['acoes']['itens']:
            for item in p['acoes']['itens']:
                qty = item.get('quantidade_total_com_garantias', 0)
                price = item.get('preco_unitario_atual', 0)
                avg_price = item.get('valor_preco_medio', 0)
                valor_bruto = qty * price
                valor_compra = qty * avg_price
                valor_liquido = (valor_bruto - valor_compra) * 0.85 + valor_compra if valor_bruto > valor_compra else valor_bruto
                
                rows.append({
                    'codigo_ativo': item.get('codigo_ativo'),
                    'nome': item.get('codigo_ativo'),
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'quantidade_total': qty,
                    'key_xp': 'acoes'
                })
        
        # Dividends/Proventos
        if 'proventos' in p:
            saldo = p['proventos'].get('saldo', 0)
            saldo_liquido = p['proventos'].get('saldo_liquido', 0)
            rows.append({
                'nome': 'Proventos',
                'valor_bruto': saldo,
                'valor_liquido': saldo_liquido,
                'key_xp': 'proventos',
                'codigo_ativo': 'PROVENTO'
            })
        
        # Funds
        if 'fundos' in p and 'itens' in p['fundos'] and p['fundos']['itens']:
            for item in p['fundos']['itens']:
                valor_bruto = item.get('valor_bruto', 0)
                valor_liquido = item.get('valor_liquido', 0)
                rows.append({
                    'nome': item.get('nome_fundo'),
                    'codigo_ativo': item.get('cnpj'),
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'key_xp': 'fundos'
                })
        
        # Treasury Direct
        if 'tesouro_direto' in p and 'itens' in p['tesouro_direto'] and p['tesouro_direto']['itens']:
            for item in p['tesouro_direto']['itens']:
                nome_titulo = item.get('nome_titulo', '')
                vencimento = item.get('data_vencimento', '')[:4]
                valor_bruto = item.get('valor_bruto', 0)
                valor_aplicado = item.get('valor_aplicado', 0)
                valor_liquido = valor_bruto * 0.85 + min(valor_aplicado, valor_bruto) * 0.15
                
                rows.append({
                    'nome': f"{nome_titulo} {vencimento}",
                    'codigo_ativo': f"{nome_titulo}{vencimento}".replace(' ', ''),
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'key_xp': 'tesouro_direto'
                })
        
        # Fixed Income
        if 'renda_fixa' in p and 'itens' in p['renda_fixa'] and p['renda_fixa']['itens']:
            for item in p['renda_fixa']['itens']:
                # get market prices for CRI/CRA from ANBIMA
                if item.get('categoria') in ['CRI', 'CRA']:
                    pass
                    
                valor_bruto = item.get('valor_financeiro_bruto', 0)
                valor_liquido = item.get('valor_financeiro_liquido', 0)
                rows.append({
                    'nome': item.get('nick_name'),
                    'codigo_ativo': item.get('codigo_cetip_selic'),
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'indexador': item.get('nome_indexador', '') or 'PRE',
                    'categoria': item.get('categoria'),
                    'quantidade_total': item.get('quantidade_total', 0),
                    'preco_unitario': item.get('preco_unitario', 0),
                    'preco_aplicado': item.get('preco_aplicado', 0),
                    'taxa_ir': item.get('taxa_ir', 0),
                    'key_xp': 'renda_fixa'
                })
        
        # Real Estate Funds (FIIs)
        if 'fundos_imobiliarios' in p and 'itens' in p['fundos_imobiliarios'] and p['fundos_imobiliarios']['itens']:
            for item in p['fundos_imobiliarios']['itens']:
                valor = item.get('valor_atual', 0)
                rows.append({
                    'codigo_ativo': item.get('codigo_ativo'),
                    'nome': item.get('codigo_ativo'),
                    'valor_bruto': valor,
                    'valor_liquido': valor,
                    'key_xp': 'fundos_imobiliarios'
                })
        
        # FII Dividends
        if 'proventos_fundo_imobiliario' in p and 'itens' in p['proventos_fundo_imobiliario'] and p['proventos_fundo_imobiliario']['itens']:
            for item in p['proventos_fundo_imobiliario']['itens']:
                valor = item.get('valor_liquido_atual', 0)
                rows.append({
                    'nome': 'Provento FII',
                    'codigo_ativo': 'PROVENTO FII',
                    'valor_bruto': valor,
                    'valor_liquido': valor,
                    'key_xp': 'proventos_fundo_imobiliario'
                })
        
        # Pension
        if 'previdencia' in p and 'itens' in p['previdencia'] and p['previdencia']['itens']:
            for item in p['previdencia']['itens']:
                tipo = item.get('tipo_plano', '')
                valor_bruto = item.get('valor_reserva_acumulada', 0)
                aportes = item.get('aportes', 0)
                
                if tipo == 'PGBL':
                    valor_liquido = valor_bruto * 0.9
                elif tipo == 'VGBL':
                    if valor_bruto > aportes:
                        valor_liquido = (valor_bruto - aportes) * 0.9 + aportes
                    else:
                        valor_liquido = valor_bruto
                else:
                    valor_liquido = valor_bruto
                
                rows.append({
                    'nome': item.get('nome_plano'),
                    'codigo_ativo': item.get('cnpj'),
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'key_xp': 'previdencia'
                })
        
        # COE
        if 'coe' in p and 'itens' in p['coe'] and p['coe']['itens']:
            for item in p['coe']['itens']:
                valor_bruto = item.get('valor_financeiro_bruto', 0)
                valor_liquido = item.get('valor_financeiro_liquido', 0)
                rows.append({
                    'nome': item.get('nome_ativo'),
                    'codigo_ativo': item.get('codigo_ativo'),
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'key_xp': 'coe'
                })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            df['codigo_cliente'] = customer_code
            df['corretora'] = 'XP'
        
        return df
    
    def _process_btg_position(self, position_data: Dict, account_number: int) -> pd.DataFrame:
        """
        Process BTG position data into a standardized format.
        
        Parameters
        ----------
        position_data : dict
            BTG position response with snake_case keys
        account_number : int
            BTG account number
            
        Returns
        -------
        pd.DataFrame
            Standardized positions matching XP format
        """
        rows = []
        
        # Cash - Current Account
        if 'cash' in position_data and position_data['cash']:
            for cash_item in position_data['cash']:
                if 'current_account' in cash_item:
                    valor = float(cash_item['current_account'].get('value', 0))
                    if valor != 0:
                        rows.append({
                            'nome': 'Saldo',
                            'valor_bruto': valor,
                            'valor_liquido': valor,
                            'key_xp': 'financeiro',
                            'codigo_ativo': 'SALDO'
                        })
        
        # Equities (Stocks and FIIs)
        if 'equities' in position_data and position_data['equities']:
            for equity in position_data['equities']:
                if 'stock_positions' in equity and equity['stock_positions']:
                    for stock in equity['stock_positions']:
                        ticker = stock.get('ticker')
                        qty = float(stock.get('quantity', 0))
                        price = float(stock.get('market_price', 0))
                        cost_price = float(stock.get('cost_price', 0))
                        valor_bruto = float(stock.get('gross_value', 0))
                        valor_compra = qty * cost_price
                        is_fii = stock.get('is_fii', 'false') == 'true'
                        
                        # Apply tax logic similar to XP
                        if valor_bruto > valor_compra and not is_fii:
                            valor_liquido = (valor_bruto - valor_compra) * 0.85 + valor_compra
                        else:
                            valor_liquido = valor_bruto
                        
                        rows.append({
                            'codigo_ativo': ticker,
                            'nome': ticker,
                            'valor_bruto': valor_bruto,
                            'valor_liquido': valor_liquido,
                            'quantidade_total': qty,
                            'preco_unitario': price,
                            'key_xp': 'fundos_imobiliarios' if is_fii else 'acoes'
                        })
        
        # Fixed Income
        if 'fixed_income' in position_data and position_data['fixed_income']:
            for item in position_data['fixed_income']:
                ticker = item.get('ticker', '')
                valor_bruto = float(item.get('gross_value', 0))
                valor_liquido = float(item.get('net_value', 0))
                issuer = item.get('issuer', '')
                indexador = item.get('reference_index_name', 'PRE')
                categoria = item.get('accounting_group_code', '')
                
                # Determine asset code
                codigo_ativo = item.get('cetip_code') or item.get('selic_code') or ticker
                
                rows.append({
                    'nome': f"{categoria} {issuer[:30]}",
                    'codigo_ativo': codigo_ativo,
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'indexador': indexador,
                    'categoria': categoria,
                    'quantidade_total': float(item.get('quantity', 0)),
                    'preco_unitario': float(item.get('price', 0)),
                    'taxa_ir': float(item.get('income_tax', 0)),
                    'key_xp': 'tesouro_direto' if 'TESOURO' in categoria else 'renda_fixa'
                })
        
        # Investment Funds
        if 'investment_fund' in position_data and position_data['investment_fund']:
            for fund in position_data['investment_fund']:
                acquisitions = pd.DataFrame(fund['acquisition'])
                valor_bruto = acquisitions.gross_asset_value.astype(float).sum()
                valor_liquido = acquisitions.net_asset_value.astype(float).sum()
                rows.append({
                    'nome': fund['fund']['fund_name'],
                    'codigo_ativo': fund['fund']['fund_cnpj_code'],
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'key_xp': 'fundos'
                })
        
        # Pension (Previdência)
        if 'pension_informations' in position_data and position_data['pension_informations']:
            for pension in position_data['pension_informations']:
                tipo = pension.get('fund_type', '')
                valor_bruto = float(pension.get('gross_value', 0))
                aportes = float(pension.get('cost_price', 0))
                
                # Apply PGBL/VGBL tax logic similar to XP
                if tipo == 'PGBL':
                    valor_liquido = valor_bruto * 0.65  # Assuming 35% max tax
                elif tipo == 'VGBL':
                    ganho = max(0, valor_bruto - aportes)
                    valor_liquido = valor_bruto - ganho * 0.15  # 15% tax on gains
                else:
                    valor_liquido = valor_bruto
                
                # Get the actual fund details
                if 'positions' in pension and pension['positions']:
                    for pos in pension['positions']:
                        rows.append({
                            'nome': pos.get('fund_name'),
                            'codigo_ativo': pos.get('fund_code'),
                            'valor_bruto': valor_bruto,
                            'valor_liquido': valor_liquido,
                            'key_xp': 'previdencia'
                        })
        
        # Cryptocurrency
        if 'crypto_coin' in position_data and position_data['crypto_coin']:
            for crypto in position_data['crypto_coin']:
                valor_bruto = float(crypto.get('gross_financial', 0))
                valor_liquido = float(crypto.get('financial', 0))
                asset_name = crypto.get('asset', {}).get('name', 'Crypto')
                
                rows.append({
                    'nome': asset_name,
                    'codigo_ativo': asset_name.split()[0] if asset_name else 'CRYPTO',
                    'valor_bruto': valor_bruto,
                    'valor_liquido': valor_liquido,
                    'quantidade_total': float(crypto.get('quantity', 0)),
                    'key_xp': 'crypto'
                })
        
        # Pending Settlements (Valores em Trânsito)
        if 'pending_settlements' in position_data and position_data['pending_settlements']:
            for settlement in position_data['pending_settlements']:
                # Equity dividends
                if 'equities' in settlement and settlement['equities']:
                    for item in settlement['equities']:
                        if item.get('transaction') == 'PROVENTO':
                            valor = float(item.get('financial_value', 0))
                            rows.append({
                                'nome': 'Proventos',
                                'codigo_ativo': 'PROVENTO',
                                'valor_bruto': valor,
                                'valor_liquido': valor,
                                'key_xp': 'proventos'
                            })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            df['codigo_cliente'] = account_number
            df['corretora'] = 'BTG'
        
        return df

    def get_xp_positions(_self, customer_code: int) -> pd.DataFrame:
        """
        Get positions from XP for a customer.
        
        Parameters
        ----------
        customer_code : int
            XP customer code
            
        Returns
        -------
        pd.DataFrame
            Standardized positions
        """
        if not _self.xp_client:
            _self.xp_client = XPAPIClient()
            _self.xp_client.authenticate()
        
        try:
            position = _self.xp_client.get_consolidated_position(customer_code)
            return _self._process_xp_position(position, customer_code)
        except Exception as e:
            st.error(f"Error fetching XP positions for {customer_code}: {e}")
            return pd.DataFrame()
    
    def get_btg_positions(_self, account_number: int) -> pd.DataFrame:
        """
        Get positions from BTG for an account.
        
        Parameters
        ----------
        account_number : int
            BTG account number
            
        Returns
        -------
        pd.DataFrame
            Standardized positions
        """
        if not _self.btg_client:
            _self.btg_client = BTGAPIClient()
        
        try:
            position = _self.btg_client.get_account_position(account_number)
            return _self._process_btg_position(position, account_number)
        except Exception as e:
            st.error(f"Error fetching BTG positions for {account_number}: {e}")
            return pd.DataFrame()
    
    def get_ibkr_positions(_self, account_id: str = None) -> pd.DataFrame:
        """
        Get positions from IBKR.
        
        Parameters
        ----------
        account_id : str, optional
            Filter by account ID
            
        Returns
        -------
        pd.DataFrame
            Standardized positions
        """
        try:
            exchange_rate = _self.exchange_rate
            
            # Get positions
            positions = _self.ibkr_client.get_positions(exchange_rate)
            
            # Get cash
            cash = _self.ibkr_client.get_cash_balances(exchange_rate)
            cash['symbol'] = 'cash'
            
            # Combine
            all_positions = pd.concat([
                positions[['account_id', 'symbol', 'value']],
                cash[['account_id', 'symbol', 'value']]
            ], ignore_index=True)
            
            if account_id:
                all_positions = all_positions[all_positions.account_id == account_id]
            
            # Standardize format
            all_positions = all_positions.rename(columns={
                'symbol': 'codigo_ativo',
                'value': 'valor_liquido',
                'account_id': 'codigo_cliente'
            })
            all_positions['nome'] = all_positions['codigo_ativo']
            all_positions['valor_bruto'] = all_positions['valor_liquido']
            all_positions['corretora'] = 'IBKR'
            
            return all_positions
            
        except Exception as e:
            st.error(f"Error fetching IBKR positions: {e}")
            return pd.DataFrame()
    
    def get_all_positions(
        self,
        customers: pd.DataFrame,
        show_progress: bool = True
    ) -> pd.DataFrame:
        """
        Get positions from all brokers for all customers.
        
        Parameters
        ----------
        customers : pd.DataFrame
            Customer data with xp_id, btg_id, ibkr_id columns
        show_progress : bool
            Whether to show progress bar
            
        Returns
        -------
        pd.DataFrame
            Combined positions from all brokers
        """
        all_positions = []
        
        # Map IBKR account IDs to customer codes
        ibkr_map = customers[customers['ibkr_id'].notna()].set_index('ibkr_id')['xp_id'].to_dict()
        
        customers_iter = customers.itertuples()
        if show_progress:
            customers_iter = st.progress(0)
            total = len(customers)
        
        for i, customer in enumerate(customers.itertuples()):
            # XP positions
            if pd.notna(customer.xp_id):
                xp_pos = self.get_xp_positions(int(customer.xp_id))
                if not xp_pos.empty:
                    all_positions.append(xp_pos)
            
            # BTG positions
            if hasattr(customer, 'btg_id') and pd.notna(customer.btg_id):
                btg_pos = self.get_btg_positions(int(customer.btg_id))
                if not btg_pos.empty:
                    all_positions.append(btg_pos)
            
            if show_progress:
                customers_iter.progress((i + 1) / total)
        
        # IBKR positions (all at once)
        ibkr_pos = self.get_ibkr_positions()
        if not ibkr_pos.empty and ibkr_map:
            ibkr_pos['codigo_cliente'] = ibkr_pos['codigo_cliente'].replace(ibkr_map)
            all_positions.append(ibkr_pos)
        
        if not all_positions:
            return pd.DataFrame()
        
        result = pd.concat(all_positions, ignore_index=True)
        
        # Fill missing columns
        for col in ['nome', 'categoria', 'indexador']:
            if col not in result.columns:
                result[col] = ''
        
        return result
