import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import time
import plotly.express as px
import os
from dotenv import load_dotenv
import random
import streamlit.components.v1 as components
import qrcode  # <--- Adicione aqui
from io import BytesIO # <--- Adicione aqui também

# Carrega as variáveis de ambiente
load_dotenv()

# Inicializa o estado para guardar o código que foi lido (evita perder dados nos cliques)
if 'codigo_bipado_atual' not in st.session_state:
    st.session_state['codigo_bipado_atual'] = ""

# ==========================================
# 1. CONFIGURAÇÃO DO BANCO DE DADOS (SQLITE)
# ==========================================
def conectar_banco():
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
        CREATE TABLE IF NOT EXISTS vendedores (
            id_vendedor INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
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
            quantidade_estoque INTEGER DEFAULT 0,
            codigo_barras TEXT UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id_venda INTEGER PRIMARY KEY AUTOINCREMENT,
            id_cliente INTEGER,
            id_vendedor INTEGER,
            data_venda TEXT,
            valor_total REAL,
            forma_pagamento TEXT,
            FOREIGN KEY(id_cliente) REFERENCES clientes(id_cliente),
            FOREIGN KEY(id_vendedor) REFERENCES vendedores(id_vendedor)
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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            data TEXT,
            acao TEXT,
            detalhes TEXT
        )
    ''')
    
    # "Vacinas" para atualizações estruturais sem perda de dados
    try: cursor.execute("ALTER TABLE produtos ADD COLUMN quantidade_estoque INTEGER DEFAULT 0")
    except: pass
    try: cursor.execute("ALTER TABLE produtos ADD COLUMN categoria TEXT DEFAULT 'Normal'")
    except: pass
    try: cursor.execute("ALTER TABLE produtos ADD COLUMN codigo_barras TEXT")
    except: pass
    try: cursor.execute("ALTER TABLE vendas ADD COLUMN id_vendedor INTEGER")
    except: pass
    try: cursor.execute("ALTER TABLE vendas ADD COLUMN forma_pagamento TEXT")
    except: pass
    try: cursor.execute("UPDATE clientes SET email = NULL WHERE email = ''")
    except: pass

    conn.commit()
    conn.close()

@st.cache_resource
def inicializar_sistema():
    criar_tabelas()
    return True

inicializar_sistema()

def registrar_log(acao, detalhes):
    conn_log = None
    try:
        conn_log = conectar_banco()
        cursor = conn_log.cursor()
        data_agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO logs (data, acao, detalhes) VALUES (?, ?, ?)", 
                       (data_agora, acao, detalhes))
        conn_log.commit()
    except: pass 
    finally:
        if conn_log: conn_log.close()

# ==========================================
# 2. SISTEMA DE LOGIN SEGURO
# ==========================================
if 'autenticado' not in st.session_state:
    st.session_state['autenticado'] = False

def fazer_logout():
    st.session_state['autenticado'] = False
    st.session_state['codigo_bipado_atual'] = ""
    st.rerun()

if not st.session_state['autenticado']:
    st.title("🔒 Acesso Restrito")
    st.markdown("Por favor, insira suas credenciais para acessar o PDV.")
    
    with st.container():
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário")
                senha_input = st.text_input("Senha", type="password")
                botao_entrar = st.form_submit_button("Entrar no Sistema")
                
                if botao_entrar:
                    adm_user = os.getenv("USUARIO_ADMIN", "admin")
                    adm_pass = os.getenv("SENHA_ADMIN", "admin")
                    dono_user = os.getenv("USUARIO_DONO", "dono")
                    dono_pass = os.getenv("SENHA_DONO", "dono")
                    
                    if (usuario_input == adm_user and senha_input == adm_pass) or \
                       (usuario_input == dono_user and senha_input == dono_pass):
                        st.session_state['autenticado'] = True
                        st.session_state['usuario_logado'] = usuario_input
                        st.success("Acesso permitido! Carregando...")
                        registrar_log("LOGIN", f"Usuário '{usuario_input}' entrou no sistema.")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ Usuário ou senha incorretos.")
    st.stop()

# ==========================================
# 3. INTERFACE DO APLICATIVO (TABS)
# ==========================================
with st.sidebar:
    st.write(f"👤 Logado como: **{st.session_state.get('usuario_logado', 'Admin')}**")
    st.button("🚪 Sair (Logout)", on_click=fazer_logout, use_container_width=True)

st.title("🍦 PDV e Gestão Inteligente")

aba_pdv, aba_dashboard, aba_produtos, aba_estoque, aba_clientes, aba_vendedores = st.tabs([
    "🛒 Frente de Caixa (PDV)", "📊 Dashboard", "📦 Cadastrar Produtos", "📋 Gerenciar Estoque", "👥 Clientes", "👔 Vendedores"
])

# --- ABA DE FRENTE DE CAIXA (PDV) ---
with aba_pdv:
    st.subheader("🛒 Caixa Omnichannel (Leitor, Celular ou Manual)")
    
    conn = conectar_banco()
    df_cli = pd.read_sql_query("SELECT id_cliente, nome FROM clientes", conn)
    df_vend = pd.read_sql_query("SELECT id_vendedor, nome FROM vendedores", conn)
    df_prod = pd.read_sql_query("SELECT id_produto, categoria, nome_produto, preco_venda, quantidade_estoque, codigo_barras FROM produtos", conn)
    conn.close()
    
    if df_prod.empty or df_vend.empty:
        st.warning("⚠️ Atenção: Cadastre pelo menos 1 Vendedor e 1 Produto nas abas ao lado para liberar o Caixa.")
    else:
        def formatar_nome_produto(row):
            cod_str = f"[{row['codigo_barras']}] " if pd.notnull(row['codigo_barras']) else ""
            return f"{cod_str}{row['nome_produto']} - R$ {row['preco_venda']:.2f} (Estoque: {row['quantidade_estoque']})"
            
        dict_produtos = {row['id_produto']: formatar_nome_produto(row) for _, row in df_prod.iterrows()}
        dict_vendedores = dict(zip(df_vend['id_vendedor'], df_vend['nome']))
        
        dict_clientes = {0: "👤 Consumidor Final (Sem Cadastro)"}
        if not df_cli.empty:
            dict_clientes.update(dict(zip(df_cli['id_cliente'], df_cli['nome'])))
        opcoes_clientes = list(dict_clientes.keys())
        
        # Menu de seleção do modo de entrada do item
        modo_busca = st.radio("Como deseja registrar o produto?", 
                              ["🔍 Maquininha USB/Bluetooth", "📷 Câmera do Celular (Teste)", "📝 Seleção Manual"], 
                              horizontal=True)
        
        # Verifica se a câmera mandou algum código via URL (Query Parameters)
        if "bip_camera" in st.query_params:
            st.session_state['codigo_bipado_atual'] = st.query_params["bip_camera"]
            del st.query_params["bip_camera"] # Limpa a URL imediatamente para não criar loops
            st.rerun()
            
        # Interface baseada no modo escolhido
        if modo_busca == "🔍 Maquininha USB/Bluetooth":
            codigo_bipado = st.text_input("Clique aqui e bipe o produto com a maquininha:", key="leitor_pdv")
            if codigo_bipado:
                st.session_state['codigo_bipado_atual'] = codigo_bipado.strip()
                
        elif modo_busca == "📷 Câmera do Celular (Teste)":
            st.info("Aponte a câmera traseira do celular para o código de barras da embalagem.")
            
            # Componente HTML injetando JavaScript seguro de scanner nativo
            html_scanner = """
            <div id="scanner-container" style="width: 100%; max-width: 400px; height: 230px; margin: 0 auto; background: #222; border: 3px dashed #8e44ad; border-radius: 8px; overflow: hidden;"></div>
            <script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
            <script>
                const html5QrCode = new Html5Qrcode("scanner-container");
                Html5Qrcode.getCameras().then(devices => {
                    html5QrCode.start(
                        { facingMode: "environment" }, 
                        { fps: 15, qrbox: function(w, h) { return { width: w * 0.8, height: h * 0.5 }; } },
                        (decodedText, decodedResult) => {
                            const url = new URL(window.parent.location.href);
                            url.searchParams.set('bip_camera', decodedText);
                            window.parent.location.href = url.href;
                            html5QrCode.stop();
                        },
                        (errorMessage) => {} // Varredura contínua silenciosa
                    ).catch(err => { console.error(err); });
                }).catch(err => {
                    document.getElementById('scanner-container').innerHTML = "<p style='color:red; padding:20px; text-align:center;'>Permissão de câmera negada ou não encontrada.</p>";
                });
            </script>
            """
            components.html(html_scanner, height=250)

        st.markdown("---")
        
        # Resolução do produto escaneado (Se aplicável)
        produto_final_id = None
        if modo_busca != "📝 Seleção Manual":
            codigo_procurado = st.session_state['codigo_bipado_atual']
            if codigo_procurado:
                produto_encontrado = df_prod[df_prod['codigo_barras'] == codigo_procurado]
                if not produto_encontrado.empty:
                    produto_final_id = produto_encontrado['id_produto'].values[0]
                    df_produto_nome = produto_encontrado['nome_produto'].values[0]
                    st.success(f"🎉 **Item Identificado:** {df_produto_nome} (Código: {codigo_procurado})")
                    if st.button("❌ Limpar / Bipar outro"):
                        st.session_state['codigo_bipado_atual'] = ""
                        st.rerun()
                else:
                    st.error(f"❌ O código de barras '{codigo_procurado}' não está associado a nenhum produto cadastrado.")
                    if st.button("🗑️ Limpar Código Errado"):
                        st.session_state['codigo_bipado_atual'] = ""
                        st.rerun()

        # Formulário de Conclusão de Venda
        with st.form("form_venda", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                if modo_busca == "📝 Seleção Manual":
                    produto_final_id = st.selectbox("Selecione o Produto", options=df_prod['id_produto'].tolist(), format_func=lambda x: dict_produtos[x])
                else:
                    if produto_final_id:
                        st.info(f"🛒 **Carregado no Carrinho:** {dict_produtos[produto_final_id]}")
                    else:
                        st.warning("Aguardando leitura de código válidado...")
                        
                quantidade = st.number_input("Quantidade", min_value=1, step=1)
            
            with col2:
                cliente_selecionado = st.selectbox("Identificar Cliente", options=opcoes_clientes, format_func=lambda x: dict_clientes[x])
                vendedor_selecionado = st.selectbox("Vendedor Responsável", options=df_vend['id_vendedor'], format_func=lambda x: dict_vendedores[x])
                forma_pagamento = st.selectbox("Forma de Pagamento", ["PIX", "Cartão de Crédito", "Cartão de Débito", "Dinheiro"])
            
            if st.form_submit_button("💰 Confirmar e Baixar Estoque"):
                if produto_final_id is None:
                    st.error("❌ Erro: Não é possível processar sem um produto válido!")
                else:
                    estoque_atual = df_prod.loc[df_prod['id_produto'] == produto_final_id, 'quantidade_estoque'].values[0]
                    
                    if quantidade > estoque_atual:
                        st.error(f"❌ Estoque insuficiente! Só restam {estoque_atual} unidades deste produto.")
                    else:
                        preco_unitario = df_prod.loc[df_prod['id_produto'] == produto_final_id, 'preco_venda'].values[0]
                        valor_total = float(preco_unitario) * quantidade
                        data_hoje = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        id_cliente_db = cliente_selecionado if cliente_selecionado != 0 else None
                        
                        conn_venda = None
                        try:
                            conn_venda = conectar_banco()
                            cursor = conn_venda.cursor()
                            cursor.execute("INSERT INTO vendas (id_cliente, id_vendedor, data_venda, valor_total, forma_pagamento) VALUES (?, ?, ?, ?, ?)", 
                                           (id_cliente_db, vendedor_selecionado, data_hoje, valor_total, forma_pagamento))
                            id_nova_venda = cursor.lastrowid
                            
                            cursor.execute("INSERT INTO itens_venda (id_venda, id_produto, quantidade, preco_unitario) VALUES (?, ?, ?, ?)",
                                           (id_nova_venda, produto_final_id, quantidade, float(preco_unitario)))
                            
                            cursor.execute("UPDATE produtos SET quantidade_estoque = quantidade_estoque - ? WHERE id_produto = ?",
                                           (quantidade, produto_final_id))
                            conn_venda.commit()
                            
                            st.session_state['codigo_bipado_atual'] = "" # Limpa a memória do leitor
                            registrar_log("VENDA", f"Vendedor ID {vendedor_selecionado} vendeu R$ {valor_total:.2f} via {forma_pagamento}")
                            st.success(f"✅ Venda de R$ {valor_total:.2f} registrada com sucesso!")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao registrar: {e}")
                        finally:
                            if conn_venda: conn_venda.close()

# --- ABA DE DASHBOARD ---
with aba_dashboard:
    st.subheader("Inteligência de Vendas")
    
    conn = conectar_banco()
    query_historico = '''
        SELECT 
            COALESCE(c.nome, 'Consumidor Final') AS Cliente, vend.nome AS Vendedor, v.data_venda AS "Data", 
            p.nome_produto AS Produto, i.quantidade AS Qtd, v.forma_pagamento AS "Pagamento",
            (i.quantidade * i.preco_unitario) AS "Total (R$)",
            ((i.quantidade * i.preco_unitario) - (i.quantidade * p.custo_unidade)) AS "Lucro (R$)"
        FROM vendas v
        LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
        LEFT JOIN vendedores vend ON v.id_vendedor = vend.id_vendedor
        JOIN itens_venda i ON v.id_venda = i.id_venda
        JOIN produtos p ON i.id_produto = p.id_produto
        ORDER BY v.data_venda DESC
    '''
    try: df_historico = pd.read_sql_query(query_historico, conn)
    except: df_historico = pd.DataFrame()
    finally: conn.close()
    
    if df_historico.empty:
        st.info("O Dashboard será gerado após a sua primeira venda.")
    else:
        faturamento_total = df_historico['Total (R$)'].sum()
        lucro_total = df_historico['Lucro (R$)'].sum()
        
        try:
            vendedor_top = df_historico.groupby('Vendedor')['Total (R$)'].sum().idxmax()
            pagamento_top = df_historico['Pagamento'].mode()[0]
        except:
            vendedor_top = "N/A"
            pagamento_top = "N/A"

        colA, colB, colC, colD = st.columns(4)
        colA.metric("Faturamento Global", f"R$ {faturamento_total:,.2f}")
        colB.metric("Lucro Líquido", f"R$ {lucro_total:,.2f}")
        colC.metric("🏆 Melhor Vendedor", vendedor_top)
        colD.metric("💳 Pagamento Favorito", pagamento_top)

        st.markdown("---")
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            df_vendedores = df_historico.groupby('Vendedor')['Total (R$)'].sum().reset_index()
            st.plotly_chart(px.bar(df_vendedores, x='Vendedor', y='Total (R$)', title='Desempenho por Vendedor', color='Vendedor', text_auto='.2f'), use_container_width=True)
            
        with col_graf2:
            df_pagamentos = df_historico.groupby('Pagamento')['Total (R$)'].sum().reset_index()
            st.plotly_chart(px.pie(df_pagamentos, names='Pagamento', values='Total (R$)', title='Métodos de Pagamento Utilizados', hole=0.4), use_container_width=True)
            
        st.markdown("### 📋 Extrato Completo de Operações")
        st.dataframe(df_historico, use_container_width=True, hide_index=True)


# --- ABA DE CADASTRAR PRODUTOS ---
with aba_produtos:
    st.subheader("Cadastro em Lote de Produtos")
    st.info("DICA: Se o produto já tem código na embalagem, digite-o. Se você deixar em branco, decida abaixo se o sistema deve ou não inventar um.")
    
    gerar_codigo_auto = st.checkbox("⚙️ Gerar código automático ('SYS-...') para produtos que eu deixar em branco?", value=True)
    
    df_vazio = pd.DataFrame(columns=["Código de Barras (Opcional)", "Categoria", "Nome/Sabor", "Preço Venda (R$)", "Custo (R$)", "Estoque Inicial"])
    
    df_editado = st.data_editor(
        df_vazio,
        num_rows="dynamic",
        column_config={
            "Código de Barras (Opcional)": st.column_config.TextColumn("Código de Barras (Opcional)"),
            "Categoria": st.column_config.SelectboxColumn("Categoria", options=["Normal", "Big", "Paleta", "Diversos"], required=True),
            "Nome/Sabor": st.column_config.TextColumn("Nome/Sabor", required=True),
            "Preço Venda (R$)": st.column_config.NumberColumn("Preço Venda (R$)", min_value=0.0, format="%.2f", required=True),
            "Custo (R$)": st.column_config.NumberColumn("Custo (R$)", min_value=0.0, format="%.2f"),
            "Estoque Inicial": st.column_config.NumberColumn("Estoque Inicial", min_value=0, step=1, required=True)
        },
        use_container_width=True, hide_index=True
    )
    
    if st.button("💾 Gravar Produtos no Estoque"):
        linhas_validas = df_editado.dropna(subset=["Categoria", "Nome/Sabor"])
        if linhas_validas.empty:
            st.warning("⚠️ Preencha pelo menos um produto para gravar.")
        else:
            conn_prod = None
            try:
                conn_prod = conectar_banco()
                cursor = conn_prod.cursor()
                qtd_cadastrada = 0
                
                for index, linha in linhas_validas.iterrows():
                    categoria = linha["Categoria"]
                    nome = linha["Nome/Sabor"]
                    preco = float(linha["Preço Venda (R$)"]) if pd.notnull(linha["Preço Venda (R$)"]) else 0.0
                    custo = float(linha["Custo (R$)"]) if pd.notnull(linha["Custo (R$)"]) else 0.0
                    estoque = int(linha["Estoque Inicial"]) if pd.notnull(linha["Estoque Inicial"]) else 0
                    
                    cod = str(linha["Código de Barras (Opcional)"]).strip()
                    if not cod or cod == "nan" or cod == "None":
                        if gerar_codigo_auto:
                            cod = f"SYS-{random.randint(100000, 999999)}"
                        else:
                            cod = None  
                    
                    cursor.execute("INSERT INTO produtos (categoria, nome_produto, preco_venda, custo_unidade, quantidade_estoque, codigo_barras) VALUES (?, ?, ?, ?, ?, ?)", 
                                   (categoria, nome, preco, custo, estoque, cod))
                    qtd_cadastrada += 1
                conn_prod.commit()
                registrar_log("NOVOS_PRODUTOS", f"{qtd_cadastrada} produtos gravados.")
                st.success(f"✅ {qtd_cadastrada} produto(s) gravado(s)!")
                time.sleep(1.5)
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("❌ Erro: Um ou mais Códigos de Barras digitados já existem no sistema. Eles devem ser únicos.")
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
            finally:
                if conn_prod: conn_prod.close()

# --- ABA DE GERENCIAR ESTOQUE ---
with aba_estoque:
    st.subheader("Gerenciar Estoque e Etiquetas QR Code")
    from io import BytesIO
    
    conn = conectar_banco()
    df_prod_lista = pd.read_sql_query("SELECT id_produto as ID, codigo_barras as 'Código', nome_produto as Produto, preco_venda FROM produtos", conn)
    conn.close()
    
    if not df_prod_lista.empty:
        st.dataframe(df_prod_lista, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("🖨️ Gerador de QR Code para Etiqueta")
        
        produto_qr = st.selectbox("Escolha o produto para gerar o QR Code:", options=df_prod_lista['ID'], format_func=lambda x: f"{df_prod_lista.loc[df_prod_lista['ID']==x, 'Produto'].values[0]}")
        
        if st.button("Gerar QR Code"):
            cod = df_prod_lista.loc[df_prod_lista['ID']==produto_qr, 'Código'].values[0]
            if cod:
                # Cria a imagem do QR Code
                if st.button("Gerar QR Code"):
            cod = df_prod_lista.loc[df_prod_lista['ID']==produto_qr, 'Código'].values[0]
            if cod:
                # Ajustamos o box_size e o border para facilitar a leitura
                qr = qrcode.QRCode(
                    version=1, 
                    error_correction=qrcode.constants.ERROR_CORRECT_H, # Alta correção de erros
                    box_size=15, 
                    border=4
                )
                qr.add_data(cod)
                qr.make(fit=True)
                
                # Cores estritas
                img = qr.make_image(fill_color="black", back_color="white")
                
                buf = BytesIO()
                img.save(buf, format="PNG")
                st.image(buf, caption=f"Código: {cod}", width=300)
                st.info("Dica: Não deixe a tela do monitor com muito reflexo de luz.")
                
                # Converte para exibir no Streamlit
                buf = BytesIO()
                img.save(buf, format="PNG")
                st.image(buf, caption=f"QR Code para: {cod}", width=200)
                st.info("Clique com o botão direito na imagem e selecione 'Salvar imagem como' para imprimir sua etiqueta.")
            else:
                st.error("Este produto não possui código cadastrado.")

        st.markdown("### 🗑️ Remover Produto")
        with st.form("form_remover_produto"):
            produto_a_remover = st.selectbox("Selecione o produto a excluir", options=df_prod_lista['ID'], format_func=lambda x: f"ID: {x}")
            if st.form_submit_button("Remover Definitivamente"):
                conn_rem = conectar_banco()
                conn_rem.cursor().execute("DELETE FROM produtos WHERE id_produto = ?", (produto_a_remover,))
                conn_rem.commit()
                conn_rem.close()
                st.success("✅ Produto removido!")
                st.rerun()
    else:
        st.info("Estoque vazio.")

# --- ABA DE CLIENTES ---
with aba_clientes:
    st.subheader("Gestão de Clientes")
    with st.expander("➕ Adicionar Novo Cliente", expanded=True):
        with st.form("form_cliente", clear_on_submit=True):
            nome = st.text_input("Nome Completo *")
            telefone = st.text_input("Telefone")
            email = st.text_input("E-mail")
            if st.form_submit_button("💾 Salvar Cliente") and nome.strip():
                conn = conectar_banco()
                conn.cursor().execute("INSERT INTO clientes (nome, email, telefone, data_cadastro) VALUES (?, ?, ?, ?)", (nome, email, telefone, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
                conn.close()
                st.success("✅ Cliente Salvo!")
                time.sleep(1)
                st.rerun()
                
    conn = conectar_banco()
    df_clientes_lista = pd.read_sql_query("SELECT id_cliente as ID, nome, telefone, email FROM clientes", conn)
    conn.close()
    st.dataframe(df_clientes_lista, use_container_width=True, hide_index=True)

# --- ABA DE VENDEDORES ---
with aba_vendedores:
    st.subheader("👔 Gestão da Equipe de Vendas")
    colV1, colV2 = st.columns(2)
    
    with colV1:
        with st.form("form_vendedor", clear_on_submit=True):
            st.markdown("**Cadastrar Novo Vendedor**")
            nome_vendedor = st.text_input("Nome do Vendedor *")
            if st.form_submit_button("Salvar Vendedor"):
                if nome_vendedor.strip():
                    conn_vend = conectar_banco()
                    conn_vend.cursor().execute("INSERT INTO vendedores (nome, data_cadastro) VALUES (?, ?)", (nome_vendedor, datetime.now().strftime("%Y-%m-%d")))
                    conn_vend.commit()
                    conn_vend.close()
                    st.success("Vendedor Adicionado!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Digite o nome.")
                    
    with colV2:
        conn = conectar_banco()
        df_vendedores_lista = pd.read_sql_query("SELECT id_vendedor as ID, nome as Vendedor, data_cadastro as 'Data de Início' FROM vendedores", conn)
        conn.close()
        
        if not df_vendedores_lista.empty:
            st.dataframe(df_vendedores_lista, use_container_width=True, hide_index=True)
            with st.form("form_rem_vendedor"):
                vend_rem = st.selectbox("Demitir/Remover Vendedor", options=df_vendedores_lista['ID'], format_func=lambda x: f"ID: {x}")
                if st.form_submit_button("Remover"):
                    conn_rem = conectar_banco()
                    conn_rem.cursor().execute("DELETE FROM vendedores WHERE id_vendedor = ?", (vend_rem,))
                    conn_rem.commit()
                    conn_rem.close()
                    st.success("Removido!")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("Adicione o seu primeiro vendedor.")
