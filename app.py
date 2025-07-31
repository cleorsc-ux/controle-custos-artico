import streamlit as st
import pandas as pd
from datetime import datetime, date
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from pathlib import Path
import json
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# =============================================
# CONFIGURAÇÕES PRINCIPAIS
# =============================================
NOME_PLANILHA = "Controle de custos -Ártico"
ARQUIVO_CREDENCIAIS = "credenciais.json"
COLUNAS = [
    "Data", "Cliente/Projeto", "Categoria", "Descrição",
    "Quantidade", "Preço Unitário", "Subtotal", "Desconto (%)",
    "Total", "Status Pagamento", "Forma Pagamento", "Observações"
]

# Configuração da página
st.set_page_config(
    page_title="Ártico - Sistema de Controle de Custos",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stSelectbox > div > div {
        background-color: #f0f2f6;
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    .footer {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin-top: 2rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# =============================================
# AUTENTICAÇÃO E CONFIGURAÇÃO DA PLANILHA
# =============================================
def configurar_planilha(aba):
    """Configura o cabeçalho e formatação da planilha"""
    try:
        # Verificar estrutura atual
        todos_valores = aba.get_all_values()

        # Se planilha está vazia ou primeira linha não é cabeçalho
        if not todos_valores or todos_valores[0] != COLUNAS:
            # Verificar se há dados que precisam ser preservados
            dados_existentes = []
            if todos_valores:
                # Se primeira linha não é cabeçalho, todos os dados são válidos
                if todos_valores[0] != COLUNAS:
                    dados_existentes = todos_valores
                # Se há cabeçalho mas está incompleto, pegar dados das linhas seguintes
                else:
                    dados_existentes = todos_valores[1:] if len(todos_valores) > 1 else []

            # Limpar planilha
            aba.clear()

            # Adicionar cabeçalho
            aba.append_row(COLUNAS)

            # Restaurar dados existentes (se houver)
            if dados_existentes:
                for linha in dados_existentes:
                    if any(linha):  # Se linha não está vazia
                        # Garantir que linha tem todas as colunas
                        linha_completa = linha + [''] * (len(COLUNAS) - len(linha))
                        aba.append_row(linha_completa[:len(COLUNAS)])

            # Formatação do cabeçalho
            try:
                # Formatar primeira linha (cabeçalho)
                aba.format('1:1', {
                    'backgroundColor': {'red': 0.2, 'green': 0.4, 'blue': 0.8},
                    'textFormat': {
                        'foregroundColor': {'red': 1, 'green': 1, 'blue': 1},
                        'fontSize': 11,
                        'bold': True
                    },
                    'horizontalAlignment': 'CENTER'
                })

                # Formatar largura das colunas
                dimensoes = [
                    ('A:A', 120),  # Data
                    ('B:B', 200),  # Cliente/Projeto
                    ('C:C', 150),  # Categoria
                    ('D:D', 250),  # Descrição
                    ('E:E', 100),  # Quantidade
                    ('F:F', 120),  # Preço Unitário
                    ('G:G', 120),  # Subtotal
                    ('H:H', 100),  # Desconto
                    ('I:I', 120),  # Total
                    ('J:J', 150),  # Status Pagamento
                    ('K:K', 150),  # Forma Pagamento
                    ('L:L', 200),  # Observações
                ]

                for coluna, largura in dimensoes:
                    aba.update_dimension_property(coluna, 'COLUMN_WIDTH', largura)

            except Exception as format_error:
                st.warning(f"Formatação aplicada parcialmente: {format_error}")

            return True, "✅ Planilha configurada com sucesso!"

        return True, "✅ Planilha já está configurada corretamente"

    except Exception as e:
        return False, f"❌ Erro ao configurar planilha: {str(e)}"


@st.cache_resource
def init_google_sheets():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Primeiro, tentar usar secrets do Streamlit Cloud (se disponível)
        try:
            if hasattr(st, 'secrets') and 'credentials' in st.secrets:
                credentials_dict = dict(st.secrets["credentials"])
                creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
                st.success("✅ Conectado usando Streamlit Secrets")
            else:
                raise Exception("Secrets não encontrados")
        except:
            # Se não funcionar, usar arquivo local
            cred_paths = [
                Path(__file__).parent / ARQUIVO_CREDENCIAIS,  # Mesmo diretório do script
                Path(ARQUIVO_CREDENCIAIS),  # Diretório atual
                Path.cwd() / ARQUIVO_CREDENCIAIS,  # Diretório de trabalho atual
            ]

            cred_file = None
            for path in cred_paths:
                if path.exists():
                    cred_file = path
                    break

            if not cred_file:
                st.error(f"""
                ❌ **Arquivo de credenciais não encontrado!**

                Procurado em:
                - {cred_paths[0]}
                - {cred_paths[1]}
                - {cred_paths[2]}

                **Soluções:**
                1. Coloque o arquivo `credenciais.json` no mesmo diretório do script
                2. Ou configure as credenciais no Streamlit Secrets

                **Para usar Streamlit Secrets:**
                - Crie um arquivo `.streamlit/secrets.toml` com:
                ```
                [credentials]
                type = "service_account"
                project_id = "seu-projeto-id"
                private_key_id = "sua-private-key-id"
                private_key = "-----BEGIN PRIVATE KEY-----\\nsua-chave-privada\\n-----END PRIVATE KEY-----\\n"
                client_email = "seu-service-account@projeto.iam.gserviceaccount.com"
                client_id = "seu-client-id"
                auth_uri = "https://accounts.google.com/o/oauth2/auth"
                token_uri = "https://oauth2.googleapis.com/token"
                auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
                client_x509_cert_url = "sua-cert-url"
                universe_domain = "googleapis.com"
                ```
                """)
                st.stop()

            creds = ServiceAccountCredentials.from_json_keyfile_name(str(cred_file), scope)
            st.success(f"✅ Conectado usando arquivo: {cred_file.name}")

        client = gspread.authorize(creds)

        # Tentar abrir a planilha
        try:
            planilha = client.open(NOME_PLANILHA)
        except gspread.SpreadsheetNotFound:
            st.error(f"""
            ❌ **Planilha '{NOME_PLANILHA}' não encontrada!**

            **Soluções:**
            1. Verifique se o nome da planilha está correto
            2. Certifique-se de que a planilha foi compartilhada com o email da service account
            3. Verifique se a planilha existe no Google Drive

            **Email da Service Account:** `{creds.service_account_email}`
            """)
            st.stop()

        aba = planilha.sheet1

        # Configurar planilha (cabeçalho e formatação)
        sucesso, mensagem = configurar_planilha(aba)
        if sucesso:
            st.success(mensagem)
        else:
            st.warning(mensagem)

        return aba, creds.service_account_email

    except Exception as e:
        st.error(f"""
        ⚠️ **Erro na conexão com Google Sheets:**

        **Erro:** {str(e)}

        **Possíveis soluções:**
        1. Verifique suas credenciais
        2. Certifique-se de que as APIs estão habilitadas
        3. Verifique a conexão com a internet
        4. Confirme se a planilha foi compartilhada corretamente
        """)
        st.stop()


# Tentar inicializar conexão
try:
    aba, service_email = init_google_sheets()
    st.sidebar.success(f"📡 Conectado: {service_email[:30]}...")
except:
    st.error("❌ Não foi possível conectar ao Google Sheets")
    st.stop()


# =============================================
# FUNÇÕES AUXILIARES
# =============================================
@st.cache_data(ttl=300)  # Cache por 5 minutos
def carregar_dados():
    try:
        registros = aba.get_all_records()
        if registros:
            df = pd.DataFrame(registros)
            # Converter colunas numéricas
            colunas_numericas = ['Quantidade', 'Preço Unitário', 'Subtotal', 'Desconto (%)', 'Total']
            for col in colunas_numericas:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # Converter datas
            if 'Data' in df.columns:
                df['Data'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')

            return df
        return pd.DataFrame(columns=COLUNAS)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame(columns=COLUNAS)


def salvar_registro(registro):
    try:
        aba.append_row(list(registro.values()))
        st.cache_data.clear()  # Limpar cache para atualizar dados
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {str(e)}")
        return False


def gerar_relatorio_simples(df):
    """Gera um relatório simples em texto"""
    relatorio = f"""
ÁRTICO SOLUÇÕES PREDIAIS - RELATÓRIO DE CUSTOS
Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}

RESUMO FINANCEIRO:
- Total de Registros: {len(df)}
- Valor Total: R$ {df['Total'].sum():,.2f}
- Ticket Médio: R$ {df['Total'].mean() if len(df) > 0 else 0:,.2f}
- Pagamentos Pendentes: {len(df[df['Status Pagamento'] == 'Pendente'])}

DISTRIBUIÇÃO POR CATEGORIA:
"""

    if not df.empty:
        distribuicao = df.groupby('Categoria')['Total'].sum()
        for categoria, valor in distribuicao.items():
            relatorio += f"- {categoria}: R$ {valor:,.2f}\n"

    relatorio += "\n\nREGISTROS DETALHADOS:\n"
    for _, row in df.iterrows():
        relatorio += f"""
Data: {row['Data'].strftime('%d/%m/%Y') if pd.notnull(row['Data']) else 'N/A'}
Cliente: {row['Cliente/Projeto']}
Categoria: {row['Categoria']}
Descrição: {row['Descrição']}
Total: R$ {row['Total']:,.2f}
Status: {row['Status Pagamento']}
---
"""

    return relatorio


# =============================================
# INTERFACE PRINCIPAL
# =============================================

# Header personalizado
st.markdown("""
<div class="main-header">
    <h1>🏗️ ÁRTICO SOLUÇÕES PREDIAIS</h1>
    <h3>Sistema Profissional de Controle de Custos</h3>
    <p>Gestão inteligente para seu negócio</p>
</div>
""", unsafe_allow_html=True)

# Sidebar - Configurações e Formulário
with st.sidebar:
    # Seção de configurações da planilha
    st.markdown("### ⚙️ **CONFIGURAÇÕES**")

    if st.button("🔧 Reconfigurar Planilha", help="Reorganiza o cabeçalho e formatação da planilha"):
        with st.spinner("Reconfigurando planilha..."):
            sucesso, mensagem = configurar_planilha(aba)
            if sucesso:
                st.success(mensagem)
                st.cache_data.clear()  # Limpar cache
                st.rerun()
            else:
                st.error(mensagem)

    st.markdown("---")

    st.markdown("### 📝 **NOVO REGISTRO DE CUSTO**")

    with st.form(key='form_custo_completo', clear_on_submit=True):
        # Informações básicas
        st.markdown("#### 📅 **Informações Gerais**")
        data = st.date_input("Data do Gasto", datetime.now())
        cliente = st.text_input("Cliente/Projeto", placeholder="Ex: Reforma Apto 101")

        # Categoria do gasto
        categoria = st.selectbox("Categoria do Gasto", [
            "Materiais de Construção",
            "Ferramentas",
            "Mão de Obra",
            "Transporte",
            "Equipamentos",
            "Limpeza",
            "Pintura",
            "Elétrica",
            "Hidráulica",
            "Outros"
        ])

        # Detalhes do gasto
        st.markdown("#### 💰 **Detalhes Financeiros**")
        descricao = st.text_area("Descrição Detalhada",
                                 placeholder="Ex: Tinta látex branca 18L marca Suvinil")

        col1, col2 = st.columns(2)
        with col1:
            quantidade = st.number_input("Quantidade", min_value=0.01, value=1.0, step=0.01)
        with col2:
            preco_unitario = st.number_input("Preço Unitário (R$)", min_value=0.0, step=0.01)

        subtotal = quantidade * preco_unitario
        st.info(f"Subtotal: R$ {subtotal:,.2f}")

        desconto = st.slider("Desconto (%)", 0, 50, 0)
        total = subtotal * (1 - desconto / 100)

        # Status e forma de pagamento
        st.markdown("#### 💳 **Pagamento**")
        status_pagamento = st.selectbox("Status do Pagamento",
                                        ["Pendente", "Pago", "Parcial", "Cancelado"])
        forma_pagamento = st.selectbox("Forma de Pagamento",
                                       ["Dinheiro", "PIX", "Cartão Débito", "Cartão Crédito",
                                        "Transferência", "Cheque", "Boleto"])

        # Observações
        observacoes = st.text_area("Observações Adicionais",
                                   placeholder="Notas importantes sobre este gasto...")

        # Botão de salvar
        submitted = st.form_submit_button("💾 **SALVAR REGISTRO**",
                                          use_container_width=True)

        if submitted:
            if cliente and descricao:
                novo_registro = {
                    "Data": data.strftime("%d/%m/%Y"),
                    "Cliente/Projeto": cliente,
                    "Categoria": categoria,
                    "Descrição": descricao,
                    "Quantidade": quantidade,
                    "Preço Unitário": preco_unitario,
                    "Subtotal": subtotal,
                    "Desconto (%)": desconto,
                    "Total": total,
                    "Status Pagamento": status_pagamento,
                    "Forma Pagamento": forma_pagamento,
                    "Observações": observacoes
                }

                if salvar_registro(novo_registro):
                    st.success("✅ Registro salvo com sucesso!")
                    st.balloons()
                    st.rerun()
            else:
                st.error("❌ Preencha pelo menos Cliente e Descrição!")

# =============================================
# ÁREA PRINCIPAL - DASHBOARD
# =============================================

# Carregar dados
df = carregar_dados()

if not df.empty and len(df) > 0:
    # Filtros no topo
    st.markdown("### 🔍 **FILTROS E PESQUISA**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        clientes_unicos = ["Todos"] + list(df['Cliente/Projeto'].unique())
        filtro_cliente = st.selectbox("Cliente/Projeto", clientes_unicos)

    with col2:
        categorias_unicas = ["Todas"] + list(df['Categoria'].unique())
        filtro_categoria = st.selectbox("Categoria", categorias_unicas)

    with col3:
        status_unicos = ["Todos"] + list(df['Status Pagamento'].unique())
        filtro_status = st.selectbox("Status Pagamento", status_unicos)

    with col4:
        if 'Data' in df.columns and not df['Data'].isna().all():
            data_min = df['Data'].min().date() if pd.notnull(df['Data'].min()) else date.today()
        else:
            data_min = date.today()
        periodo = st.date_input("Período (início)", value=data_min)

    # Aplicar filtros
    df_filtrado = df.copy()
    if filtro_cliente != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Cliente/Projeto'] == filtro_cliente]
    if filtro_categoria != "Todas":
        df_filtrado = df_filtrado[df_filtrado['Categoria'] == filtro_categoria]
    if filtro_status != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Status Pagamento'] == filtro_status]
    if 'Data' in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado['Data'].dt.date >= periodo]

    # Métricas principais
    st.markdown("### 📊 **RESUMO EXECUTIVO**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_registros = len(df_filtrado)
        st.metric("📋 Total de Registros", total_registros)

    with col2:
        total_gasto = df_filtrado['Total'].sum()
        st.metric("💰 Valor Total", f"R$ {total_gasto:,.2f}")

    with col3:
        ticket_medio = df_filtrado['Total'].mean() if len(df_filtrado) > 0 else 0
        st.metric("📈 Ticket Médio", f"R$ {ticket_medio:,.2f}")

    with col4:
        pendentes = len(df_filtrado[df_filtrado['Status Pagamento'] == 'Pendente'])
        st.metric("⏳ Pagamentos Pendentes", pendentes)

    # Gráficos
    if len(df_filtrado) > 0:
        st.markdown("### 📈 **ANÁLISES VISUAIS**")

        col1, col2 = st.columns(2)

        with col1:
            # Gráfico por categoria
            gastos_categoria = df_filtrado.groupby('Categoria')['Total'].sum().reset_index()
            if len(gastos_categoria) > 0:
                fig_categoria = px.pie(gastos_categoria, values='Total', names='Categoria',
                                       title="💼 Gastos por Categoria",
                                       color_discrete_sequence=px.colors.qualitative.Set3)
                st.plotly_chart(fig_categoria, use_container_width=True)

        with col2:
            # Gráfico por status
            gastos_status = df_filtrado.groupby('Status Pagamento')['Total'].sum().reset_index()
            if len(gastos_status) > 0:
                fig_status = px.bar(gastos_status, x='Status Pagamento', y='Total',
                                    title="💳 Status dos Pagamentos",
                                    color='Status Pagamento',
                                    color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_status, use_container_width=True)

        # Evolução temporal
        if 'Data' in df_filtrado.columns and not df_filtrado['Data'].isna().all():
            st.markdown("### 📅 **EVOLUÇÃO TEMPORAL**")
            df_temporal = df_filtrado.groupby(df_filtrado['Data'].dt.to_period('M'))['Total'].sum().reset_index()
            df_temporal['Data'] = df_temporal['Data'].astype(str)

            if len(df_temporal) > 0:
                fig_temporal = px.line(df_temporal, x='Data', y='Total',
                                       title="📊 Evolução Mensal dos Gastos",
                                       markers=True)
                fig_temporal.update_traces(line_color='#1e3c72', line_width=3)
                st.plotly_chart(fig_temporal, use_container_width=True)

    # Tabela detalhada
    st.markdown("### 📋 **REGISTROS DETALHADOS**")

    # Configurar colunas para exibição
    colunas_exibir = ['Data', 'Cliente/Projeto', 'Categoria', 'Descrição',
                      'Quantidade', 'Preço Unitário', 'Total', 'Status Pagamento']

    df_display = df_filtrado[colunas_exibir].copy()
    if 'Data' in df_display.columns:
        df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y')

    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Botões de exportação
    st.markdown("### 📥 **EXPORTAR DADOS**")
    col1, col2, col3 = st.columns(3)

    with col1:
        csv = df_filtrado.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📄 Exportar CSV",
            csv,
            f"custos_artico_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv",
            use_container_width=True
        )

    with col2:
        # Exportar Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_filtrado.to_excel(writer, sheet_name='Custos', index=False)
        excel_data = output.getvalue()

        st.download_button(
            "📊 Exportar Excel",
            excel_data,
            f"custos_artico_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col3:
        # Botão de relatório em texto
        relatorio_txt = gerar_relatorio_simples(df_filtrado)
        st.download_button(
            "📑 Gerar Relatório TXT",
            relatorio_txt,
            f"relatorio_custos_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            "text/plain",
            use_container_width=True
        )

else:
    # Estado vazio
    st.markdown("""
    <div style='text-align: center; padding: 4rem;'>
        <h2>📋 Nenhum registro encontrado</h2>
        <p>Comece adicionando seu primeiro custo usando o formulário na barra lateral.</p>
    </div>
    """, unsafe_allow_html=True)

# =============================================
# RODAPÉ
# =============================================
st.markdown("---")
st.markdown("""
<div class="footer">
    <p><strong>Desenvolvido para Ártico Soluções Prediais | © 2024</strong></p>
    <p><em>Sistema de controle de custos profissional - Versão 2.1</em></p>
</div>
""", unsafe_allow_html=True)
