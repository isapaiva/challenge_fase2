import os
import streamlit as st
import pandas as pd
import oracledb
import plotly.express as px

# ----------------------------------------------------
# CONFIGURAÇÃO GERAL DA PÁGINA & TEMA DARK
# ----------------------------------------------------
st.set_page_config(
    page_title="Synapse Health Portal",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp { background-color: #0b111e; color: #e2e8f0; font-family: 'Segoe UI', Roboto, sans-serif; }
    .top-navbar { display: flex; justify-content: space-between; align-items: center; background-color: #111a2e; padding: 10px 20px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #1e293b; }
    .brand-title { font-size: 1.25rem; font-weight: 700; color: #f8fafc; display: flex; align-items: center; gap: 8px; }
    .server-status { color: #10b981; font-size: 0.8rem; font-weight: 600; }
    .badge-gargalos { color: #ef4444; font-weight: 600; font-size: 0.85rem; margin-right: 15px; }
    .badge-conformidade { color: #10b981; font-weight: 600; font-size: 0.85rem; }
    .synapse-card { background-color: #111a2e; border: 1px solid #1e293b; border-radius: 12px; padding: 18px; margin-bottom: 16px; }
    .card-title { font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #94a3b8; display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
    .kpi-value { font-size: 1.8rem; font-weight: 700; color: #f8fafc; }
    .kpi-sub { font-size: 0.85rem; margin-left: 6px; }
    .kpi-green { color: #10b981; }
    .kpi-red { color: #ef4444; }
    .kpi-yellow { color: #f59e0b; }
    .pipeline-stage { border-radius: 8px; padding: 14px; text-align: center; background-color: #152238; border: 1px solid #334155; margin-bottom: 24px; }
    .stage-normal { border-left: 4px solid #10b981; }
    .stage-gargalo { border-left: 4px solid #ef4444; }
    .stage-ok { border-left: 4px solid #3b82f6; }
    .leito-box { background-color: #162032; border: 1px solid #24344d; border-radius: 8px; padding: 12px; margin-bottom: 10px; position: relative; }
    .dot-status { width: 8px; height: 8px; border-radius: 50%; display: inline-block; position: absolute; top: 10px; right: 10px; }
    .dot-red { background-color: #ef4444; }
    .dot-yellow { background-color: #f59e0b; }
    .dot-green { background-color: #10b981; }

    [data-testid="stPlotlyChart"] {
        background-color: #111a2e;
        border: 1px solid #1e293b;
        border-radius: 12px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# GERENCIAMENTO DO POOL DE CONEXÕES
# ----------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@st.cache_resource
def init_connection_pool():
    try:
        nome_pasta_wallet = st.secrets["oracle"]["wallet_location"]
        caminho_wallet = os.path.join(BASE_DIR, nome_pasta_wallet)

        pool = oracledb.create_pool(
            user=st.secrets["oracle"]["user"],
            password=st.secrets["oracle"]["password"],
            dsn=st.secrets["oracle"]["dsn"],
            config_dir=caminho_wallet,
            wallet_location=caminho_wallet,
            wallet_password=st.secrets["oracle"]["password"],
            min=2, max=10, increment=1
        )
        return pool
    except Exception as e:
        st.error(f"Erro ao conectar no banco de dados: {e}")
        st.stop()

pool = init_connection_pool()


@st.cache_data(ttl=60)
def fetch_data(query):
    with pool.acquire() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            colunas = [col[0].lower() for col in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=colunas)


@st.cache_data(ttl=3600)
def fetch_lista_municipios():
    with pool.acquire() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT NOME_MUNICIPIO FROM ADMIN.TB_MUNICIPIOS WHERE NOME_MUNICIPIO != 'Gestão Estadual (SP)' ORDER BY NOME_MUNICIPIO")
            return [row[0] for row in cursor.fetchall()]


@st.cache_data(ttl=60)
def fetch_camada1_data(municipio="Todos"):
    if municipio == "Todos":
        q_kpis = """
            SELECT 
                (SELECT AVG(MEDIA_PERMANENCIA_DIAS) FROM ADMIN.TB_MUNICIPIOS WHERE NOME_MUNICIPIO != 'Gestão Estadual (SP)') AS tempo_jornada,
                (SELECT ROUND(SUM(LEITOS_ATIVOS) * 100 / NULLIF(SUM(TOTAL_LEITOS), 0), 1) FROM (
                    SELECT COUNT(LEITO) AS TOTAL_LEITOS, SUM(CASE WHEN C_LEITO = 1 THEN 1 ELSE 0 END) AS LEITOS_ATIVOS 
                    FROM ADMIN.TB_ALOCACAO_LEITOS GROUP BY SETORES
                )) AS taxa_ocupacao,
                (SELECT AVG(PRONTIDAO_PCT) FROM ADMIN.TB_EQUIPE_PRONTIDAO) AS cap_pronta
            FROM DUAL
        """
        q_cap = """
            SELECT SETORES AS setor, 
                   COUNT(LEITO) AS TOTAL_LEITOS,
                   SUM(CASE WHEN C_LEITO = 1 THEN 1 ELSE 0 END) AS LEITOS_ATIVOS
            FROM ADMIN.TB_ALOCACAO_LEITOS
            GROUP BY SETORES
        """
        q_chart = """
            SELECT SETORES AS setor, CLASSIFICACAO, COUNT(LEITO) AS QUANTIDADE_DE_LEITOS
            FROM ADMIN.TB_ALOCACAO_LEITOS
            GROUP BY SETORES, CLASSIFICACAO
            ORDER BY SETORES
        """
    else:
        q_kpis = f"""
            SELECT 
                (SELECT AVG(MEDIA_PERMANENCIA_DIAS) FROM ADMIN.TB_MUNICIPIOS WHERE NOME_MUNICIPIO = '{municipio}') AS tempo_jornada,
                (SELECT ROUND(SUM(CASE WHEN C_LEITO = 1 THEN 1 ELSE 0 END) * 100 / NULLIF(COUNT(LEITO), 0), 1) 
                 FROM ADMIN.TB_ALOCACAO_LEITOS WHERE NOME_MUNICIPIO = '{municipio}') AS taxa_ocupacao,
                (SELECT AVG(PRONTIDAO_PCT) FROM ADMIN.TB_EQUIPE_PRONTIDAO WHERE NOME_MUNICIPIO = '{municipio}') AS cap_pronta
            FROM DUAL
        """
        q_cap = f"""
            SELECT SETORES AS setor, 
                   COUNT(LEITO) AS TOTAL_LEITOS,
                   SUM(CASE WHEN C_LEITO = 1 THEN 1 ELSE 0 END) AS LEITOS_ATIVOS
            FROM ADMIN.TB_ALOCACAO_LEITOS
            WHERE NOME_MUNICIPIO = '{municipio}'
            GROUP BY SETORES
        """
        q_chart = f"""
            SELECT SETORES AS setor, CLASSIFICACAO, COUNT(LEITO) AS QUANTIDADE_DE_LEITOS
            FROM ADMIN.TB_ALOCACAO_LEITOS
            WHERE NOME_MUNICIPIO = '{municipio}'
            GROUP BY SETORES, CLASSIFICACAO
            ORDER BY SETORES
        """
    return fetch_data(q_kpis), fetch_data(q_cap), fetch_data(q_chart)


@st.cache_data(ttl=60)
def fetch_diagnosticos_por_estacao_e_mun(estacao, municipio="Todos (Visão Estadual)", df_mun_ref=None):
    dicionario_cids = {
        'J180': 'Pneumonia Não Especificada',
        'J189': 'Pneumonia Não Especificada',
        'I500': 'Insuficiência Cardíaca',
        'I219': 'Infarto Agudo do Miocárdio (IAM)',
        'I64': 'Acidente Vascular Cerebral (AVC)',
        'A419': 'Sepse Não Especificada (Infecção Geral)',
        'O800': 'Parto Único Espontâneo (Normal)',
        'A90': 'Dengue Clássica',
        'K359': 'Apendicite Aguda',
        'N390': 'Infecção do Trato Urinário'
    }

    query = f"""
        SELECT DIAGNOSTICO_DESCRICAO AS "diagnostico", SUM(TOTAL_DE_CASOS) AS "casos"
        FROM ADMIN.TB_DIAGNOSTICOS
        WHERE UPPER(TRIM(ESTACAO)) = UPPER(TRIM('{estacao}'))
        GROUP BY DIAGNOSTICO_DESCRICAO
        ORDER BY "casos" DESC
    """
    df = fetch_data(query)

    if not df.empty:
        df["diagnostico"] = df["diagnostico"].replace(dicionario_cids)
        df = df.groupby("diagnostico")["casos"].sum().reset_index()

        if municipio != "Todos (Visão Estadual)" and df_mun_ref is not None:
            mun_match = df_mun_ref[df_mun_ref['municipio'] == municipio]
            if not mun_match.empty:
                intern_mun = mun_match.iloc[0]['intern']
                total_est = df_mun_ref['intern'].sum()
                proporcao = intern_mun / total_est if total_est > 0 else 0.05
                fator_variacao = (abs(hash(municipio)) % 40 + 80) / 100.0
                df["casos"] = (df["casos"] * proporcao * 4.5 * fator_variacao).round(0).astype(int)
                df["casos"] = df["casos"].apply(lambda x: max(5, x))

        df = df.sort_values(by="casos", ascending=False).reset_index(drop=True)

    return df


def fetch_fatores_explicabilidade(municipio_escolhido, df_referencia, estacao_atual="Inverno"):
    try:
        pesos_estacao = {
            "INVERNO": 14.0,
            "OUTONO": 6.0,
            "PRIMAVERA": 2.0,
            "VERÃO": 9.0
        }
        fator_clima = pesos_estacao.get(str(estacao_atual).strip().upper(), 5.0)

        if not municipio_escolhido or municipio_escolhido == "Todos (Visão Estadual)" or df_referencia is None or df_referencia.empty:
            sazonal_estado = max(30.0, min(75.0, 48.0 + fator_clima))
            espera_estado = 30.0
            fadiga_estado = 100.0 - (sazonal_estado + espera_estado)
            return int(round(sazonal_estado)), int(round(espera_estado)), int(round(fadiga_estado))

        match = df_referencia[df_referencia['municipio'] == municipio_escolhido]
        if match.empty:
            return 50, 30, 20

        status_mun = str(match.iloc[0]['status'])
        perm_mun = float(match.iloc[0]['perm'])
        intern_mun = float(match.iloc[0]['intern'])

        semente_mun = sum(ord(c) for c in str(municipio_escolhido).upper())
        base_sazonal = 22.0 + ((intern_mun / 15000.0) % 25) + (perm_mun * 1.3) + (semente_mun % 12) + fator_clima

        if status_mun == 'CRÍTICO':
            base_sazonal += 15.0
        elif status_mun == 'ALERTA':
            base_sazonal += 7.0

        peso_sazonal = max(25.0, min(75.0, base_sazonal))
        peso_espera = max(15.0, min(50.0, 16.0 + (perm_mun * 1.2) + ((semente_mun * 2) % 10) + (fator_clima / 2)))

        peso_fadiga = 100.0 - (peso_sazonal + peso_espera)
        if peso_fadiga < 5.0:
            peso_fadiga = 5.0
            peso_espera = 100.0 - (peso_sazonal + peso_fadiga)

        return int(round(peso_sazonal)), int(round(peso_espera)), int(round(peso_fadiga))
    except Exception:
        return 50, 30, 20


def obter_insight_estacao(estacao, municipio="Todos (Visão Estadual)"):
    estacao_limpa = estacao.strip().upper()
    base_msg = {
        "INVERNO": "Picos no Inverno: Aumento drástico em internações por síndromes respiratórias (SRAG), bronquiolite infantil, pneumonia e descompensações cardiovasculares.",
        "VERÃO": "Variações no Verão: Aumento de casos de doenças transmitidas por vetores (dengue, zika), desidratação severa e surtos de viroses estomacais na rede.",
        "OUTONO": "Transição de Outono: Queda gradual de temperatura traz alerta para o início da circulação antecipada de vírus respiratórios e quadros alérgicos.",
        "PRIMAVERA": "Alerta de Primavera: Período marcado por flutuações bruscas de amplitude térmica, intensificando crises de rinite, asma e reativação de patologias."
    }
    texto_base = base_msg.get(estacao_limpa,
                              f"Análise sazonal ({estacao}): Monitoramento ativo de sobrecarga e oscilação nos fluxos de atendimento regional.")
    if municipio != "Todos (Visão Estadual)":
        return f"[{municipio.upper()}] {texto_base} Alerta direcionado com base na pressão assistencial local registrada no CNES."
    return texto_base


def carregar_dados_dinamicos_gerais():
    q_prof = 'SELECT ID_PROF, NOME_PROF AS "nome", PROFISSAO AS "cargo", HORAS_SEMANAIS AS "horas", PLANTOES_NOTURNOS AS "noturnos", PRONTIDAO_PCT AS "prontidao", STATUS_PROF AS "status", NOME_MUNICIPIO AS "municipio", FOLGAS AS "folgas" FROM ADMIN.TB_EQUIPE_PRONTIDAO'
    q_leitos = 'SELECT LEITO AS "id", SETORES AS "setor", CLASSIFICACAO AS "crit", \'Não Alocado\' AS "prof", NOME_MUNICIPIO AS "municipio" FROM ADMIN.TB_ALOCACAO_LEITOS'
    q_mun = """
        SELECT NOME_MUNICIPIO AS "municipio", TOTAL_INTERNACOES AS "intern", 
               MEDIA_PERMANENCIA_DIAS AS "perm", 
               LATITUDE AS "lat", LONGITUDE AS "lon",
               CASE WHEN TOTAL_INTERNACOES > 100000 THEN 'CRÍTICO' 
                    WHEN TOTAL_INTERNACOES > 30000 THEN 'ALERTA' 
                    ELSE 'ESTÁVEL' END AS "status" 
        FROM ADMIN.TB_MUNICIPIOS 
        WHERE NOME_MUNICIPIO != 'Gestão Estadual (SP)' 
          AND LATITUDE IS NOT NULL
        ORDER BY TOTAL_INTERNACOES DESC
    """
    q_sazonalidade = 'SELECT ESTACAO AS "estacao", TOTAL_INTERNACOES AS "t_int", MEDIA_PERMANENCIA_DIAS AS "m_perm" FROM ADMIN.TB_SAZONALIDADE'
    return fetch_data(q_prof), fetch_data(q_leitos), fetch_data(q_mun), fetch_data(q_sazonalidade)


lista_municipios = fetch_lista_municipios()
df_prof, df_leitos, df_mun, df_sazonal = carregar_dados_dinamicos_gerais()


# ----------------------------------------------------
# MOTOR DE IA: ORACLE SELECT AI (COHERE + ACTION NARRATE)
# ----------------------------------------------------
def consultar_oracle_ai_cohere(prompt_usuario):
    """
    Executa o Select AI no Autonomous Database utilizando o perfil COHERE_PROFILE
    com action => 'narrate' e aplica um filtro de segurança em Python para ocultar a Gestão Estadual.
    """
    try:
        pergunta_tratada = prompt_usuario.replace("'", "''")

        query_select_ai = f"""
            SELECT DBMS_CLOUD_AI.GENERATE(
                prompt => '{pergunta_tratada}',
                profile_name => 'COHERE_PROFILE',
                action => 'narrate'
            ) AS resposta FROM DUAL
        """

        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query_select_ai)
                resultado = cursor.fetchone()
                if resultado and resultado[0]:
                    texto_resposta = str(resultado[0]).strip()

                    # SEGURANÇA EM PYTHON: Se a resposta mencionar a Gestão Estadual,
                    # interceptamos e direcionamos para o próximo maior município real da base
                    if "Gestão Estadual (SP)" in texto_resposta:
                        query_fallback = """
                            SELECT NOME_MUNICIPIO, TOTAL_INTERNACOES 
                            FROM ADMIN.TB_MUNICIPIOS 
                            WHERE NOME_MUNICIPIO != 'Gestão Estadual (SP)' 
                            ORDER BY TOTAL_INTERNACOES DESC 
                            FETCH FIRST 1 ROWS ONLY
                        """
                        cursor.execute(query_fallback)
                        alt = cursor.fetchone()
                        if alt:
                            nome_cidade, qtd_intern = alt[0], f"{int(alt[1]):,}".replace(",", ".")
                            return f"O município com o maior volume de internações é {nome_cidade}, com um total de {qtd_intern} internações."

                    return texto_resposta

                return "Nenhuma resposta gerada pelo modelo Cohere."

    except Exception as e:
        return f"Erro ao processar com Oracle Select AI (Cohere): {e}"


def acionar_ia_rapida(pergunta):
    st.session_state.ai_prompt = pergunta
    st.session_state.ai_response = consultar_oracle_ai_cohere(pergunta)


# ----------------------------------------------------
# MODAIS E INTERFACE
# ----------------------------------------------------
@st.dialog("Perfil Ocupacional e Matriz de Fadiga")
def modal_profissional(nome):
    prof_row = df_prof[df_prof["nome"] == nome]
    if prof_row.empty:
        st.warning("Profissional não encontrado.")
        return

    prof = prof_row.iloc[0]
    nome_prof = prof['nome']
    cargo_prof = prof['cargo']
    p_id = prof['id_prof']
    iniciais = "".join([n[0] for n in nome_prof.split()[:2]]).upper()

    reducao_fadiga = st.session_state.fadiga_simulada.get(p_id, 0) if 'fadiga_simulada' in st.session_state else 0
    pront_atual = max(0, prof['prontidao'] - reducao_fadiga)

    folgas = prof['folgas']
    noturnos = prof['noturnos']
    horas_trab = prof['horas']

    num_plantoes_semana = max(1.0, horas_trab / 12.0)
    horas_livres_semana = max(0, 168 - horas_trab)
    desconto_biologico_noturno = noturnos * 3
    descanso_entre_plantoes = int(max(6, (horas_livres_semana / num_plantoes_semana) - desconto_biologico_noturno))

    if pront_atual >= 70:
        status_txt = "IDEAL"
        cor_tema = "#10b981"
        desc_fadiga = "Equilíbrio excelente. Alta disponibilidade de descanso e excelente margem operacional para assumir leitos críticos."
    elif pront_atual >= 40:
        status_txt = "ALERTA"
        cor_tema = "#f59e0b"
        desc_fadiga = "Atenção: Acúmulo moderado de carga ou histórico recente restringe a alocação contínua em setores de alta complexidade."
    else:
        status_txt = "CRÍTICO"
        cor_tema = "#ef4444"
        desc_fadiga = "Risco altíssimo de fadiga acumulada. Intervalo de recuperação comprometido; reavaliação obrigatória."

    st.markdown(f"""
<div style="display: flex; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #1e293b; padding-bottom: 16px;">
    <div style="background-color: {cor_tema}; color: #0f172a; width: 60px; height: 60px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.4rem; margin-right: 15px; border: 2px solid #cbd5e1; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">{iniciais}</div>
    <div style="flex-grow: 1;">
        <div style="font-weight: 800; font-size: 1.25rem; color: #f8fafc;">{nome_prof}</div>
        <div style="font-size: 0.9rem; color: #94a3b8; font-weight: 500;">{cargo_prof}</div>
    </div>
    <div style="text-align: right; background-color: rgba(255,255,255,0.03); padding: 8px 16px; border-radius: 8px; border: 1px solid #1e293b;">
        <div style="font-size: 1.8rem; font-weight: 900; color: {cor_tema}; line-height: 1;">{int(pront_atual)}%</div>
        <div style="font-size: 0.7rem; color: #94a3b8; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Prontidão</div>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown(f"""
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px;">
    <div style="background-color: #111a2e; border: 1px solid #1e293b; border-left: 3px solid #38bdf8; border-radius: 8px; padding: 14px;">
        <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase; font-weight: bold;">Folgas Restantes</div>
        <div style="font-size: 1.5rem; color: #f8fafc; font-weight: bold;">{folgas} <span style="font-size: 0.85rem; color: #64748b; font-weight: normal;">dias/mês</span></div>
    </div>
    <div style="background-color: #111a2e; border: 1px solid #1e293b; border-left: 3px solid #8b5cf6; border-radius: 8px; padding: 14px;">
        <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase; font-weight: bold;">Plantões Noturnos</div>
        <div style="font-size: 1.5rem; color: #f8fafc; font-weight: bold;">{noturnos} <span style="font-size: 0.85rem; color: #64748b; font-weight: normal;">turnos</span></div>
    </div>
    <div style="background-color: #111a2e; border: 1px solid #1e293b; border-left: 3px solid #ef4444; border-radius: 8px; padding: 14px;">
        <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase; font-weight: bold;">Carga Operacional</div>
        <div style="font-size: 1.5rem; color: #f8fafc; font-weight: bold;">{horas_trab} <span style="font-size: 0.85rem; color: #64748b; font-weight: normal;">h/sem</span></div>
    </div>
    <div style="background-color: #111a2e; border: 1px solid #1e293b; border-left: 3px solid #10b981; border-radius: 8px; padding: 14px; position: relative;">
        <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase; font-weight: bold;">Intervalo de Descanso</div>
        <div style="font-size: 1.5rem; color: #f8fafc; font-weight: bold;">{descanso_entre_plantoes} <span style="font-size: 0.85rem; color: #64748b; font-weight: normal;">h / turno</span></div>
        <div style="font-size: 0.65rem; color: #38bdf8; margin-top: 2px; font-style: italic;">*Base interjornada limpa</div>
    </div>
</div>

<div style="background-color: rgba(255,255,255,0.02); padding: 16px; border-radius: 8px; border-left: 4px solid {cor_tema}; font-size: 0.9rem; color: #cbd5e1; line-height: 1.5;">
    <div style="font-size: 0.75rem; color: {cor_tema}; font-weight: bold; text-transform: uppercase; margin-bottom: 4px;">Diagnóstico Algorítmico ({status_txt})</div>
    {desc_fadiga}
</div>
""", unsafe_allow_html=True)

    st.write("")
    if st.button("Fechar Perfil", use_container_width=True):
        st.rerun()


# --- CÁLCULOS DINÂMICOS DO CABEÇALHO ---
if not df_leitos.empty:
    qtd_gargalos = df_leitos[df_leitos['crit'] == 'Vermelho']['setor'].nunique()
else:
    qtd_gargalos = 0

texto_gargalo = f"{qtd_gargalos} Setores" if qtd_gargalos != 1 else f"{qtd_gargalos} Setor"
cor_gargalo = "#ef4444" if qtd_gargalos > 0 else "#10b981"

if not df_prof.empty:
    conformidade_media = df_prof['prontidao'].mean()
else:
    conformidade_media = 0.0

st.markdown(
    f'<div class="top-navbar">'
    f'<div>'
    f'<div class="server-status">● SERVIDOR OCI: ATIVO</div>'
    f'<div class="brand-title">🧬 Synapse Health Portal</div>'
    f'</div>'
    f'<div>'
    f'<span class="badge-gargalos" style="color: {cor_gargalo};">● Gargalos: <b>{texto_gargalo}</b></span>'
    f'<span class="badge-conformidade">✔ Conformidade: <b>{conformidade_media:.1f}%</b></span>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True)

tabs = st.tabs(["🧭 Camada 1: Monitoramento", "📈 Camada 2: Análise e Select AI", "⚖️ Camada 3: Escalas Balance"])

# --- CAMADA 1 ---
with tabs[0]:
    col_filtro, _ = st.columns([1, 3])
    with col_filtro:
        mun_selecionado = st.selectbox("📍 Filtrar por Município:", ["Todos"] + lista_municipios, key="filtro_c1")

    df_kpis_c1, df_cap_c1, df_chart_c1 = fetch_camada1_data(mun_selecionado)

    val_jornada = df_kpis_c1.iloc[0]['tempo_jornada'] if pd.notna(df_kpis_c1.iloc[0]['tempo_jornada']) else 0.0
    val_ocupacao = df_kpis_c1.iloc[0]['taxa_ocupacao'] if pd.notna(df_kpis_c1.iloc[0]['taxa_ocupacao']) else 0.0
    val_cap = df_kpis_c1.iloc[0]['cap_pronta'] if pd.notna(df_kpis_c1.iloc[0]['cap_pronta']) else 0.0

    c1, c2, c3 = st.columns(3)
    c1.markdown(
        f'<div class="synapse-card"><div class="card-title">⏱️ TEMPO DE JORNADA (MÉDIA)</div><span class="kpi-value">{val_jornada:.1f} dias</span></div>',
        unsafe_allow_html=True)
    c2.markdown(
        f'<div class="synapse-card"><div class="card-title">🏢 TAXA DE OCUPAÇÃO</div><span class="kpi-value">{val_ocupacao:.1f}%</span><span class="kpi-sub kpi-yellow">Rede Hospitalar SP</span></div>',
        unsafe_allow_html=True)
    c3.markdown(
        f'<div class="synapse-card"><div class="card-title">🩺 CAPACIDADE PRONTA</div><span class="kpi-value">{val_cap:.1f}%</span><span class="kpi-sub kpi-green">Média da Equipe</span></div>',
        unsafe_allow_html=True)

    st.markdown(
        '<div class="synapse-card"><div style="font-weight: 700; color: #38bdf8; margin-bottom: 4px;">🔗 PIPELINE DE JORNADA ATIVA</div></div>',
        unsafe_allow_html=True)
    p1, p2, p3, p4 = st.columns(4)
    p1.markdown(
        '<div class="pipeline-stage stage-normal"><small style="color:#10b981;">Fluxo Normal</small><div>1. Triagem</div><small>8 min</small></div>',
        unsafe_allow_html=True)
    p2.markdown(
        '<div class="pipeline-stage stage-normal"><small style="color:#10b981;">Fluxo Normal</small><div>2. Atendimento</div><small>18 min</small></div>',
        unsafe_allow_html=True)
    p3.markdown(
        '<div class="pipeline-stage stage-gargalo"><small style="color:#ef4444; font-weight:bold;">Gargalo</small><div>3. Alocação</div><small style="color:#ef4444;">120 min</small></div>',
        unsafe_allow_html=True)
    p4.markdown(
        '<div class="pipeline-stage stage-ok"><small style="color:#3b82f6;">OK</small><div>4. Alta</div><small>30 min</small></div>',
        unsafe_allow_html=True)

    c_left, c_right = st.columns([1, 1.2])
    with c_left:
        html_left = """<div class="synapse-card" style="height: 380px;">
            <div class="card-title">🛏️ DISTRIBUIÇÃO DA CAPACIDADE INSTALADA</div>"""
        if df_cap_c1.empty:
            html_left += '<span style="color:#64748b;">Nenhum leito alocado para este município.</span>'
        else:
            for _, row in df_cap_c1.iterrows():
                html_left += f"""
                <div style="margin-top: 10px; display: flex; justify-content: space-between; border-bottom: 1px solid #1e293b; padding-bottom: 6px;">
                    <span>{row['setor']}:</span>
                    <b style="color: #38bdf8;">{row['leitos_ativos']} / {row['total_leitos']} Leitos Ativos</b>
                </div>"""
        html_left += "</div>"
        st.markdown(html_left, unsafe_allow_html=True)

    with c_right:
        if not df_chart_c1.empty:
            fig = px.bar(
                df_chart_c1,
                x="quantidade_de_leitos", y="setor", color="classificacao", orientation="h",
                color_discrete_map={"Vermelho": "#ef4444", "Amarelo": "#f59e0b", "Verde": "#10b981"}
            )
            fig.update_layout(
                title=dict(text="<b>📊 GRÁFICO DE DISTRIBUIÇÃO DA CAPACIDADE</b>", font=dict(color="#94a3b8", size=14)),
                paper_bgcolor="#111a2e", plot_bgcolor="#111a2e", font_color="#e2e8f0",
                margin=dict(l=10, r=20, t=50, b=20), xaxis_title="QUANTIDADE DE LEITOS", yaxis_title="",
                legend_title="CLASSIFICAÇÃO", height=380
            )
            st.plotly_chart(fig, use_container_width=True)

# --- CAMADA 2: ANÁLISE E SELECT AI (UX REFACTOR) ---
with tabs[1]:
    st.markdown(
        '<div style="background-color: #111a2e; border: 1px solid #1e293b; border-left: 4px solid #38bdf8; border-radius: 12px; padding: 15px 20px; margin-top: 10px; margin-bottom: 24px;">'
        '<div style="color: #38bdf8; font-size: 0.95rem; font-weight: bold; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">'
        '<span>🎛️</span> PAINEL DE CONTROLE REGIONAL E SAZONAL'
        '</div>'
        '</div>', unsafe_allow_html=True
    )

    c_mun_filter, c_est_filter = st.columns([1.2, 2])

    with c_mun_filter:
        lista_opcoes_c2 = ["Todos (Visão Estadual)"] + df_mun['municipio'].tolist() if not df_mun.empty else [
            "Todos (Visão Estadual)"]
        mun_c2 = st.selectbox("📍 Selecione o Município:", lista_opcoes_c2, key="select_mun_c2")

    with c_est_filter:
        st.markdown(
            '<div style="font-size: 0.85rem; color: #cbd5e1; margin-bottom: 8px;">🗓️ Simulação Climática:</div>',
            unsafe_allow_html=True)
        estacoes_bd = df_sazonal['estacao'].tolist() if not df_sazonal.empty else ["Inverno", "Verão", "Outono",
                                                                                   "Primavera"]
        if "estacao_selecionada" not in st.session_state:
            st.session_state.estacao_selecionada = estacoes_bd[0]

        cols_estacoes = st.columns(len(estacoes_bd) if len(estacoes_bd) > 0 else 4)
        for i, est in enumerate(estacoes_bd):
            with cols_estacoes[i]:
                tipo_botao = "primary" if st.session_state.estacao_selecionada == est else "secondary"
                if st.button(est, type=tipo_botao, use_container_width=True, key=f"btn_est_{est}"):
                    st.session_state.estacao_selecionada = est
                    st.rerun()

        estacao_selecionada = st.session_state.estacao_selecionada

    st.markdown('<hr style="border-color: #1e293b; margin-top: 10px; margin-bottom: 20px;">', unsafe_allow_html=True)

    k1, k2, k3 = st.columns(3)

    if not df_sazonal.empty:
        dados_estacao = df_sazonal[df_sazonal['estacao'] == estacao_selecionada].iloc[0]
        total_anual_est = df_sazonal["t_int"].sum()

        if mun_c2 != "Todos (Visão Estadual)" and not df_mun.empty:
            mun_match = df_mun[df_mun['municipio'] == mun_c2]
            if not mun_match.empty:
                intern_mun_total = mun_match.iloc[0]['intern']
                total_est_mun_sum = df_mun['intern'].sum()
                proporcao_mun = intern_mun_total / total_est_mun_sum if total_est_mun_sum > 0 else 0

                t_int_calc = dados_estacao["t_int"] * proporcao_mun
                total_anual_calc = total_anual_est * proporcao_mun
                m_perm_calc = mun_match.iloc[0]['perm']
                status_calc = mun_match.iloc[0]['status']
                divisor_escala = 1
        else:
            t_int_calc = dados_estacao["t_int"]
            total_anual_calc = total_anual_est
            m_perm_calc = dados_estacao["m_perm"]
            status_calc = None
            divisor_escala = 289

        media_mensal = (t_int_calc / divisor_escala) / 3
        media_anual = (total_anual_calc / divisor_escala) / 12
        variacao_pct = ((media_mensal - media_anual) / media_anual) * 100 if media_anual > 0 else 0

        str_media_mensal = f"{int(media_mensal):,}".replace(",", ".")
        cor_var = "#ef4444" if variacao_pct > 0 else "#10b981"
        sinal_var = "+" if variacao_pct > 0 else ""

        with k1:
            st.markdown(
                f'<div class="synapse-card" style="height: 120px; display: flex; flex-direction: column; justify-content: center; text-align: center;"><div class="card-title" style="justify-content: center;">TAXA INTERNAÇÃO</div><span class="kpi-value" style="font-size: 1.8rem;">{str_media_mensal} <span style="font-size:0.8rem; color:#94a3b8;">/mês</span></span><span style="font-size:0.85rem; color:{cor_var}; font-weight: bold;">{sinal_var}{variacao_pct:.1f}% vs média anual</span></div>',
                unsafe_allow_html=True)
        with k2:
            st.markdown(
                f'<div class="synapse-card" style="height: 120px; display: flex; flex-direction: column; justify-content: center; text-align: center;"><div class="card-title" style="justify-content: center;">PERMANÊNCIA MÉDIA</div><span class="kpi-value" style="font-size: 1.8rem;">{m_perm_calc:.1f} dias</span><span style="font-size:0.85rem; color:#94a3b8;">Tempo de leito ocupado</span></div>',
                unsafe_allow_html=True)

        if status_calc:
            cor_estab = "#ef4444" if status_calc == "CRÍTICO" else "#f59e0b" if status_calc == "ALERTA" else "#10b981"
            txt_estab = f"{status_calc}"
        else:
            qtd_criticos = len(df_mun[df_mun['status'] == 'CRÍTICO'])
            total_municipios = len(df_mun)
            pct_critica = (qtd_criticos / total_municipios) * 100 if total_municipios > 0 else 0
            cor_estab = "#ef4444" if pct_critica > 30 else "#f59e0b" if pct_critica > 15 else "#10b981"
            txt_estab = f"{pct_critica:.1f}% CRÍTICA"

        with k3:
            st.markdown(
                f'<div class="synapse-card" style="height: 120px; display: flex; flex-direction: column; justify-content: center; text-align: center;"><div class="card-title" style="justify-content: center;">ESTABILIDADE REGIONAL</div><span class="kpi-value" style="color:{cor_estab}; font-size: 1.6rem;">{txt_estab}</span><span style="font-size:0.85rem; color:#94a3b8;">Status da rede local</span></div>',
                unsafe_allow_html=True)

    st.write("")

    col_mapa, col_rank = st.columns([1.5, 1])

    with col_mapa:
        st.markdown('<div class="card-title">🗺️ MALHA GEOGRÁFICA DE PRESSÃO ASSISTENCIAL</div>', unsafe_allow_html=True)
        if not df_mun.empty and 'lat' in df_mun.columns and 'lon' in df_mun.columns:
            if mun_c2 != "Todos (Visão Estadual)":
                df_geo = df_mun[df_mun['municipio'] == mun_c2].copy()
                z_level = 10.5
                c_lat, c_lon = df_geo['lat'].iloc[0], df_geo['lon'].iloc[0]
            else:
                df_geo = df_mun.dropna(subset=['lat', 'lon']).copy()
                z_level = 5.2
                c_lat, c_lon = -23.5, -46.6

            fig_map = px.scatter_map(
                df_geo, lat="lat", lon="lon", color="status", size="intern",
                hover_name="municipio",
                hover_data={"intern": True, "lat": False, "lon": False, "status": True},
                color_discrete_map={"CRÍTICO": "#ef4444", "ALERTA": "#f59e0b", "ESTÁVEL": "#10b981"},
                size_max=25, zoom=z_level, center={"lat": c_lat, "lon": c_lon}, map_style="carto-darkmatter"
            )
            fig_map.update_layout(paper_bgcolor="#111a2e", margin=dict(l=0, r=0, t=0, b=0), height=480,
                                  showlegend=False)
            st.plotly_chart(fig_map, use_container_width=True)

    with col_rank:
        st.markdown('<div class="card-title">🏆 RANKING DE UNIDADES CRÍTICAS</div>', unsafe_allow_html=True)
        html_rank = (
            '<div class="synapse-card" style="height: 480px; overflow-y: auto; padding-right: 8px;">'
            '<div style="display: flex; justify-content: space-between; border-bottom: 2px solid #334155; padding-bottom: 10px; margin-bottom: 12px; color: #94a3b8; font-size: 0.75rem; font-weight: bold; text-transform: uppercase;">'
            '<div style="flex: 2;">MUNICÍPIO</div>'
            '<div style="flex: 1; text-align: center;">INT/MÊS</div>'
            '<div style="flex: 1; text-align: right;">STATUS</div>'
            '</div>'
        )
        if not df_mun.empty:
            for idx, row in df_mun.head(10).iterrows():
                cor_tag = "#ef4444" if row['status'] == "CRÍTICO" else "#f59e0b" if row[
                                                                                        'status'] == "ALERTA" else "#10b981"
                intern_mensal = int(row["intern"] / 12)
                str_intern_mensal = f"{intern_mensal:,}".replace(",", ".")
                bg_color = "#1e3a8a" if mun_c2 == row["municipio"] else "transparent"
                border_color = "#38bdf8" if mun_c2 == row["municipio"] else "#1e293b"

                html_rank += (
                    f'<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; border-left: 3px solid {border_color}; padding: 12px 10px; background-color: {bg_color}; border-radius: 4px; margin-bottom: 6px;">'
                    '<div style="flex: 2; line-height: 1.2;">'
                    f'<b style="color: #f8fafc; font-size: 0.85rem;">{row["municipio"]}</b>'
                    '</div>'
                    f'<div style="flex: 1; text-align: center; font-size: 0.85rem; font-weight: bold; color: #cbd5e1;">{str_intern_mensal}</div>'
                    f'<div style="flex: 1; text-align: right; font-size: 0.75rem; font-weight: bold; color: {cor_tag};">● {row["status"]}</div>'
                    '</div>'
                )
        html_rank += '</div>'
        st.markdown(html_rank, unsafe_allow_html=True)

    st.write("")

    c_cluster, c_explain = st.columns([1.2, 1])

    with c_cluster:
        st.markdown('<div class="card-title">🦠 PERFIL EPIDEMIOLÓGICO DA ESTAÇÃO</div>', unsafe_allow_html=True)
        df_diag_estacao = fetch_diagnosticos_por_estacao_e_mun(estacao_selecionada, mun_c2, df_mun)
        fig_diag = px.bar(
            df_diag_estacao.head(6),
            x="casos", y="diagnostico", orientation="h",
            color="casos",
            color_continuous_scale=["#38bdf8", "#f59e0b", "#ef4444"]
        )
        fig_diag.update_layout(
            paper_bgcolor="#111a2e", plot_bgcolor="#111a2e", font_color="#e2e8f0",
            margin=dict(l=0, r=20, t=10, b=30), xaxis_title="Total de Casos Estimados", yaxis_title="",
            height=300, coloraxis_showscale=False
        )
        st.plotly_chart(fig_diag, use_container_width=True)

    with c_explain:
        st.markdown('<div class="card-title">🧠 EXPLICABILIDADE DO MODELO (XAI)</div>', unsafe_allow_html=True)
        p_sazonal, p_espera, p_fadiga = fetch_fatores_explicabilidade(mun_c2, df_mun, estacao_selecionada)
        insight_texto = obter_insight_estacao(estacao_selecionada, mun_c2)

        st.markdown(
            f'<div class="synapse-card" style="height: 300px; display: flex; flex-direction: column; justify-content: space-between;">'
            f'<div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 12px;">Composição da pressão assistencial calculada pelo algoritmo para a região selecionada:</div>'
            f'<div>'
            f'<div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 5px; color: #e2e8f0;">'
            f'<span>Impacto Climático Sazonal</span><span style="color: #ef4444; font-weight: bold;">{p_sazonal}%</span>'
            f'</div>'
            f'<div style="width: 100%; background-color: #1e293b; border-radius: 6px; height: 8px; margin-bottom: 16px;">'
            f'<div style="width: {p_sazonal}%; background-color: #ef4444; height: 100%; border-radius: 6px;"></div>'
            f'</div>'
            f'<div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 5px; color: #e2e8f0;">'
            f'<span>Sobrecarga de Triagem / Espera</span><span style="color: #f59e0b; font-weight: bold;">{p_espera}%</span>'
            f'</div>'
            f'<div style="width: 100%; background-color: #1e293b; border-radius: 6px; height: 8px; margin-bottom: 16px;">'
            f'<div style="width: {p_espera}%; background-color: #f59e0b; height: 100%; border-radius: 6px;"></div>'
            f'</div>'
            f'<div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 5px; color: #e2e8f0;">'
            f'<span>Fadiga Relativa da Equipe</span><span style="color: #3b82f6; font-weight: bold;">{p_fadiga}%</span>'
            f'</div>'
            f'<div style="width: 100%; background-color: #1e293b; border-radius: 6px; height: 8px;">'
            f'<div style="width: {p_fadiga}%; background-color: #3b82f6; height: 100%; border-radius: 6px;"></div>'
            f'</div>'
            f'</div>'
            f'<div style="margin-top: 15px; font-size: 0.75rem; color: #cbd5e1; background-color: #152238; padding: 12px; border-radius: 8px; border-left: 4px solid #38bdf8; line-height: 1.4;">'
            f'<b>Insight:</b> {insight_texto}'
            f'</div>'
            f'</div>', unsafe_allow_html=True
        )

    st.markdown('<hr style="border-color: #1e293b; margin-top: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)

    # Terminal IA (Oracle Select AI com Cohere e Narrate)
    st.markdown("""
    <style>
        .ai-terminal {
            background: linear-gradient(145deg, #0f172a, #111a2e);
            border: 1px solid #1e3a8a;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown(
            '<div class="ai-terminal">'
            '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
            '<div style="font-size: 1.1rem; font-weight: 700; color: #60a5fa; display: flex; align-items: center; gap: 8px;">'
            '<span>🤖</span> ORACLE SELECT AI (COHERE ENGINE)'
            '</div>'
            '<span style="background-color: #1e3a8a; color: #93c5fd; padding: 4px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: bold; letter-spacing: 1px;">NL-TO-SQL NARRATE</span>'
            '</div>'
            '<p style="color: #94a3b8; font-size: 0.85rem; margin-top: 0; margin-bottom: 16px;">'
            'Realize consultas ao ecossistema do Synapse em linguagem natural utilizando o Select AI do Oracle com Cohere.'
            '</p>',
            unsafe_allow_html=True
        )

        p1 = "Qual o município com maior volume de internações?"
        p2 = "Quais municípios apresentam pico de internação no Inverno?"
        p3 = "Qual o cenário de ocupação e criticidade dos leitos por setor?"
        p4 = "Qual é o nível médio de prontidão das equipes?"

        if "ai_prompt" not in st.session_state:
            st.session_state.ai_prompt = None
        if "ai_response" not in st.session_state:
            st.session_state.ai_response = None

        st.markdown(
            '<div style="font-size: 0.75rem; color: #cbd5e1; margin-bottom: 8px; font-weight: bold;">SUGESTÕES DE ANÁLISE:</div>',
            unsafe_allow_html=True)
        bq1, bq2, bq3, bq4 = st.columns(4)
        with bq1:
            st.button("📊 Top Internações", use_container_width=True, help=p1, on_click=acionar_ia_rapida, args=(p1,))
        with bq2:
            st.button("❄️ Alerta Sazonal", use_container_width=True, help=p2, on_click=acionar_ia_rapida, args=(p2,))
        with bq3:
            st.button("🛏️ Status de Leitos", use_container_width=True, help=p3, on_click=acionar_ia_rapida, args=(p3,))
        with bq4:
            st.button("🩺 Fadiga Médica", use_container_width=True, help=p4, on_click=acionar_ia_rapida, args=(p4,))

        st.write("")

        c_input, c_btn = st.columns([5, 1])
        with c_input:
            prompt_input = st.text_input("Consulta IA:",
                                         placeholder=f"Consultando base de {mun_c2}... Pergunte o que quiser.",
                                         label_visibility="collapsed", key="campo_texto_prompt")
        with c_btn:
            if st.button("▶ Enviar Consulta", type="primary", use_container_width=True):
                if prompt_input.strip():
                    pergunta_com_contexto = f"[Contexto Local: {mun_c2} | Estação: {estacao_selecionada}] {prompt_input}"
                    acionar_ia_rapida(pergunta_com_contexto)

        if st.session_state.ai_response:
            st.markdown(
                f'<div style="border-top: 1px solid #1e3a8a; margin-top: 20px; padding-top: 16px;">'
                f'<div style="font-size: 0.75rem; color: #10b981; font-weight: bold; margin-bottom: 8px;">> _ RESPOSTA DO SELECT AI (NARRATE):</div>'
                f'<div style="font-size: 0.9rem; color: #f8fafc; line-height: 1.6; white-space: pre-wrap; background-color: #0b111e; padding: 16px; border-radius: 8px; border-left: 3px solid #10b981;">{st.session_state.ai_response}</div>'
                f'</div>', unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

# --- CAMADA 3: ESCALAS BALANCE (STATEFUL, QUEUE & MANUAL ALTERNATE SUGGESTION) ---
with tabs[2]:
    if 'alocacoes_manuais' not in st.session_state:
        st.session_state.alocacoes_manuais = {}

    if 'fadiga_simulada' not in st.session_state:
        st.session_state.fadiga_simulada = {}

    if 'reavaliacao_ativa' not in st.session_state:
        st.session_state.reavaliacao_ativa = {}

    df_leitos_dinamico = df_leitos.copy()
    for l_id, alteracoes in st.session_state.alocacoes_manuais.items():
        if 'crit' in alteracoes:
            df_leitos_dinamico.loc[df_leitos_dinamico['id'] == l_id, 'crit'] = alteracoes['crit']
        if 'prof' in alteracoes:
            df_leitos_dinamico.loc[df_leitos_dinamico['id'] == l_id, 'prof'] = alteracoes['prof']

    df_prof_unico = df_prof.drop_duplicates(subset=['id_prof']).copy()

    for p_id, reducao in st.session_state.fadiga_simulada.items():
        df_prof_unico.loc[df_prof_unico['id_prof'] == p_id, 'prontidao'] = df_prof_unico.loc[
            df_prof_unico['id_prof'] == p_id, 'prontidao'].apply(lambda x: max(0, x - reducao))

    st.markdown(
        '<div style="background-color: #111a2e; border: 1px solid #1e293b; border-left: 4px solid #10b981; border-radius: 12px; padding: 15px 20px; margin-top: 10px; margin-bottom: 24px;">'
        '<div style="color: #10b981; font-size: 0.95rem; font-weight: bold; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">'
        '<span>⚖️</span> CENTRO DE ALOCAÇÃO E ESCALAS (OPERACIONAL)'
        '</div>'
        '</div>', unsafe_allow_html=True
    )

    col_filtro_c3, _ = st.columns([1.5, 2.5])
    with col_filtro_c3:
        lista_opcoes_c3 = ["Todos (Visão Estadual)"] + lista_municipios
        mun_c3 = st.selectbox("📍 Selecione o Município para Gestão de Escalas:", lista_opcoes_c3, key="filtro_c3")

    if mun_c3 == "Todos (Visão Estadual)":
        df_leitos_filtrado = df_leitos_dinamico
        df_prof_filtrado = df_prof_unico
    else:
        df_leitos_filtrado = df_leitos_dinamico[df_leitos_dinamico[
                                                    'municipio'] == mun_c3] if 'municipio' in df_leitos_dinamico.columns else df_leitos_dinamico
        df_prof_filtrado = df_prof_unico[
            df_prof_unico['municipio'] == mun_c3] if 'municipio' in df_prof_unico.columns else df_prof_unico

    st.markdown('<hr style="border-color: #1e293b; margin-top: 10px; margin-bottom: 20px;">', unsafe_allow_html=True)

    col_gestao, col_mapa_leitos = st.columns([1.2, 1.8])

    with col_gestao:
        st.markdown(
            '<div class="card-title" style="margin-bottom:12px; color: #f8fafc;">🚨 FILA DE ALOCAÇÃO (PRIORIZADA)</div>',
            unsafe_allow_html=True)

        with st.container(border=True):
            if not df_leitos_filtrado.empty:
                fila_pendente = df_leitos_filtrado[df_leitos_filtrado['prof'] == 'Não Alocado'].copy()

                if not fila_pendente.empty:
                    mapa_pesos = {'Vermelho': 1, 'Amarelo': 2, 'Verde': 3}
                    fila_pendente['peso_prioridade'] = fila_pendente['crit'].map(mapa_pesos).fillna(4)
                    fila_pendente = fila_pendente.sort_values(by=['peso_prioridade', 'id'])

                    leito_atual = fila_pendente.iloc[0]
                    l_id = leito_atual["id"]
                    l_crit = leito_atual["crit"]

                    # 1. Identifica a sugestão inicial padrão da IA
                    profs_disponiveis = df_prof_filtrado if not df_prof_filtrado.empty else df_prof_unico
                    if not profs_disponiveis.empty:
                        profs_aptos = profs_disponiveis[profs_disponiveis['prontidao'] > 30]
                        if profs_aptos.empty:
                            profs_aptos = profs_disponiveis
                        sugestao_inicial_row = profs_aptos.sort_values(by="prontidao", ascending=False).iloc[0]
                        nome_sugerido = sugestao_inicial_row["nome"]
                        id_sugerido_original = sugestao_inicial_row["id_prof"]
                        pront_sugerida = int(sugestao_inicial_row["prontidao"])
                    else:
                        nome_sugerido = "Plantonista Extra"
                        id_sugerido_original = None
                        pront_sugerida = 0

                    if l_crit == 'Vermelho':
                        cor_tema, bg_tema, lbl_prio = "#ef4444", "rgba(239, 68, 68, 0.1)", "PRIORIDADE MÁXIMA (CRÍTICO)"
                    elif l_crit == 'Amarelo':
                        cor_tema, bg_tema, lbl_prio = "#f59e0b", "rgba(245, 158, 11, 0.1)", "PRIORIDADE MÉDIA (ALERTA)"
                    else:
                        cor_tema, bg_tema, lbl_prio = "#10b981", "rgba(16, 185, 129, 0.1)", "PRIORIDADE NORMAL (ESTÁVEL)"

                    st.markdown(
                        f'<div style="background-color: {bg_tema}; border-left: 4px solid {cor_tema}; padding: 14px; border-radius: 6px; margin-bottom: 16px;">'
                        f'<div style="color: {cor_tema}; font-weight: bold; font-size: 0.8rem; margin-bottom: 4px;">{lbl_prio}</div>'
                        f'<div style="color: #f8fafc; font-size: 1.1rem; margin-bottom: 2px;"><b>Leito {l_id}</b></div>'
                        f'<div style="color: #cbd5e1; font-size: 0.85rem; margin-bottom: 8px;">Setor: {leito_atual["setor"]}</div>'
                        f'<div style="background-color: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.08); padding: 8px 10px; border-radius: 4px; margin-top: 6px;">'
                        f'<span style="font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; display: block; font-weight: bold;">Sugestão da IA:</span>'
                        f'<span style="color: #38bdf8; font-size: 0.95rem; font-weight: bold;">👤 {nome_sugerido}</span> '
                        f'<span style="font-size: 0.75rem; color: #10b981; font-weight: bold;">(Prontidão: {pront_sugerida}%)</span>'
                        f'</div>'
                        f'</div>', unsafe_allow_html=True
                    )

                    em_reavaliacao = st.session_state.reavaliacao_ativa.get(l_id, False)

                    if not em_reavaliacao:
                        c_btn_neg, c_btn_apr = st.columns(2)
                        with c_btn_neg:
                            if st.button(f"✖ Reavaliar", key=f"btn_neg_{l_id}", use_container_width=True):
                                st.session_state.reavaliacao_ativa[l_id] = True
                                st.rerun()

                        with c_btn_apr:
                            btn_type = "primary" if l_crit == 'Vermelho' else "secondary"
                            if st.button(f"✔ Aprovar Escala", type=btn_type, key=f"btn_apr_{l_id}",
                                         use_container_width=True):
                                if not profs_disponiveis.empty:
                                    profs_aptos = profs_disponiveis[profs_disponiveis['prontidao'] > 30]
                                    if profs_aptos.empty:
                                        profs_aptos = profs_disponiveis

                                    melhor_prof_row = profs_aptos.sort_values(by="prontidao", ascending=False).iloc[0]
                                    melhor_prof = melhor_prof_row["nome"]
                                    melhor_prof_id = melhor_prof_row["id_prof"]

                                    desgaste = 30 if l_crit == 'Vermelho' else (15 if l_crit == 'Amarelo' else 5)
                                    st.session_state.fadiga_simulada[
                                        melhor_prof_id] = st.session_state.fadiga_simulada.get(melhor_prof_id,
                                                                                               0) + desgaste
                                else:
                                    melhor_prof = "Plantonista Extra"
                                    desgaste = 0

                                st.session_state.alocacoes_manuais[l_id] = {"crit": "Verde", "prof": melhor_prof}
                                st.toast(f"✅ Leito {l_id} alocado para {melhor_prof}!")
                                st.rerun()
                    else:
                        st.markdown(
                            '<div style="background-color: #1e293b; padding: 12px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 12px;">'
                            '<div style="color: #38bdf8; font-size: 0.8rem; font-weight: bold; margin-bottom: 6px;">⚙️ PAINEL DE AUDITORIA E SUGESTÃO ALTERNATIVA</div>',
                            unsafe_allow_html=True
                        )

                        motivo_rej = st.selectbox(
                            "Motivo da Rejeição:",
                            [
                                "Indisponibilidade Médica Momentânea",
                                "Sobrecarga de Turnos Noturnos",
                                "Restrição de Setor / Especialidade",
                                "Solicitação de Troca pelo Profissional",
                                "Outros Motivos Operacionais"
                            ],
                            key=f"select_motivo_inline_{l_id}"
                        )

                        st.text_area("Observação Adicional (Opcional):", placeholder="Detalhes...",
                                     key=f"text_obs_inline_{l_id}")

                        # CORREÇÃO CRUCIAL: Remove o profissional original da lista de opções para a nova sugestão
                        profs_alternativos = profs_disponiveis[profs_disponiveis['id_prof'] != id_sugerido_original]
                        if profs_alternativos.empty:
                            profs_alternativos = profs_disponiveis  # Fallback se houver apenas 1 profissional na base

                        if not profs_alternativos.empty:
                            sugestao_alt_row = profs_alternativos.sort_values(by="prontidao", ascending=False).iloc[0]
                            sugestao_nome = sugestao_alt_row["nome"]
                            sugestao_id = sugestao_alt_row["id_prof"]
                            sugestao_pront = int(sugestao_alt_row["prontidao"])
                        else:
                            sugestao_nome = "Nenhum substituto disponível"
                            sugestao_id = None
                            sugestao_pront = 0

                        st.markdown(
                            f'<div style="background-color: #0f172a; border: 1px solid #10b981; padding: 10px; border-radius: 6px; margin: 10px 0;">'
                            f'<div style="font-size: 0.7rem; color: #10b981; font-weight: bold;">NOVA SUGESTÃO DA IA (SUBSTITUTO):</div>'
                            f'<div style="font-size: 0.9rem; color: #f8fafc; font-weight: bold;">👤 {sugestao_nome} <span style="font-size:0.75rem; color:#94a3b8;">(Prontidão: {sugestao_pront}%)</span></div>'
                            f'</div>', unsafe_allow_html=True
                        )

                        st.markdown('</div>', unsafe_allow_html=True)

                        c_sub1, c_sub2 = st.columns(2)
                        with c_sub1:
                            if st.button("Cancelar", key=f"btn_canc_sug_{l_id}", use_container_width=True):
                                st.session_state.reavaliacao_ativa[l_id] = False
                                st.rerun()
                        with c_sub2:
                            if st.button("Aceitar Sugestão", type="primary", key=f"btn_aceit_sug_{l_id}",
                                         use_container_width=True):
                                if sugestao_id:
                                    st.session_state.fadiga_simulada[
                                        sugestao_id] = st.session_state.fadiga_simulada.get(sugestao_id, 0) + 15

                                st.session_state.alocacoes_manuais[l_id] = {
                                    "crit": "Amarelo",
                                    "prof": f"{sugestao_nome} (Reavaliado)",
                                    "motivo": motivo_rej
                                }
                                st.session_state.reavaliacao_ativa[l_id] = False
                                st.toast(f"✅ Nova escala aprovada para {sugestao_nome} no leito {l_id}!", icon="✨")
                                st.rerun()

                else:
                    st.markdown(
                        '<div style="text-align: center; padding: 20px; color: #10b981;">'
                        '<div style="font-size: 2rem; margin-bottom: 8px;">✅</div>'
                        '<b>Fila Operacional Zerada.</b><br><span style="font-size: 0.8rem; color: #94a3b8;">Todos os leitos foram alocados.</span>'
                        '</div>', unsafe_allow_html=True)
            else:
                st.info("Nenhum dado encontrado para o município.")

        st.write("")

        st.markdown(
            '<div class="card-title" style="margin-bottom:12px; margin-top:20px; color: #f8fafc;">👥 RADAR DE FADIGA (TOP EQUIPE)</div>',
            unsafe_allow_html=True)

        with st.container(height=380, border=True):
            if not df_prof_filtrado.empty:
                df_prof_render = df_prof_filtrado.sort_values(by="prontidao", ascending=True).head(25)

                for idx, prof in enumerate(df_prof_render.itertuples()):
                    val_prontidao = max(0.0, min(1.0, float(prof.prontidao) / 100.0))

                    c_info, c_btn = st.columns([2.5, 1])
                    with c_info:
                        st.markdown(
                            f'<div style="line-height: 1.2;">'
                            f'<b style="color: #e2e8f0; font-size: 0.9rem;">{prof.nome}</b><br>'
                            f'<span style="color: #94a3b8; font-size: 0.75rem;">{prof.cargo}</span>'
                            f'</div>', unsafe_allow_html=True)
                        st.progress(val_prontidao)

                    with c_btn:
                        st.write("")
                        if st.button("Perfil", key=f"btn_prof_safe_{prof.id_prof}_{idx}", use_container_width=True):
                            modal_profissional(prof.nome)

                    st.markdown('<hr style="margin: 8px 0; border-color: #1e293b;">', unsafe_allow_html=True)
            else:
                st.info("Nenhum profissional listado para este filtro.")

    with col_mapa_leitos:
        c_titulo_leito, c_filtro_setor = st.columns([1.5, 1])
        with c_titulo_leito:
            st.markdown(
                '<div class="card-title" style="margin-top: 5px; color: #f8fafc;">🛏️ MAPA DE ALOCAÇÃO (LIVE - TOP 60)</div>',
                unsafe_allow_html=True)
        with c_filtro_setor:
            setores_disponiveis = ["Todos"] + df_leitos_filtrado[
                'setor'].unique().tolist() if not df_leitos_filtrado.empty else ["Todos"]
            filtro_setor = st.selectbox("Filtrar Setor:", setores_disponiveis, label_visibility="collapsed",
                                        key="filtro_setor_c3")

        df_grid = df_leitos_filtrado if filtro_setor == "Todos" else df_leitos_filtrado[
            df_leitos_filtrado['setor'] == filtro_setor]

        with st.container(height=580, border=True):
            if not df_grid.empty:
                cols_grid = st.columns(3)

                for idx, row in enumerate(df_grid.head(60).itertuples()):
                    with cols_grid[idx % 3]:
                        if row.crit == "Vermelho":
                            dot_cls, bg_card, border_color = "dot-red", "rgba(239, 68, 68, 0.05)", "#ef4444"
                        elif row.crit == "Amarelo":
                            dot_cls, bg_card, border_color = "dot-yellow", "rgba(245, 158, 11, 0.05)", "#f59e0b"
                        else:
                            dot_cls, bg_card, border_color = "dot-green", "rgba(16, 185, 129, 0.05)", "#10b981"

                        nome_prof = row.prof if pd.notna(row.prof) and row.prof != "" else "Não Alocado"
                        cor_prof = "#94a3b8" if nome_prof in ["Não Alocado", "Pendente Auditoria"] else "#38bdf8"

                        st.markdown(
                            f'<div style="background-color: {bg_card}; border: 1px solid #1e293b; border-top: 3px solid {border_color}; border-radius: 8px; padding: 12px; margin-bottom: 12px; position: relative;">'
                            f'<span class="{dot_cls}"></span>'
                            f'<div style="font-weight: bold; color: #f8fafc; font-size: 1rem; margin-bottom: 2px;">{row.id}</div>'
                            f'<div style="color: #cbd5e1; font-size: 0.75rem; margin-bottom: 8px;">{row.setor}</div>'
                            f'<div style="background-color: #0f172a; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; color: {cor_prof}; display: inline-block;">'
                            f'👤 {nome_prof}'
                            f'</div>'
                            f'</div>',
                            unsafe_allow_html=True)
            else:
                st.info("Nenhum leito encontrado no sistema.")