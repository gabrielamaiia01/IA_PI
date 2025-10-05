from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
import numpy as np
from flask import Flask, jsonify, request
import pandas as pd
import numpy as np
import os

app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/pages')

DATA_PATH = 'backend/data/BaseDPEvolucaoMensalCisp.csv'

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

def load_data():
    df = pd.read_csv(DATA_PATH, sep=";", encoding="latin1")
    return df

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
# Dashboard
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
        homicidios_dolosos_pct = ((homicidios_dolosos - hom_prev)/hom_prev*100) if hom_prev>0 else None

    ano_atual, mes_atual = latest_row["ano"], latest_row["mes"]
    latro_ano_ant = df_grouped[(df_grouped["ano"]==ano_atual-1)&(df_grouped["mes"]==mes_atual)]
    variacao_latrocinio_anual = None
    if not latro_ano_ant.empty:
        lat_ant = latro_ano_ant.iloc[0]["latrocinio"]
        variacao_latrocinio_anual = ((latrocinios - lat_ant)/lat_ant*100) if lat_ant>0 else None

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

    col_corr = ["tentat_hom", "lesao_corp_culposa", "estupro", "estelionato", 
                "apreensao_drogas","trafico_drogas","apf","pessoas_desaparecidas",
                "encontro_cadaver","registro_ocorrencias"]
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
# Municípios
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
# Mapa geográfico
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

    # Junta dados e gera mapa
    df_grouped = df.groupby(group_by)["letalidade_violenta"].sum().reset_index()
    df_grouped[group_by] = df_grouped[group_by].astype(str)
    gdf[shapefile_col] = gdf[shapefile_col].astype(str)
    gdf = gdf.merge(df_grouped, left_on=shapefile_col, right_on=group_by, how="left")
    gdf["letalidade_violenta"] = gdf["letalidade_violenta"].fillna(0)

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    gdf.plot(column="letalidade_violenta", cmap="YlOrRd", linewidth=0.8, ax=ax, edgecolor='0.8', legend=True)
    ax.set_axis_off()
    plt.title("Letalidade Violenta", fontsize=15)

    params_str = f"{group_by}_{inicio}_{fim}_{municipio}".replace(" ", "_").replace(":", "_")
    image_name = f"{params_str}.png"
    image_path = os.path.join(MAP_FOLDER, image_name)
    plt.savefig(image_path, bbox_inches='tight', dpi=150)
    plt.close(fig)

    return jsonify({"image_url": f"/static/img/{image_name}"})

# ===========================
# Agrupamentos (KMeans)
# ===========================
@app.route("/api/agrupamentos_data")
def agrupamentos_data():
    df = load_data()
    k = int(request.args.get("k", 4))
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    municipio = request.args.get("municipio")

    # ===============================
    # 🔹 Filtragem por data e município
    # ===============================
    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")

    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]
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

    # ===============================
    # 🔹 Seleção de colunas numéricas
    # ===============================
    dados_cluster = df.select_dtypes(include=[np.number]).drop(columns=[
        'hom_doloso','lesao_corp_morte','latrocinio','cvli','hom_por_interv_policial',
        'ameaca','total_roubos','recuperacao_veiculos','fase','encontro_ossada',
        'furto_bicicleta','sequestro','lesao_corp_dolosa','roubo_conducao_saque',
        'sequestro_relampago','roubo_banco','roubo_bicicleta','roubo_residencia',
        'furto_coletivo','posse_drogas','roubo_comercio','extorsao','roubo_cx_eletronico',
        'roubo_apos_saque','pol_civis_mortos_serv','hom_culposo','furto_celular',
        'furto_transeunte','cmba','mes','pol_militares_mortos_serv','total_furtos',
        'aaapai','furto_veiculos','roubo_transeunte','cmp','risp','roubo_celular',
        'outros_furtos','roubo_rua','apreensao_drogas_sem_autor','roubo_em_coletivo',
        'outros_roubos','roubo_carga'
    ], errors='ignore')

    if dados_cluster.empty:
        return jsonify({"error": "Sem dados numéricos para agrupar."}), 400

    # ===============================
    # 🔹 Imputação e normalização
    # ===============================
    colunas = dados_cluster.columns
    imputer = SimpleImputer(strategy="mean")
    dados_imp = pd.DataFrame(imputer.fit_transform(dados_cluster), columns=colunas)
    scaler = StandardScaler()
    dados_scaled = scaler.fit_transform(dados_imp)

    # ===============================
    # 🔹 KMeans clustering
    # ===============================
    kmeans = KMeans(n_clusters=k, random_state=42)
    clusters = kmeans.fit_predict(dados_scaled)
    df['cluster'] = clusters
    media_clusters = df.groupby('cluster')[colunas].mean().round(2).to_dict(orient="index")

    # ===============================
    # 🔹 PCA 2D
    # ===============================
    pca = PCA(n_components=2)
    pca_result = pca.fit_transform(dados_scaled)
    pca_df = pd.DataFrame(pca_result, columns=["pca1", "pca2"])
    pca_df["cluster"] = clusters
    pca_data = pca_df.to_dict(orient="records")

    # ===============================
    # 🔹 Perfil médio dos clusters
    # ===============================
    df_cluster_profile = df.groupby("cluster")[colunas].mean()

    # Remove colunas geográficas (se existirem)
    for col_geo in ["cisp", "aisp", "risp", "mcirc"]:
        if col_geo in df_cluster_profile.columns:
            df_cluster_profile = df_cluster_profile.drop(columns=[col_geo])

    # Normaliza para visualização
    df_norm = (df_cluster_profile - df_cluster_profile.min()) / (df_cluster_profile.max() - df_cluster_profile.min())

    perfil_img_path = os.path.join(MAP_FOLDER, f"perfil_medio_{k}.png")
    fig1, ax1 = plt.subplots(figsize=(12,6))
    df_norm.plot(kind="bar", ax=ax1)
    ax1.set_title("Perfil médio dos clusters (valores normalizados)")
    ax1.set_ylabel("Intensidade relativa")
    ax1.set_xticklabels([f"Cluster {i}" for i in df_norm.index], rotation=0)
    plt.tight_layout()
    fig1.savefig(perfil_img_path, dpi=150)
    plt.close(fig1)

    # ===============================
    # 🔹 Método do cotovelo
    # ===============================
    inertia = []
    K_range = range(2, 10)
    for k_elbow in K_range:
        kmeans_elbow = KMeans(n_clusters=k_elbow, random_state=42)
        kmeans_elbow.fit(dados_scaled)
        inertia.append(kmeans_elbow.inertia_)

    cotovelo_img_path = os.path.join(MAP_FOLDER, f"cotovelo_{k}.png")
    fig2, ax2 = plt.subplots(figsize=(8,5))
    ax2.plot(K_range, inertia, 'bo-')
    ax2.set_xlabel("Número de Clusters")
    ax2.set_ylabel("Inertia")
    ax2.set_title("Método do Cotovelo")
    plt.tight_layout()
    fig2.savefig(cotovelo_img_path, dpi=150)
    plt.close(fig2)

    # ===============================
    # 🔹 Retorno JSON final
    # ===============================
    return jsonify({
        "media_clusters": media_clusters,
        "pca_data": pca_data,
        "explained_variance": [round(v, 3) for v in pca.explained_variance_ratio_],
        "perfil_medio_img": f"/static/img/perfil_medio_{k}.png",
        "cotovelo_img": f"/static/img/cotovelo_{k}.png"
    })

if __name__ == "__main__":
    app.run(debug=True)
