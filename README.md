# Consultoria App

Aplicativo Streamlit para consolidação e análise de carteiras de clientes em múltiplas corretoras (XP, BTG, IBKR).

## Estrutura do Projeto

```
consultoria-app/
├── app.py              # Aplicação principal Streamlit
├── config.py           # Configurações e constantes
├── data_loader.py      # Carregamento de dados (Google Sheets / Excel)
├── brokers.py          # Clientes de API das corretoras
├── visualizations.py   # Gráficos e visualizações
├── requirements.txt    # Dependências
└── README.md           # Este arquivo
```

## Funcionalidades

### 📊 Visão Geral
- Resumo de todos os clientes
- Distribuição por corretora
- Lista de clientes com busca

### 👤 Análise por Cliente
- Carregamento de posições via API
- Detalhamento de ativos
- Alocação por classe e subclasse

### 📈 Alocação
- Comparação atual vs alvo
- Visualização de gaps
- Identificação de desvios

### 🔄 Rebalanceamento
- Sugestões de alocação para novos aportes
- Distribuição proporcional aos gaps
- Priorização de classes deficitárias

## Configuração

### 1. Credenciais Google Sheets

Coloque o arquivo de credenciais do Google Service Account em:
```
/home/mateus/Documentos/finance/personal-186619-dd73e34aa638.json
```

### 2. Variáveis de Ambiente (opcional)

```bash
export IBKR_TOKEN="seu_token_ibkr"
export XP_CLIENT_ID="seu_client_id_xp"
export XP_CLIENT_SECRET="seu_client_secret_xp"
export BTG_CLIENT_ID="seu_client_id_btg"
export BTG_CLIENT_SECRET="seu_client_secret_btg"
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar finlib (opcional)

Se você quiser usar as APIs de XP e BTG, certifique-se de que a biblioteca `finlib` está instalada:

```bash
cd /home/mateus/Documentos/finance
pip install -e .
```

## Execução

```bash
cd /home/mateus/Documentos/finance/consultoria-app
streamlit run app.py
```

Ou a partir da pasta finance:

```bash
streamlit run consultoria-app/app.py
```

A aplicação estará disponível em: http://localhost:8501

## Fonte de Dados

### Google Sheets (Padrão)
A aplicação carrega dados da planilha:
- **Sheet ID**: `1HlKyfENVqKnLmSKLdtHnI7DW6IqAhXH9BgUQSwIK8Tg`

### Excel Local (Alternativo)
Se o Google Sheets não estiver disponível, usa:
- **Arquivo**: `consultoria/Consultoria.xlsx`

### Estrutura das Planilhas

#### `customers`
| Coluna | Descrição |
|--------|-----------|
| name | Nome do cliente |
| xp_id | ID na XP |
| btg_id | ID no BTG |
| ibkr_id | ID na IBKR |
| tax | Taxa de assessoria |
| start_date | Data de início |

#### `relations`
| Coluna | Descrição |
|--------|-----------|
| classe | Classe do ativo (inflacao, pre, pos_fixado, etc.) |
| subclasse | Subclasse (tesouro, emissao_bancaria, etc.) |
| codigo_ativo | Código do ativo |
| corretora | Corretora (XP, BTG, IBKR) |

#### Planilhas de Alocação (por cliente)
Cada cliente pode ter uma planilha com seu ID ou nome, contendo:
| Classe | % Classe | Subclasse | % Subclasse |
|--------|----------|-----------|-------------|
| Inflação | 50% | Emissão Bancária | 15% |
| ... | ... | ... | ... |

## Manutenção

### Adicionar Novo Cliente
1. Adicionar linha na aba `customers` do Google Sheets
2. Criar planilha de alocação alvo (se necessário)

### Adicionar Novo Ativo
1. O sistema detecta automaticamente ativos não categorizados
2. Adicionar relação na aba `relations`

### Atualizar APIs
Os clientes das corretoras estão em `brokers.py` e podem ser customizados conforme necessário.

## Tecnologias

- **Streamlit**: Framework web
- **Pandas**: Manipulação de dados
- **Plotly**: Gráficos interativos
- **gspread**: Integração Google Sheets
- **finlib**: APIs das corretoras (XP, BTG)
