from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import os
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
import pickle
import psycopg2
from dotenv import load_dotenv

# === 1. Carregar variáveis do arquivo .env ===
load_dotenv()

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

app = Flask(
    __name__,
    static_folder='../frontend/static',
    template_folder='../frontend/pages'
)

# ===========================
# Paths e configurações
# ===========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'BaseDPEvolucaoMensalCisp.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'model.pkl')

SHAPEFILES = {
    "mcirc": os.path.join(BASE_DIR, 'data', 'RJ_Municipios_2024.shp'),
    "cisp": os.path.join(BASE_DIR, 'data', 'lm_cisp_bd.shp'),
    "aisp": os.path.join(BASE_DIR, 'data', 'lm_aisp_072024.shp'),
    "risp": os.path.join(BASE_DIR, 'data', 'Limite_RISP_WGS.shp')
}

MAP_FOLDER = os.path.join(app.static_folder, "img")
os.makedirs(MAP_FOLDER, exist_ok=True)

COLUMN_MAPPING = {
    "mcirc": "CD_MUN",
    "cisp": "cisp",
    "aisp": "aisp",
    "risp": "risp"
}

# =======================
# Carregar modelo
# =======================
model = None
feature_names = [
    'cisp', 'mes', 'ano', 'mcirc', 'tentat_hom', 'estupro',
    'lesao_corp_culposa', 'roubo_veiculo', 'estelionato',
    'apreensao_drogas', 'trafico_drogas', 'apf',
    'pessoas_desaparecidas', 'encontro_cadaver', 'registro_ocorrencias'
]

try:
    with open(MODEL_PATH, 'rb') as f:
        model = pickle.load(f)
    print(f"✓ Modelo carregado com sucesso! ({type(model).__name__})")
except Exception as e:
    print(f"✗ Erro ao carregar modelo: {e}")

# ===========================
# Função para carregar dados
# ===========================
def load_data():
    # usa caminho absoluto para evitar problemas de working directory
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH, sep=";", encoding="latin1")
    return df


def get_media_mes_proximo(df, mes, ano, coluna='letalidade_violenta'):
    """
    Retorna a média do mês mais próximo anterior que tenha algum dado na coluna especificada,
    buscando retroativamente por anos anteriores se necessário.
    """
    mes_atual = int(mes)
    ano_atual = int(ano)

    for _ in range(120):  # Limite de 10 anos para evitar loop infinito
        mes_atual -= 1
        if mes_atual == 0:
            mes_atual = 12
            ano_atual -= 1

        df_filtrado = df[(df['mes'] == mes_atual) & (df['ano'] == ano_atual)]
        if not df_filtrado.empty and coluna in df_filtrado.columns:
            media = df_filtrado[coluna].mean()
            if pd.notna(media):
                return float(media)

    return None  # Nenhum dado encontrado nos últimos 10 anos


def gerar_drivers_principais(df, features_dict, importance_dict):
    """
    Gera até 3 drivers principais: features que mais mudaram em relação ao mês mais próximo anterior
    que tenha dados, considerando apenas features relevantes pelo modelo.
    """
    drivers = []
    mes = int(features_dict['mes'])
    ano = int(features_dict['ano'])

    for feature, importance in sorted(importance_dict.items(), key=lambda x: x[1], reverse=True):
        # Ignora features irrelevantes
        if importance < 0.01 or feature in ['cisp', 'mes', 'ano']:
            continue

        # Pega média do mês mais próximo anterior **da mesma feature**
        valor_anterior = get_media_mes_proximo(df, mes, ano, coluna=feature)
        valor_atual = features_dict.get(feature, 0)

        if valor_anterior is None or valor_anterior == 0:
            continue  # não há dados anteriores para comparação

        diff_percent = (valor_atual - valor_anterior) / valor_anterior * 100

        if diff_percent > 3:
            frase = f"aumento de {feature.replace('_', ' ')} (+{round(diff_percent)}%)"
        elif diff_percent < -3:
            frase = f"queda de {feature.replace('_', ' ')} ({round(diff_percent)}%)"
        else:
            frase = f"{feature.replace('_', ' ')} estável"

        drivers.append(frase)
        if len(drivers) >= 3:
            break

    return ", ".join(drivers)


def classificar_tendencia(pred, media_mes_proximo):
    if media_mes_proximo is None or media_mes_proximo == 0:
        return "Sem dados suficientes"

    diff_ratio = (pred - media_mes_proximo) / media_mes_proximo

    if diff_ratio <= -0.2:
        return "Queda significativa"
    elif diff_ratio <= -0.05:
        return "Leve queda"
    elif diff_ratio < 0.05:
        return "Estável"
    elif diff_ratio < 0.2:
        return "Leve aumento"
    else:
        return "Aumento significativo"


def classificar_risco(pred, df):
    vals = df['letalidade_violenta'][df['letalidade_violenta'] > 0]
    if vals.empty:
        return "Baixo"

    q33 = vals.quantile(0.33)
    q66 = vals.quantile(0.66)

    if pred <= max(q33, 5):
        return "Baixo"
    elif pred <= max(q66, 10):
        return "Moderado"
    else:
        return "Alto"


def salvar_previsao_banco(features_dict, prediction_value):
    # se as variáveis de conexão não estiverem setadas, sai sem erro
    if not all([DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT]):
        print("Parâmetros do DB ausentes — pulando salvamento no banco.")
        return

    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO crimes_RJ.dados_previstos
            (cisp, mcirc, mes, ano, letalidade_violenta, tentat_hom, estupro,
             lesao_corp_culposa, roubo_veiculo, estelionato, apreensao_drogas,
             trafico_drogas, apf, pessoas_desaparecidas, encontro_cadaver, registro_ocorrencias)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            int(features_dict['cisp']),
            int(features_dict['mcirc']),
            int(features_dict['mes']),
            int(features_dict['ano']),
            int(round(prediction_value)),
            int(features_dict.get('tentat_hom', 0)),
            int(features_dict.get('estupro', 0)),
            int(features_dict.get('lesao_corp_culposa', 0)),
            int(features_dict.get('roubo_veiculo', 0)),
            int(features_dict.get('estelionato', 0)),
            int(features_dict.get('apreensao_drogas', 0)),
            int(features_dict.get('trafico_drogas', 0)),
            int(features_dict.get('apf', 0)),
            int(features_dict.get('pessoas_desaparecidas', 0)),
            int(features_dict.get('encontro_cadaver', 0)),
            int(features_dict.get('registro_ocorrencias', 0))
        ))
        conn.commit()
        cursor.close()
        conn.close()
        print("Previsão inserida com sucesso no banco!")
    except Exception as e:
        print("Erro ao inserir previsão no banco:", e)

# ===========================
# Rotas de páginas
# ===========================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/previsao')
def previsao():
    return render_template('previsao.html')

@app.route('/agrupamentos')
def agrupamentos():
    return render_template('agrupamentos.html')

# ===========================
# API - Dashboard
# ===========================
@app.route('/api/dashboard_data')
def dashboard_data():
    df = load_data()
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    municipio = request.args.get("municipio")

    # Preparar datas
    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")

    # Filtrar por município
    if municipio:
        gdf_mun = gpd.read_file(SHAPEFILES["mcirc"])[["CD_MUN", "NM_MUN"]]
        gdf_mun["CD_MUN"] = gdf_mun["CD_MUN"].astype(str)
        df["mcirc"] = df["mcirc"].astype(str)
        df = df.merge(gdf_mun, left_on="mcirc", right_on="CD_MUN", how="left")
        df = df[df["NM_MUN"] == municipio]

    # Aplicar filtros de data
    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]

    # Caso não haja dados após os filtros
    if df.empty:
        return jsonify({
            "letalidade_violenta_total": 0,
            "homicidios_dolosos": 0,
            "homicidios_dolosos_pct": None,
            "latrocinios": 0,
            "variacao_latrocinio_anual_pct": None,
            "mortes_intervencao_policial": 0,
            "tendencia_mortes_intervencao_policial": "Sem dados",
            "evolucao_temporal": [],
            "correlacao_crimes": {},
            "scatter_data": []
        })

    # Agrupamento mensal
    df_grouped = df.groupby(["ano", "mes"]).agg({
        "letalidade_violenta": "sum",
        "hom_doloso": "sum",
        "latrocinio": "sum",
        "hom_por_interv_policial": "sum",
        "tentat_hom": "sum",
        "lesao_corp_culposa": "sum",
        "estupro": "sum",
        "estelionato": "sum",
        "apreensao_drogas": "sum",
        "trafico_drogas": "sum",
        "apf": "sum",
        "pessoas_desaparecidas": "sum",
        "encontro_cadaver": "sum",
        "registro_ocorrencias": "sum",
        "roubo_rua": "sum"
    }).reset_index().sort_values(["ano", "mes"]).reset_index(drop=True)

    # KPIs principais
    letalidade_total = int(df_grouped["letalidade_violenta"].sum())

    # === Homicídios dolosos (média do período filtrado) ===
    homicidios_dolosos = df["hom_doloso"].mean() if not df.empty else 0

    # === Comparação com a média do mês anterior à data de início ===
    homicidios_dolosos_pct = None
    if inicio:
        inicio_dt = pd.to_datetime(inicio)
        mes_prev = inicio_dt.month - 1
        ano_prev = inicio_dt.year
        if mes_prev == 0:
            mes_prev = 12
            ano_prev -= 1

        # Carrega dataset completo (sem filtro de data, com filtro de município se existir)
        df_prev = load_data()
        df_prev["data"] = pd.to_datetime(df_prev["ano"].astype(str) + "-" + df_prev["mes"].astype(str) + "-01")

        if municipio:
            gdf_mun = gpd.read_file(SHAPEFILES["mcirc"])[["CD_MUN", "NM_MUN"]]
            gdf_mun["CD_MUN"] = gdf_mun["CD_MUN"].astype(str)
            df_prev["mcirc"] = df_prev["mcirc"].astype(str)
            df_prev = df_prev.merge(gdf_mun, left_on="mcirc", right_on="CD_MUN", how="left")
            df_prev = df_prev[df_prev["NM_MUN"] == municipio]

        # === Agrupar para garantir médias mensais ===
        df_grouped_periodo = df.groupby(["ano", "mes"])["hom_doloso"].mean().reset_index()
        homicidios_dolosos = df_grouped_periodo["hom_doloso"].mean()  # média mensal do período

        df_grouped_prev = df_prev.groupby(["ano", "mes"])["hom_doloso"].mean().reset_index()
        df_mes_prev = df_grouped_prev[(df_grouped_prev["ano"] == ano_prev) & (df_grouped_prev["mes"] == mes_prev)]

        if not df_mes_prev.empty:
            media_prev = df_mes_prev["hom_doloso"].iloc[0]  # média mensal do mês anterior
            if media_prev > 0:
                homicidios_dolosos_pct = ((homicidios_dolosos - media_prev) / media_prev) * 100

    # === Latrocínios (comparação com ano anterior) ===
    latrocinios = int(df_grouped["latrocinio"].sum())
    df_full = load_data()
    df_full["data"] = pd.to_datetime(df_full["ano"].astype(str) + "-" + df_full["mes"].astype(str) + "-01")

    if municipio:
        gdf_mun = gpd.read_file(SHAPEFILES["mcirc"])[["CD_MUN", "NM_MUN"]]
        gdf_mun["CD_MUN"] = gdf_mun["CD_MUN"].astype(str)
        df_full["mcirc"] = df_full["mcirc"].astype(str)
        df_full = df_full.merge(gdf_mun, left_on="mcirc", right_on="CD_MUN", how="left")
        df_full = df_full[df_full["NM_MUN"] == municipio]

    soma_ano_ant = 0
    for _, row in df_grouped.iterrows():
        ano_ant = int(row["ano"]) - 1
        mes = int(row["mes"])
        df_mes_ant = df_full[(df_full["ano"] == ano_ant) & (df_full["mes"] == mes)]
        if not df_mes_ant.empty:
            soma_ano_ant += df_mes_ant["latrocinio"].sum()

    variacao_latrocinio_anual_pct = ((latrocinios - soma_ano_ant) / soma_ano_ant) * 100 if soma_ano_ant > 0 else None

    # === Mortes por intervenção policial e tendência ===
    mortes_intervencao_policial = df["hom_por_interv_policial"].mean()

    if inicio:
        inicio_dt = pd.to_datetime(inicio)
        mes_prev = inicio_dt.month - 1
        ano_prev = inicio_dt.year
        if mes_prev == 0:
            mes_prev = 12
            ano_prev -= 1

        df_trend_base = load_data()
        df_trend_base["data"] = pd.to_datetime(df_trend_base["ano"].astype(str) + "-" + df_trend_base["mes"].astype(str) + "-01")

        if municipio:
            gdf_mun = gpd.read_file(SHAPEFILES["mcirc"])[["CD_MUN", "NM_MUN"]]
            gdf_mun["CD_MUN"] = gdf_mun["CD_MUN"].astype(str)
            df_trend_base["mcirc"] = df_trend_base["mcirc"].astype(str)
            df_trend_base = df_trend_base.merge(gdf_mun, left_on="mcirc", right_on="CD_MUN", how="left")
            df_trend_base = df_trend_base[df_trend_base["NM_MUN"] == municipio]

        df_prev_mes = df_trend_base[(df_trend_base["ano"] == ano_prev) & (df_trend_base["mes"] == mes_prev)]

        if df_prev_mes.empty:
            tendencia_interv = "Indefinida"
        else:
            media_prev = df_prev_mes["hom_por_interv_policial"].mean()
            ratio = mortes_intervencao_policial / media_prev if media_prev > 0 else 1
            if ratio > 1.05:
                tendencia_interv = "crescente"
            elif ratio < 0.95:
                tendencia_interv = "decrescente"
            else:
                tendencia_interv = "estável"
    else:
        tendencia_interv = "Indefinida"

    # Evolução temporal
    df_grouped["Periodo"] = df_grouped["ano"].astype(str) + "-" + df_grouped["mes"].astype(str).str.zfill(2)
    evolucao_temporal = df_grouped[["Periodo", "letalidade_violenta"]].rename(
        columns={"Periodo": "x", "letalidade_violenta": "y"}
    ).to_dict(orient="records")

    # Correlação com outros crimes
    col_corr = ["tentat_hom", "lesao_corp_culposa", "estupro", "estelionato",
                "apreensao_drogas", "trafico_drogas", "apf", "pessoas_desaparecidas",
                "encontro_cadaver", "registro_ocorrencias"]
    correlacao_dict = df_grouped[["letalidade_violenta"] + col_corr].corr()["letalidade_violenta"] \
        .drop("letalidade_violenta").to_dict()

    # Scatter
    scatter_data = []
    if "roubo_rua" in df.columns:
        scatter_data = df[["roubo_rua", "letalidade_violenta"]].dropna().to_dict(orient="records")
        scatter_data = [{"x": r["roubo_rua"], "y": r["letalidade_violenta"]} for r in scatter_data]

    def replace_invalid(obj):
        if isinstance(obj, dict):
            return {k: replace_invalid(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [replace_invalid(v) for v in obj]
        elif isinstance(obj, (float, np.floating)) and (np.isnan(obj) or np.isinf(obj)):
            return None
        return obj

    # Bloqueia comparação se início for inválido
    if not inicio or pd.to_datetime(inicio) < pd.Timestamp("2003-01-01"):
        homicidios_dolosos_pct = None
        variacao_latrocinio_anual_pct = None

    return jsonify(replace_invalid({
        "letalidade_violenta_total": letalidade_total,
        "homicidios_dolosos": round(homicidios_dolosos, 2),
        "homicidios_dolosos_pct": homicidios_dolosos_pct,
        "latrocinios": latrocinios,
        "variacao_latrocinio_anual_pct": variacao_latrocinio_anual_pct,
        "mortes_intervencao_policial": round(mortes_intervencao_policial or 0, 2),
        "tendencia_mortes_intervencao_policial": tendencia_interv,
        "evolucao_temporal": evolucao_temporal,
        "correlacao_crimes": correlacao_dict,
        "scatter_data": scatter_data
    }))

@app.route('/api/medias')
def api_medias():
    df = load_data()
    medias = df.mean(numeric_only=True).to_dict()
    return jsonify(medias)

# ===========================
# API - Municípios
# ===========================
@app.route("/api/municipios")
def get_municipios():
    shapefile = SHAPEFILES["mcirc"]
    gdf = gpd.read_file(shapefile)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    municipios = sorted(gdf['NM_MUN'].unique().tolist())
    return jsonify(municipios)

# ===========================
# API - Mapa geográfico
# ===========================
@app.route("/api/map_image/<group_by>")
def map_image(group_by):
    df = load_data()
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    municipio = request.args.get("municipio")

    shapefile = SHAPEFILES.get(group_by)
    if not shapefile:
        return jsonify({"error": "Agrupamento inválido"}), 400

    shapefile_col = COLUMN_MAPPING.get(group_by)
    gdf = gpd.read_file(shapefile)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")
    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]

    if municipio and "NM_MUN" in gdf.columns:
        gdf = gdf[gdf["NM_MUN"] == municipio]

    df_grouped = df.groupby(group_by)["letalidade_violenta"].sum().reset_index()
    df_grouped[group_by] = df_grouped[group_by].astype(str)
    gdf[shapefile_col] = gdf[shapefile_col].astype(str)
    gdf = gdf.merge(df_grouped, left_on=shapefile_col, right_on=group_by, how="left")
    gdf["letalidade_violenta"] = gdf["letalidade_violenta"].fillna(0)

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    gdf.plot(
        column="letalidade_violenta",
        cmap="YlOrRd",
        linewidth=0.8,
        ax=ax,
        edgecolor='0.8',
        legend=True
    )
    ax.set_axis_off()
    plt.title("Letalidade Violenta", fontsize=15)

    params_str = f"{group_by}_{inicio}_{fim}_{municipio}".replace(" ", "_").replace(":", "_")
    image_name = f"{params_str}.png"
    image_path = os.path.join(MAP_FOLDER, image_name)
    plt.savefig(image_path, bbox_inches="tight")
    plt.close(fig)

    return jsonify({"image_url": f"/static/img/{image_name}"})

# ===========================
# API - Features do modelo
# ===========================
@app.route('/api/model_features')
def model_features():
    return jsonify(feature_names)

# ===========================
# API - Previsão
# ===========================
@app.route('/api/previsao', methods=['POST'])
def previsao_api():
    global model
    df = load_data()
    data = request.get_json()

    if not model:
        return jsonify({"error": "Modelo não carregado"}), 500

    # === Preparar dados para previsão ===
    X = pd.DataFrame([data['features']], columns=feature_names)
    pred = int(round(model.predict(X)[0]))

    # === Histórico real (soma por mês) ===
    df_hist = df.groupby(['ano', 'mes'])['letalidade_violenta'].sum().reset_index()
    df_hist = df_hist.sort_values(['ano', 'mes'])

    preds_boot = []
    for _ in range(1000):
        sample = df_hist['letalidade_violenta'].sample(len(df_hist), replace=True)
        preds_boot.append(pred + (sample.mean() - df_hist['letalidade_violenta'].mean()))
    lower = max(np.percentile(preds_boot, 2.5), 0)
    upper = np.percentile(preds_boot, 97.5)
    
    # === Média histórica mensal ===
    df_hist_media = df.groupby(['ano', 'mes'])['letalidade_violenta'].mean().reset_index()
    media_historica_valores = df_hist_media['letalidade_violenta'].tolist()

    # === Buscar previsões e médias no banco de dados em uma única conexão ===
    prev_data = []
    if all([DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT]):
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ano, mes, SUM(letalidade_violenta), AVG(letalidade_violenta)
                FROM crimes_RJ.dados_previstos
                GROUP BY ano, mes
                ORDER BY ano, mes
            """)
            prev_data = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            print("Erro ao buscar previsões no banco:", e)

    prev_labels = [f"{row[0]}-{row[1]:02d}" for row in prev_data]
    prev_valores = [row[2] for row in prev_data]
    media_previsoes_valores = [row[3] for row in prev_data]

    # === Informações do período atual ===
    mes = int(data['features'][1])
    ano = int(data['features'][2])
    media_mes_proximo = get_media_mes_proximo(df, mes, ano)
    tendencia = classificar_tendencia(pred, media_mes_proximo)
    risco = classificar_risco(pred, df)

    # === Importância das features (robusto a vários tipos de modelo) ===
    try:
        importance = list(model.feature_importances_)
    except Exception:
        try:
            importance = list(model.booster_.feature_importance(importance_type='gain'))
        except Exception:
            importance = [0] * len(feature_names)
    importance_dict = dict(zip(feature_names, importance))

    # === Drivers principais ===
    drivers = gerar_drivers_principais(df, dict(zip(feature_names, data['features'])), importance_dict)

    # === Salvar previsão no banco ===
    try:
        salvar_previsao_banco(dict(zip(feature_names, data['features'])), pred)
    except Exception as e:
        print("Erro ao salvar previsão (não fatal):", e)

    # === Dados históricos para gráfico ===
    historico_labels = df_hist.apply(lambda row: f"{int(row['ano'])}-{int(row['mes']):02d}", axis=1).tolist()
    historico_valores = df_hist['letalidade_violenta'].tolist()

    return jsonify({
        "success": True,
        "previsao_leitura": pred,
        "intervalo_95": [lower, upper],
        "tendencia": tendencia,
        "risco": risco,
        "drivers": drivers,
        "feature_importance": {k: float(v) for k, v in importance_dict.items()},
        "historico_labels": historico_labels,
        "historico_valores": historico_valores,
        "media_historica_valores": media_historica_valores,
        "prev_valores": prev_valores,
        "media_previsoes_valores": media_previsoes_valores
    })

# ===========================
# API - Agrupamentos
# ===========================
@app.route("/api/agrupamentos_data")
def agrupamentos_data():
    df = load_data()
    k = int(request.args.get("k", 4))
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    municipio = request.args.get("municipio")

    # Filtragem por data
    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")
    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]

    # Filtragem por município
    if municipio:
        try:
            gdf_mun = gpd.read_file(SHAPEFILES["mcirc"])[["CD_MUN", "NM_MUN"]]
            gdf_mun["CD_MUN"] = gdf_mun["CD_MUN"].astype(str)
            df["mcirc"] = df["mcirc"].astype(str)
            df = df.merge(gdf_mun, left_on="mcirc", right_on="CD_MUN", how="left")
            df = df[df["NM_MUN"] == municipio]
        except Exception as e:
            print("Erro ao filtrar por município:", e)

    if df.empty:
        return jsonify({"error": "Sem dados após filtragem."}), 400

    # Seleção e exclusão das variáveis
    dados_cluster = df.select_dtypes(include=[np.number]).drop(columns=[
        'hom_doloso', 'lesao_corp_morte', 'latrocinio', 'cvli', 'hom_por_interv_policial', 
        'ameaca', 'total_roubos', 'recuperacao_veiculos', 'fase', 'encontro_ossada', 
        'furto_bicicleta', 'sequestro', 'lesao_corp_dolosa', 'roubo_conducao_saque', 
        'sequestro_relampago', 'roubo_banco', 'roubo_bicicleta', 'roubo_residencia', 
        'furto_coletivo', 'posse_drogas', 'roubo_comercio', 'extorsao', 'roubo_cx_eletronico', 
        'roubo_apos_saque', 'pol_civis_mortos_serv', 'hom_culposo', 'furto_celular',
        'furto_transeunte', 'cmba', 'aisp', 'pol_militares_mortos_serv', 'total_furtos', 
        'aaapai', 'furto_veiculos', 'roubo_transeunte', 'cmp', 'risp', 'roubo_celular', 
        'outros_furtos', 'roubo_rua', 'apreensao_drogas_sem_autor', 'roubo_em_coletivo', 
        'outros_roubos', 'roubo_carga'
    ])

    if dados_cluster.empty:
        return jsonify({"error": "Sem dados numéricos para agrupar."}), 400

    # Imputação e normalização
    colunas = dados_cluster.columns
    dados_imp = pd.DataFrame(
        SimpleImputer(strategy="mean").fit_transform(dados_cluster),
        columns=colunas
    )
    dados_scaled = StandardScaler().fit_transform(dados_imp)

    # KMeans clustering
    kmeans = KMeans(n_clusters=k, random_state=42)
    clusters = kmeans.fit_predict(dados_scaled)
    df['cluster'] = clusters
    media_clusters = df.groupby('cluster')[colunas].mean().round(2).to_dict(orient="index")

    # PCA 2D
    pca = PCA(n_components=2)
    pca_result = pca.fit_transform(dados_scaled)
    pca_df = pd.DataFrame(pca_result, columns=["pca1", "pca2"])
    pca_df["cluster"] = clusters
    pca_data = pca_df.to_dict(orient="records")

    # Perfil médio dos clusters
    df_cluster_profile = df.groupby("cluster")[colunas].mean()

    # Remove colunas geográficas
    for col_geo in ["cisp", "aisp", "risp", "mcirc", "ano", "mes"]:
        if col_geo in df_cluster_profile.columns:
            df_cluster_profile = df_cluster_profile.drop(columns=[col_geo])

    # Normaliza para visualização
    df_norm = (df_cluster_profile - df_cluster_profile.min()) / \
              (df_cluster_profile.max() - df_cluster_profile.min())

    perfil_img_path = os.path.join(MAP_FOLDER, f"perfil_medio_{k}.png")
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    df_norm.plot(kind="bar", ax=ax1)
    ax1.set_title("Perfil médio dos clusters (valores normalizados)")
    ax1.set_ylabel("Intensidade relativa")
    ax1.set_xticklabels([f"Cluster {i}" for i in df_norm.index], rotation=0)
    plt.tight_layout()
    fig1.savefig(perfil_img_path, dpi=150)
    plt.close(fig1)

    # Importância das variáveis
    importances = {}
    for col in dados_cluster.columns:
        group_means = df.groupby('cluster')[col].mean()
        inter = np.var(group_means)
        intra = np.mean(df.groupby('cluster')[col].var())
        importances[col] = inter / (intra + 1e-6)
    importances_series = pd.Series(importances).sort_values(ascending=False)

    return jsonify({
        "media_clusters": media_clusters,
        "pca_data": pca_data,
        "explained_variance": [round(v, 3) for v in pca.explained_variance_ratio_],
        "perfil_medio_img": f"/static/img/perfil_medio_{k}.png",
        "importancias": importances_series.to_dict()
    })

# ===========================
# Main
# ===========================
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
