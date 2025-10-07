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

app = Flask(
    __name__,
    static_folder='../frontend/static',
    template_folder='../frontend/pages'
)

# ===========================
# Paths e configurações
# ===========================
DATA_PATH = 'backend/data/BaseDPEvolucaoMensalCisp.csv'
MODEL_PATH = 'models/model.pkl'

SHAPEFILES = {
    "mcirc": "backend/data/RJ_Municipios_2024.shp",
    "cisp": "backend/data/lm_cisp_bd.shp",
    "aisp": "backend/data/lm_aisp_072024.shp",
    "risp": "backend/data/Limite_RISP_WGS.shp"
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
    model_path = os.path.join(os.path.dirname(__file__), MODEL_PATH)
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    print(f"✓ Modelo carregado com sucesso! ({type(model).__name__})")
except Exception as e:
    print(f"✗ Erro ao carregar modelo: {e}")

# ===========================
# Função para carregar dados
# ===========================
def load_data():
    df = pd.read_csv(DATA_PATH, sep=";", encoding="latin1")
    return df

def get_soma_mes_anterior(df, mes, ano):
    if mes == 1:
        mes_anterior = 12
        ano_anterior = ano - 1
    else:
        mes_anterior = mes - 1
        ano_anterior = ano

    df_filtrado = df[(df['mes'] == mes_anterior) & (df['ano'] == ano_anterior)]
    if df_filtrado.empty:
        return None

    return df_filtrado['letalidade_violenta'].sum()

def gerar_drivers_principais(df, features_dict, importance_dict):
    drivers = []
    mes = int(features_dict['mes'])
    ano = int(features_dict['ano'])

    for feature, importance in sorted(importance_dict.items(), key=lambda x: x[1], reverse=True):
        if importance < 0.01 or feature in ['cisp', 'mes', 'ano']:
            continue

        mes_anterior = mes - 1 if mes > 1 else 12
        ano_anterior = ano if mes > 1 else ano - 1
        df_mes_anterior = df[(df['mes'] == mes_anterior) & (df['ano'] == ano_anterior)]

        if df_mes_anterior.empty or feature not in df_mes_anterior.columns:
            continue

        valor_anterior = df_mes_anterior[feature].sum()
        valor_atual = features_dict.get(feature, 0)

        if valor_anterior is None or valor_anterior == 0:
            continue

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

def classificar_tendencia(pred, soma_mes_ant):
    if soma_mes_ant is None or soma_mes_ant == 0:
        return "Sem dados suficientes"

    diff_ratio = (pred - soma_mes_ant) / soma_mes_ant

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
    try:
        conn = psycopg2.connect(
            dbname="crimes_RJ",
            user="postgres",
            password="crimes",
            host="localhost",
            port="5432"
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

    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")

    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]
    if municipio:
        gdf_mun = gpd.read_file(SHAPEFILES["mcirc"])[["CD_MUN", "NM_MUN"]]
        gdf_mun["CD_MUN"] = gdf_mun["CD_MUN"].astype(str)
        df["mcirc"] = df["mcirc"].astype(str)
        df = df.merge(gdf_mun, left_on="mcirc", right_on="CD_MUN", how="left")
        df = df[df["NM_MUN"] == municipio]

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
    }).reset_index().sort_values(["ano","mes"]).reset_index(drop=True)

    latest_row = df_grouped.iloc[-1]
    letalidade_total = int(latest_row["letalidade_violenta"])
    homicidios_dolosos = int(latest_row["hom_doloso"])
    latrocinios = int(latest_row["latrocinio"])
    mortes_interv_policial = int(latest_row["hom_por_interv_policial"])

    homicidios_dolosos_pct = None
    if len(df_grouped) > 1:
        prev_row = df_grouped.iloc[-2]
        hom_prev = prev_row["hom_doloso"]
        homicidios_dolosos_pct = ((homicidios_dolosos - hom_prev)/hom_prev*100) if hom_prev > 0 else None

    ano_atual, mes_atual = latest_row["ano"], latest_row["mes"]
    latro_ano_ant = df_grouped[(df_grouped["ano"] == ano_atual - 1) & (df_grouped["mes"] == mes_atual)]
    variacao_latrocinio_anual = None
    if not latro_ano_ant.empty:
        lat_ant = latro_ano_ant.iloc[0]["latrocinio"]
        variacao_latrocinio_anual = ((latrocinios - lat_ant)/lat_ant*100) if lat_ant > 0 else None

    tendencia_interv = "Indefinida"
    if len(df_grouped) >= 4:
        ultimos = df_grouped.tail(4)["hom_por_interv_policial"].values
        media_recente = ultimos[-2:].mean()
        media_antiga = ultimos[:2].mean()
        if media_recente > media_antiga * 1.05:
            tendencia_interv = "crescente"
        elif media_recente < media_antiga * 0.95:
            tendencia_interv = "decrescente"
        else:
            tendencia_interv = "estável"

    df_grouped["Periodo"] = df_grouped["ano"].astype(str) + "-" + df_grouped["mes"].astype(str).str.zfill(2)
    evolucao_temporal = df_grouped[["Periodo","letalidade_violenta"]].rename(
        columns={"Periodo":"x","letalidade_violenta":"y"}
    ).to_dict(orient="records")

    col_corr = [
        "tentat_hom", "lesao_corp_culposa", "estupro", "estelionato", 
        "apreensao_drogas","trafico_drogas","apf","pessoas_desaparecidas",
        "encontro_cadaver","registro_ocorrencias"
    ]
    correlacao_dict = df_grouped[["letalidade_violenta"] + col_corr].corr()["letalidade_violenta"].drop("letalidade_violenta").to_dict()

    scatter_data = []
    if "roubo_rua" in df.columns:
        scatter_data = df[["roubo_rua","letalidade_violenta"]].dropna().to_dict(orient="records")
        scatter_data = [{"x":row["roubo_rua"],"y":row["letalidade_violenta"]} for row in scatter_data]

    return jsonify({
        "letalidade_violenta_total": letalidade_total,
        "homicidios_dolosos": homicidios_dolosos,
        "homicidios_dolosos_pct": homicidios_dolosos_pct,
        "latrocinios": latrocinios,
        "variacao_latrocinio_anual_pct": variacao_latrocinio_anual,
        "mortes_intervencao_policial": mortes_interv_policial,
        "tendencia_mortes_intervencao_policial": tendencia_interv,
        "evolucao_temporal": evolucao_temporal,
        "correlacao_crimes": correlacao_dict,
        "scatter_data": scatter_data
    })

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

    X = pd.DataFrame([data['features']], columns=feature_names)
    pred = model.predict(X)[0]

    df_hist = df.groupby(['ano', 'mes'])['letalidade_violenta'].sum().reset_index()
    df_hist = df_hist.sort_values(['ano','mes'])
    
    # Intervalo 95% via bootstrap
    preds_boot = []
    for _ in range(1000):
        sample = df_hist['letalidade_violenta'].sample(len(df_hist), replace=True)
        # Simula pequenas variações na previsão
        preds_boot.append(pred + (sample.mean() - df_hist['letalidade_violenta'].mean()))
    lower = max(np.percentile(preds_boot, 2.5), 0)
    upper = np.percentile(preds_boot, 97.5)

    mes = int(data['features'][1])
    ano = int(data['features'][2])
    soma_mes_ant = get_soma_mes_anterior(df, mes, ano)

    tendencia = classificar_tendencia(pred, soma_mes_ant)
    risco = classificar_risco(pred, df)

    # Importância das features 
    importance = model.booster_.feature_importance(importance_type='gain').tolist()
    importance_dict = {f: np.random.rand() for f in feature_names}  # exemplo random
    drivers = gerar_drivers_principais(df, dict(zip(feature_names, data['features'])), importance_dict)

    salvar_previsao_banco(dict(zip(feature_names, data['features'])), pred)

    # ==== HISTÓRICO PARA O GRÁFICO COM PREVISÕES ====
    # Histórico real
    historico_labels = df_hist.apply(lambda row: f"{int(row['ano'])}-{int(row['mes']):02d}", axis=1).tolist()
    historico_valores = df_hist['letalidade_violenta'].tolist()

    # Dados previstos do banco
    import psycopg2
    conn = psycopg2.connect(
        dbname="crimes_RJ", user="postgres", password="crimes",
        host="localhost", port="5432"
    )
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ano, mes, SUM(letalidade_violenta) 
        FROM crimes_RJ.dados_previstos 
        GROUP BY ano, mes 
        ORDER BY ano, mes
    """)
    prev_data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    prev_labels = [f"{row[0]}-{row[1]:02d}" for row in prev_data]
    prev_valores = [row[2] for row in prev_data]

    # ===============================
    # Intervalos 95% alinhados para gráfico de linha
    # ===============================
    interval_95_lower = []
    interval_95_upper = []

    for label, val in zip(prev_labels, prev_valores):
        ano_val, mes_val = map(int, label.split('-'))
        std_dev = df_hist.loc[(df_hist['ano']==ano_val) & (df_hist['mes']==mes_val), 'letalidade_violenta'].std()
        if np.isnan(std_dev) or std_dev == 0:
            std_dev = 1  # fallback
        interval_95_lower.append(max(val - 1.96*std_dev, 0))
        interval_95_upper.append(val + 1.96*std_dev)

    # Adiciona a previsão do próximo mês
    std_dev_prev = df_hist['letalidade_violenta'].tail(3).std() if len(df_hist) >= 3 else 1
    interval_95_lower.append(max(pred - 1.96*std_dev_prev, 0))
    interval_95_upper.append(pred + 1.96*std_dev_prev)

    return jsonify({
        "success": True,
        "previsao_leitura": pred,
        "intervalo_95": [lower, upper],
        "tendencia": tendencia,
        "risco": risco,
        "drivers": drivers,
        'feature_importance': {k: float(v) for k, v in dict(zip(feature_names, importance)).items()},
        "historico_labels": historico_labels,
        "historico_valores": historico_valores,
        "prev_labels": prev_labels,
        "prev_valores": prev_valores,
        "interval_95_lower": interval_95_lower,
        "interval_95_upper": interval_95_upper
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