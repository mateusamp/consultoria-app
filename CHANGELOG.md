# Changelog - Consultoria App Updates

## 2024 - Major Refactoring

### Recent Changes (2026-01-20)

#### UI Improvements & Relations Management
- **Status**: ✅ Complete
- **Changes**:
  1. **Removed Relations Page**: Deleted `pages/2_🔗_Relacoes.py` since it duplicates spreadsheet data
  2. **Enhanced Unclassified Assets Warning**: 
     - Warning now properly displays when assets are not in relations sheet
     - Shows count and list of unclassified asset codes
     - Displays total value and percentage of unclassified assets
  3. **Add Assets to Relations Feature**:
     - New "➕ Adicionar à Planilha" button appears when unclassified assets detected
     - Shows preview of assets that will be added
     - Automatically appends assets to Google Sheets 'relations' tab
     - Leaves 'classe' and 'subclasse' fields empty for manual filling
     - Direct link to open Google Sheets for editing
  4. **Page Renumbering**: Renumbered `3_👥_Clientes.py` to `2_👥_Clientes.py`

**New Methods Added**:
- `DataLoader.append_to_relations()`: Appends new assets to relations sheet

**Testing**:
- ✅ Found customers with unclassified assets:
  - Carlos Benjamin Blanco de Souza: 2 assets (NTN-B12039, CDBA250QJE8)
  - Guilherme Pagliara Lage: 2 assets (CDB825AYOP3, CDB123BCJD4)
  - João Daniel Nunes Duarte: 3 assets (CDBB2595D07, CDBC25AJ4NI, KNDI11)

### Summary
Implemented 6 major changes to simplify the app, adapt to Brazilian spreadsheet format, and improve data management.

### Changes Implemented

#### 1. ✅ Removed Data Source Selection
- **What**: Removed Google Sheets vs Excel Local selection radio button
- **Why**: Always use Google Sheets as the single source of truth
- **Files Modified**:
  - `app.py`: Removed data source radio button, simplified DataLoader instantiation
  - All page files: Updated DataLoader() calls to remove `use_google_sheets` parameter

#### 2. ✅ Single Targets Sheet
- **What**: Changed from multiple target sheets (one per customer) to a single 'targets' sheet
- **Structure**: 
  - Old: Multiple sheets named by customer (XP ID or name), columns: classe, subclasse, pct_classe, pct_subclasse
  - New: Single 'targets' sheet, columns: nome, classe, subclasse, target (percentage format)
- **Files Modified**:
  - `data_loader.py`: 
    - Removed `get_available_target_sheets()` method
    - Removed `load_target_allocation(sheet_name)` method
    - Added `load_targets()` to load entire targets sheet
    - Added `get_customer_targets(customer_name, targets_df)` to filter targets by customer
    - Updated `calculate_allocation_diff()` to use 'target' column instead of 'pct_subclasse'
  - `app.py`, all pages: Updated to use new methods

#### 3. ✅ Brazilian Number Format Support
- **What**: Added parsing for Brazilian spreadsheet format (comma = decimal, dot = thousands)
- **Examples**: 
  - "R$ 1.042,27" → 1042.27
  - "10,0%" → 10.0
  - "0,005" → 0.005
- **Files Modified**:
  - `data_loader.py`: 
    - Added `_parse_brazilian_number()` static method
    - Applied to all numeric columns in targets sheet
  - `brokers.py`: 
    - Added module-level `parse_brazilian_number()` function
    - Updated `_process_xp_position()` to parse all numeric values:
      - Cash, stocks, dividends, funds, treasury bonds, fixed income
      - Real estate funds (FIIs), pension plans, COEs

#### 4. ✅ Portuguese Column Names Support
- **What**: Updated customers sheet to use Portuguese column names from Google Sheets
- **Mapping**:
  - nome → name
  - xp → xp_id
  - btg → btg_id
  - ibkr → ibkr_id
  - taxa → tax
  - minimo_mensal → min_monthly
  - data_inicial → start_date
  - ultimo_valor → last_value
- **Files Modified**:
  - `data_loader.py`: `load_customers()` method with column mapping

#### 5. ✅ Warning System
- **What**: Added warnings when customer has missing data
- **Warnings**:
  - Customer has no targets defined in 'targets' sheet
  - Assets not found in 'relations' sheet (unclassified assets)
- **Files Modified**:
  - `app.py`: `show_customer_analysis()` function checks for both conditions

#### 6. ✅ Fixed Deprecated use_container_width
- **What**: Replaced deprecated `use_container_width=True` with `width='stretch'`
- **Why**: Streamlit deprecation warning - will be removed after 2025-12-31
- **Files Modified**:
  - `app.py`
  - `pages/1_📈_Analise_Detalhada.py`
  - `pages/2_🔗_Relacoes.py`
  - `pages/3_👥_Clientes.py`

### Known Issues / TODO

#### IBKR Extraction Testing Needed
- **Status**: ⚠️ Not yet tested
- **Issue**: User reported IBKR extractions "seem not correct"
- **Location**: `brokers.py` - `IBKRClient.get_positions()` method
- **Problem**: Column names are set blindly without checking actual flex query response
- **Action Required**: 
  1. Test IBKR flex query 1145252 to verify actual columns returned
  2. Update column mapping if needed
  3. Add error handling for unexpected column structures

### Recent Improvements (2026-01-20)

#### BTG Position Processing Enhanced
- **Status**: ✅ Complete and tested
- **What**: Replaced simple BTG total with detailed position breakdown
- **Changes**:
  - Added `_camel_to_snake()` method to BTGAPIClient for consistent key formatting
  - Added `_format_dict()` method to recursively convert API responses to snake_case
  - Created `_process_btg_position()` method in brokers.py following XP standards
  - Processes all asset types: Fixed Income, Equities (stocks/FIIs), Funds, Pension, Crypto, Cash, Pending Settlements
  - Applies same tax logic as XP (15% on gains for stocks, 35% max for PGBL, etc.)
- **Testing**: 
  - ✅ Validation passed with 0.00% difference between raw total and processed total
  - ✅ All 13 positions from account 3026592 correctly processed
  - ✅ Total: R$ 1,010,899.76 (bruto) / R$ 948,097.79 (líquido)
  - ✅ Tax impact correctly calculated: 6.21% overall
  - ✅ XP compatibility confirmed for all BTG asset types

**Breakdown by Asset Type:**
- Fixed Income (Renda Fixa): R$ 728,131.62 → R$ 697,358.19 (7 positions)
- Pension (Previdência): R$ 88,419.39 → R$ 57,472.60 (1 PGBL)
- Treasury Direct: R$ 76,057.69 → R$ 74,975.94 (1 NTN-B1)
- Real Estate Funds: R$ 58,848.70 (2 FIIs)
- Crypto: R$ 58,998.36 (1 Bitcoin)
- Dividends: R$ 444.00 (pending settlement)

### Files Changed
- ✅ `consultoria-app/data_loader.py` (9 changes)
- ✅ `consultoria-app/brokers.py` (4 changes)
- ✅ `consultoria-app/app.py` (6 changes)
- ✅ `consultoria-app/pages/1_📈_Analise_Detalhada.py` (5 changes)
- ✅ `consultoria-app/pages/2_🔗_Relacoes.py` (2 changes)
- ✅ `consultoria-app/pages/3_👥_Clientes.py` (4 changes)

### Testing Checklist
- [ ] Test loading customers from Google Sheets with Portuguese columns
- [ ] Test loading targets from single 'targets' sheet
- [ ] Verify Brazilian number format parsing works correctly
- [ ] Check warning appears when customer has no targets
- [ ] Check warning appears for unclassified assets
- [ ] Test XP positions with Brazilian format
- [ ] **IMPORTANT**: Test IBKR flex query and verify columns
- [ ] Verify all deprecation warnings are gone

### Google Sheets Structure
**Sheet ID**: `1HlKyfENVqKnLmSKLdtHnI7DW6IqAhXH9BgUQSwIK8Tg`

**customers** sheet:
```
nome, xp, ibkr, btg, taxa, minimo_mensal, cpf, ultimo_valor, data_inicial, endereco
```

**targets** sheet:
```
nome, classe, subclasse, target
```
- Example: "João Silva", "Renda Fixa", "Títulos Públicos", "10,0%"

**relations** sheet (unchanged):
```
classe, subclasse, codigo_ativo, corretora, key_xp, nome, categoria, indexador
```
