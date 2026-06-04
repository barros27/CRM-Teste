import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. CONFIGURAÇÃO DO BANCO DE DADOS (SQLITE)
# ==========================================
def conectar_banco():
    # Aumentamos o timeout para que o banco espere até 15 segundos se houver uma fila de ações, evitando o erro "locked"
    return sqlite3.connect('meu_crm.db', timeout=15)

def criar_tabelas():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id_cliente INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE,
            telefone TEXT,
            status TEXT DEFAULT 'Ativo',
            origem TEXT,
            data_cadastro TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id_produto INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT NOT NULL,
            nome_produto TEXT NOT NULL,
            preco_venda REAL NOT NULL,
            custo_unidade REAL,
            quantidade_estoque INTEGER DEFAULT 0
        )
    ''')
    
    try: cursor.execute("ALTER TABLE produtos ADD COLUMN quantidade_estoque INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
        
    try: cursor.execute("ALTER TABLE produtos ADD COLUMN categoria TEXT DEFAULT 'Normal'")
    except sqlite3.OperationalError: pass
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id_venda INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER,
            data_venda TEXT,
            valor_total REAL,
            FOREIGN KEY(id_cliente) REFERENCES clientes(id_cliente)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_venda (
            id_item INTEGER PRIMARY KEY AUTOINCREMENT,
            id_venda INTEGER,
            id_produto INTEGER,
            quantidade INTEGER,
            preco_unitario REAL,
            FOREIGN KEY(id_venda) REFERENCES vendas(id_venda),
            FOREIGN KEY(id_produto) REFERENCES produtos(id_produto)
        )
    ''')
    
    # "Vacina": Corrige e-mails em branco antigos que estavam a causar o erro de duplicação
    try:
        cursor.execute("UPDATE clientes SET email = NULL WHERE email = ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

# O @st.cache_resource garante que o banco só seja configurado 1 VEZ ao ligar o site.
# Isso acaba imediatamente com a lentidão e com os bloqueios (locks) constantes do SQLite.
@st.cache_resource
def inicializar_sistema():
    criar_tabelas()
    return True

inicializar_sistema()

# ==========================================
# 2. SISTEMA DE LOGIN E SEGURANÇA
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def fazer_logout():
    st.session_state['autenticado'] = False
    st.rerun()

if not st.session_state['autenticado']:
    st.title("🔒 Acesso Restrito")
    st.markdown("Por favor, insira as suas credenciais.")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário")
                senha_input = st.text_input("Senha", type="password")
                botao_entrar = st.form_submit_button("Entrar no Sistema")
                
                if botao_entrar:
                    # Lê os valores protegidos do ficheiro .env
                    # Certifique-se de que o arquivo .env está na mesma pasta!
                    adm_user = os.getenv("USUARIO_ADMIN")
                    adm_pass = os.getenv("SENHA_ADMIN")
                    dono_user = os.getenv("USUARIO_DONO")
                    dono_pass = os.getenv("SENHA_DONO")
                    
                    if (usuario_input == adm_user and senha_input == adm_pass) or \
                       (usuario_input == dono_user and senha_input == dono_pass):
                        st.session_state['autenticado'] = True
                        st.success("Acesso permitido! Carregando...")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Usuário ou senha incorretos.")
    st.stop()


# ==========================================
# 3. INTERFACE DO APLICATIVO (STREAMLIT)
# ==========================================
with st.sidebar:
    st.write("👤 Logado no sistema")
    st.button("🚪 Sair (Logout)", on_click=fazer_logout, use_container_width=True)

st.title("🍦 CRM Picolés e Sorvetes")

aba_cadastro, aba_produtos, aba_gerenciar_produtos, aba_vendas, aba_dashboard = st.tabs([
    "👥 Clientes", "📦 Cadastrar Picolés (Lote)", "📋 Gerenciar Estoque", "🛒 Nova Venda", "📊 Dashboard"
])

# --- ABA DE CADASTRO E GERENCIAMENTO DE CLIENTES ---
with aba_cadastro:
    st.subheader("👥 Gestão de Clientes")
    
    col_add, col_rem = st.columns(2)
    
    # --- LADO ESQUERDO: ADICIONAR ---
    with col_add:
        with st.expander("➕ Adicionar Novo Cliente", expanded=True):
            with st.form("form_cliente", clear_on_submit=True):
                nome = st.text_input("Nome Completo * (Obrigatório)")
                telefone = st.text_input("Telefone (Opcional)")
                email = st.text_input("E-mail (Opcional)")
                origem = st.selectbox("Origem de Captação", ["Instagram", "Indicação", "Panfleto", "Passou na porta", "Outros"])
                
                botao_salvar = st.form_submit_button("💾 Salvar Cliente")
                
                if botao_salvar:
                    if nome.strip() == "":
                        st.error("❌ O campo 'Nome' é obrigatório!")
                    else:
                        conn = None
                        try:
                            email_db = email.strip() if email.strip() != "" else None
                            telefone_db = telefone.strip() if telefone.strip() != "" else None
                            
                            conn = conectar_banco()
                            cursor = conn.cursor()
                            data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            cursor.execute('''
                                INSERT INTO clientes (nome, email, telefone, origem, data_cadastro)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (nome, email_db, telefone_db, origem, data_hoje))
                            conn.commit()
                            
                            st.success(f"✅ Cliente {nome} cadastrado com sucesso!")
                            time.sleep(1)
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("❌ Este e-mail já está cadastrado num outro cliente.")
                        except Exception as e:
                            st.error(f"Erro inesperado: {e}")
                        finally:
                            # O bloco finally garante que a porta do banco é fechada mesmo em caso de erro!
                            if conn:
                                conn.close()

    # --- LADO DIREITO: REMOVER ---
    with col_rem:
        with st.expander("🗑️ Remover Cliente Existente", expanded=True):
            conn = conectar_banco()
            df_clientes_lista = pd.read_sql_query("SELECT id_cliente, nome, email, telefone, origem FROM clientes", conn)
            conn.close()

            if not df_clientes_lista.empty:
                with st.form("form_remover_cliente"):
                    cliente_id_para_remover = st.selectbox(
                        "Selecione o cliente para excluir",
                        options=df_clientes_lista['id_cliente'],
                        format_func=lambda x: df_clientes_lista.loc[df_clientes_lista['id_cliente'] == x, 'nome'].values[0]
                    )
                    
                    st.write("") 
                    st.write("")
                    
                    if st.form_submit_button("🚨 Excluir Definitivamente"):
                        conn_rem = None
                        try:
                            conn_rem = conectar_banco()
                            cursor = conn_rem.cursor()
                            cursor.execute("DELETE FROM clientes WHERE id_cliente = ?", (cliente_id_para_remover,))
                            conn_rem.commit()
                            st.success("✅ Cliente removido com sucesso!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao remover: {e}")
                        finally:
                            if conn_rem:
                                conn_rem.close()
            else:
                st.info("Nenhum cliente para remover.")

    st.markdown("---")
    st.subheader("📋 Lista de Clientes")

    if not df_clientes_lista.empty:
        st.dataframe(df_clientes_lista, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum cliente cadastrado no momento.")


# --- ABA DE CADASTRAR PRODUTOS (EM LOTE) ---
with aba_produtos:
    st.subheader("Cadastro em Lote de Picolés")
    st.write("Adicione linhas na tabela abaixo para registar vários sabores de uma só vez.")
    
    df_vazio = pd.DataFrame(columns=["Tipo de Picolé", "Sabor", "Preço Venda (R$)", "Custo (R$)", "Estoque Adicionado"])
    
    df_editado = st.data_editor(
        df_vazio,
        num_rows="dynamic",
        column_config={
            "Tipo de Picolé": st.column_config.SelectboxColumn(
                "Tipo de Picolé",
                options=["Normal", "Big", "Paleta Mexicana", "Outros"],
                required=True
            ),
            "Sabor": st.column_config.TextColumn("Sabor", required=True),
            "Preço Venda (R$)": st.column_config.NumberColumn("Preço Venda (R$)", min_value=0.0, format="%.2f", required=True),
            "Custo (R$)": st.column_config.NumberColumn("Custo (R$)", min_value=0.0, format="%.2f"),
            "Estoque Adicionado": st.column_config.NumberColumn("Estoque Adicionado", min_value=0, step=1, required=True)
        },
        use_container_width=True,
        hide_index=True
    )
    
    if st.button("💾 Gravar Todos os Picolés"):
        linhas_validas = df_editado.dropna(subset=["Tipo de Picolé", "Sabor"])
        if linhas_validas.empty:
            st.warning("⚠️ Preencha pelo menos um picolé (Tipo e Sabor) para poder gravar.")
        else:
            conn_prod = None
            try:
                conn_prod = conectar_banco()
                cursor = conn_prod.cursor()
                for index, linha in linhas_validas.iterrows():
                    categoria = linha["Tipo de Picolé"]
                    sabor = linha["Sabor"]
                    preco = float(linha["Preço Venda (R$)"]) if pd.notnull(linha["Preço Venda (R$)"]) else 0.0
                    custo = float(linha["Custo (R$)"]) if pd.notnull(linha["Custo (R$)"]) else 0.0
                    estoque = int(linha["Estoque Adicionado"]) if pd.notnull(linha["Estoque Adicionado"]) else 0
                    
                    cursor.execute("INSERT INTO produtos (categoria, nome_produto, preco_venda, custo_unidade, quantidade_estoque) VALUES (?, ?, ?, ?, ?)", 
                                   (categoria, sabor, preco, custo, estoque))
                conn_prod.commit()
                st.success(f"✅ {len(linhas_validas)} picolé(s) gravado(s) com sucesso!")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar em lote: {e}")
            finally:
                if conn_prod:
                    conn_prod.close()

# --- NOVA ABA: GERENCIAR PRODUTOS E ESTOQUE ---
with aba_gerenciar_produtos:
    st.subheader("Gerenciar Estoque de Picolés")
    
    conn = conectar_banco()
    df_prod_lista = pd.read_sql_query("SELECT id_produto, categoria, nome_produto as sabor, preco_venda, custo_unidade, quantidade_estoque FROM produtos", conn)
    conn.close()
    
    if df_prod_lista.empty:
        st.info("Nenhum picolé cadastrado no momento. Use a aba ao lado para registar o seu catálogo.")
    else:
        st.dataframe(df_prod_lista, use_container_width=True, hide_index=True)
        
        st.markdown("### 🗑️ Remover Picolé")
        with st.form("form_remover_produto"):
            dict_produtos_remover = {
                row['id_produto']: f"[{row['categoria']}] {row['sabor']}" 
                for _, row in df_prod_lista.iterrows()
            }
            produto_a_remover = st.selectbox(
                "Selecione o picolé que deseja excluir do sistema", 
                options=df_prod_lista['id_produto'], 
                format_func=lambda x: f"{dict_produtos_remover[x]} (ID: {x})"
            )
            
            if st.form_submit_button("🚨 Remover Definitivamente"):
                conn_rem_prod = None
                try:
                    conn_rem_prod = conectar_banco()
                    cursor = conn_rem_prod.cursor()
                    cursor.execute("DELETE FROM produtos WHERE id_produto = ?", (produto_a_remover,))
                    conn_rem_prod.commit()
                    st.success("✅ Produto removido com sucesso!")
                    time.sleep(1.5) 
                    st.rerun() 
                except Exception as e:
                    st.error(f"Erro inesperado: {e}")
                finally:
                    if conn_rem_prod:
                        conn_rem_prod.close()

# --- ABA DE REGISTRAR VENDA ---
with aba_vendas:
    st.subheader("Registrar Nova Venda")
    
    conn = conectar_banco()
    df_cli = pd.read_sql_query("SELECT id_cliente, nome FROM clientes", conn)
    df_prod = pd.read_sql_query("SELECT id_produto, categoria, nome_produto, preco_venda, quantidade_estoque FROM produtos", conn)
    conn.close()
    
    if df_cli.empty or df_prod.empty:
        st.warning("⚠️ Cadastre pelo menos 1 Cliente e 1 Picolé nas abas ao lado antes de registar vendas.")
    else:
        with st.form("form_venda", clear_on_submit=True):
            dict_clientes = dict(zip(df_cli['id_cliente'], df_cli['nome']))
            dict_produtos = {
                row['id_produto']: f"[{row['categoria']}] {row['nome_produto']} (Estoque: {row['quantidade_estoque']})" 
                for _, row in df_prod.iterrows()
            }
            
            cliente_selecionado = st.selectbox("Selecione o Cliente", options=df_cli['id_cliente'], format_func=lambda x: dict_clientes[x])
            produto_selecionado = st.selectbox("Selecione o Picolé", options=df_prod['id_produto'], format_func=lambda x: dict_produtos[x])
            quantidade = st.number_input("Quantidade da Venda", min_value=1, step=1)
            
            if st.form_submit_button("💰 Confirmar Venda"):
                estoque_atual = df_prod.loc[df_prod['id_produto'] == produto_selecionado, 'quantidade_estoque'].values[0]
                
                if quantidade > estoque_atual:
                    st.error(f"❌ Estoque insuficiente! Só tem {estoque_atual} unidades deste picolé na geladeira.")
                else:
                    preco_unitario = df_prod.loc[df_prod['id_produto'] == produto_selecionado, 'preco_venda'].values[0]
                    valor_total = float(preco_unitario) * quantidade
                    data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    conn_venda = None
                    try:
                        conn_venda = conectar_banco()
                        cursor = conn_venda.cursor()
                        
                        cursor.execute("INSERT INTO vendas (id_cliente, data_venda, valor_total) VALUES (?, ?, ?)", 
                                       (cliente_selecionado, data_hoje, valor_total))
                        id_nova_venda = cursor.lastrowid
                        
                        cursor.execute("INSERT INTO itens_venda (id_venda, id_produto, quantidade, preco_unitario) VALUES (?, ?, ?, ?)",
                                       (id_nova_venda, produto_selecionado, quantidade, float(preco_unitario)))
                        
                        cursor.execute("UPDATE produtos SET quantidade_estoque = quantidade_estoque - ? WHERE id_produto = ?",
                                       (quantidade, produto_selecionado))
                        conn_venda.commit()
                        st.success(f"✅ Venda de R$ {valor_total:.2f} registada com sucesso! O estoque foi reduzido.")
                    except Exception as e:
                        st.error(f"Erro ao registar a venda: {e}")
                    finally:
                        if conn_venda:
                            conn_venda.close()

# --- ABA DE DASHBOARD E VISUALIZAÇÃO ---
with aba_dashboard:
    st.subheader("Visão Geral do Negócio")
    
    conn = conectar_banco()
    df_clientes = pd.read_sql_query("SELECT * FROM clientes", conn)
    
    # Busca o produto mais vendido
    query_top_prod = "SELECT p.nome_produto, SUM(i.quantidade) as qtd FROM itens_venda i JOIN produtos p ON i.id_produto = p.id_produto GROUP BY p.nome_produto ORDER BY qtd DESC LIMIT 1"
    try:
        df_top_prod = pd.read_sql_query(query_top_prod, conn)
    except:
        df_top_prod = pd.DataFrame()
    
    # Calcula o valor total investido no estoque atual
    query_estoque_valor = "SELECT SUM(quantidade_estoque * custo_unidade) as valor_estoque FROM produtos"
    try:
        df_estoque_valor = pd.read_sql_query(query_estoque_valor, conn)
        valor_investido_estoque = df_estoque_valor['valor_estoque'].fillna(0).iloc[0] if not df_estoque_valor.empty else 0.0
    except:
        valor_investido_estoque = 0.0
    
    conn.close()
    
    if df_clientes.empty:
        st.info("Nenhum cliente cadastrado ainda. Use a aba ao lado para adicionar o primeiro!")
    else:
        colA, colB, colC, colD = st.columns(4)
        
        colA.metric("Total de Clientes", len(df_clientes))
        
        melhor_origem = df_clientes['origem'].mode()[0] if not df_clientes['origem'].empty else "N/A"
        colB.metric("Melhor Canal (Marketing)", melhor_origem)
        
        produto_campeao = df_top_prod['nome_produto'].iloc[0] if not df_top_prod.empty and not pd.isna(df_top_prod['nome_produto'].iloc[0]) else "N/A"
        colC.metric("🏆 Picolé Mais Vendido", produto_campeao)
        
        colD.metric("📦 Valor Investido em Estoque", f"R$ {valor_investido_estoque:,.2f}")

        st.markdown("---")
        st.subheader("🛍️ Histórico e Painel Financeiro")
        
        query_historico = '''
            SELECT 
                c.nome AS Cliente,
                v.data_venda AS "Data da Compra",
                p.categoria AS "Tipo de Picolé",
                p.nome_produto AS Sabor,
                i.quantidade AS Quantidade,
                (i.quantidade * i.preco_unitario) AS "Valor Total (R$)",
                (i.quantidade * p.custo_unidade) AS "Custo das Vendas (R$)",
                ((i.quantidade * i.preco_unitario) - (i.quantidade * p.custo_unidade)) AS "Lucro Líquido (R$)"
            FROM vendas v
            JOIN clientes c ON v.id_cliente = c.id_cliente
            JOIN itens_venda i ON v.id_venda = i.id_venda
            JOIN produtos p ON i.id_produto = p.id_produto
            ORDER BY v.data_venda DESC
        '''
        
        conn = conectar_banco()
        try:
            df_historico = pd.read_sql_query(query_historico, conn)
        except:
            df_historico = pd.DataFrame()
        finally:
            conn.close()
        
        if df_historico.empty:
            st.info("Nenhuma venda registrada ainda.")
        else:
            col_filtro1, col_filtro2 = st.columns(2)
            
            with col_filtro1:
                lista_clientes_compras = ["Todos os Clientes"] + df_historico['Cliente'].unique().tolist()
                cliente_filtro = st.selectbox("👤 Procurar histórico de um cliente:", lista_clientes_compras)
                
            with col_filtro2:
                lista_produtos_compras = ["Todos os Produtos"] + df_historico['Sabor'].unique().tolist()
                produto_filtro = st.selectbox("🍦 Filtrar vendas por um Picolé específico:", lista_produtos_compras)
            
            df_historico_filtrado = df_historico.copy()
            
            if cliente_filtro != "Todos os Clientes":
                df_historico_filtrado = df_historico_filtrado[df_historico_filtrado['Cliente'] == cliente_filtro]
                
            if produto_filtro != "Todos os Produtos":
                df_historico_filtrado = df_historico_filtrado[df_historico_filtrado['Sabor'] == produto_filtro]
                
            st.markdown("### 💰 Resumo Financeiro (Baseado nos Filtros)")
            
            faturamento_total = df_historico_filtrado['Valor Total (R$)'].sum()
            custo_total = df_historico_filtrado['Custo das Vendas (R$)'].sum()
            lucro_total = df_historico_filtrado['Lucro Líquido (R$)'].sum()
            margem = (lucro_total / faturamento_total * 100) if faturamento_total > 0 else 0.0

            colF1, colF2, colF3, colF4 = st.columns(4)
            colF1.metric("Faturamento", f"R$ {faturamento_total:,.2f}")
            colF2.metric("Custo das Vendas (CMV)", f"R$ {custo_total:,.2f}")
            colF3.metric("Lucro Líquido", f"R$ {lucro_total:,.2f}")
            colF4.metric("Margem de Lucro", f"{margem:.1f}%")

            st.markdown("### 📈 Painel de Indicadores")
            
            df_historico_filtrado['Data Curta'] = pd.to_datetime(df_historico_filtrado['Data da Compra']).dt.date
            df_historico_filtrado['Mês-Ano'] = pd.to_datetime(df_historico_filtrado['Data da Compra']).dt.to_period('M').astype(str)
            
            df_mensal = df_historico_filtrado.groupby('Mês-Ano')['Valor Total (R$)'].sum().reset_index()
            df_mensal = df_mensal.sort_values(by='Mês-Ano')
            fig_mensal = px.bar(df_mensal, x='Mês-Ano', y='Valor Total (R$)', 
                                title='Faturamento Mensal (R$)', text_auto='.2f',
                                color_discrete_sequence=['#8e44ad'])
            st.plotly_chart(fig_mensal, use_container_width=True)
            
            col_grafico1, col_grafico2 = st.columns(2)
            
            with col_grafico1:
                df_faturamento = df_historico_filtrado.groupby('Data Curta')['Valor Total (R$)'].sum().reset_index()
                fig_fat = px.line(df_faturamento, x='Data Curta', y='Valor Total (R$)', 
                                  title='Faturamento Diário (R$)', markers=True,
                                  color_discrete_sequence=['#2ecc71'])
                st.plotly_chart(fig_fat, use_container_width=True)
                
            with col_grafico2:
                df_produtos = df_historico_filtrado.groupby('Sabor')['Quantidade'].sum().reset_index()
                df_produtos = df_produtos.sort_values(by='Quantidade', ascending=True)
                fig_prod = px.bar(df_produtos, x='Quantidade', y='Sabor', orientation='h', 
                                  title='Ranking de Produtos (Unidades)',
                                  color_discrete_sequence=['#3498db'])
                st.plotly_chart(fig_prod, use_container_width=True)

            st.markdown("---")
            st.markdown("### 📋 Tabela de Dados Brutos")
            st.dataframe(df_historico_filtrado, use_container_width=True, hide_index=True)