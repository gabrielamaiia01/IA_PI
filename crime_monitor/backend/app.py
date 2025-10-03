from flask import Flask, render_template, jsonify, request
import pandas as pd
import os
import geopandas as gpd
import matplotlib.pyplot as plt

app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/pages')

DATA_PATH = 'backend/data/BaseDPEvolucaoMensalCisp.csv'

import psycopg2

def load_data():
    
    try:
        conn = psycopg2.connect(
            dbname="crimes_RJ",
            user="postgres",
            password="crimes",
            host="localhost",
            port="5432"
        )
        query = "SELECT * FROM crimes_RJ.dados_reais;"  # Ou outra tabela que quiser
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        print("Erro ao conectar ao banco:", e)
        return pd.DataFrame()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/previsao')
def previsao():
    return render_template('previsao.html')

@app.route('/api/dashboard_data')
def dashboard_data():
    df = load_data()
    if df.empty:
        return jsonify({"error": "No data available"}), 404

    # KPIs
    df_grouped = df.groupby(["ano", "mes"]).agg({
        "letalidade_violenta": "sum",
        "tentat_hom": "sum",
        "estupro": "sum",
        "lesao_corp_culposa": "sum",
        "estelionato": "sum",
        "apreensao_drogas": "sum",
        "trafico_drogas": "sum",
        "apf": "sum",
        "pessoas_desaparecidas": "sum",
        "encontro_cadaver": "sum",
        "registro_ocorrencias": "sum"
    }).reset_index()

    latest_data = df.iloc[-1]

    # Evolução temporal
    df_grouped["Periodo"] = df_grouped["ano"].astype(str) + "-" + df_grouped["mes"].astype(str).str.zfill(2)
    evolucao_temporal = df_grouped[["Periodo", "letalidade_violenta"]].rename(
        columns={"Periodo": "x", "letalidade_violenta": "y"}
    ).to_dict(orient="records")

    # Correlação
    colunas_corr = ["tentat_hom", "lesao_corp_culposa", "estupro",
                    "lesao_corp_culposa", "estelionato", "apreensao_drogas", 
                    "trafico_drogas", "apf", "pessoas_desaparecidas", 
                    "encontro_cadaver", "registro_ocorrencias"]
    correlacao = df_grouped[["letalidade_violenta"] + colunas_corr].corr()
    correlacao_dict = correlacao["letalidade_violenta"].drop("letalidade_violenta").to_dict()

    # Scatter
    if "roubo_rua" in df.columns:
        scatter_data = df[["roubo_rua", "letalidade_violenta"]].dropna().to_dict(orient="records")
        scatter_data = [{"x": row["roubo_rua"], "y": row["letalidade_violenta"]} for row in scatter_data]
    else:
        scatter_data = []

    return jsonify({
        "evolucao_temporal": evolucao_temporal,
        "correlacao_crimes": correlacao_dict,
        "scatter_data": scatter_data
    })

@app.route('/api/previsao_data')
def previsao_data():
    return jsonify({
        "previsao_proxima_leitura": 1190,
        "intervalo_95": "1.120 - 1.260",
        "tendencia": "Leve queda",
        "detalhes_previsao": "Com base em séries temporais e correlações. Drivers principais: queda de roubos de rua (-4%), sazonalidade pós-feriado, operações policiais estáveis."
    })

# Shapefiles
SHAPEFILES = {
    "mcirc": "backend/data/RJ_Municipios_2024.shp",
    "cisp": "backend/data/lm_cisp_bd.shp",
    "aisp": "backend/data/lm_aisp_072024.shp",
    "risp": "backend/data/Limite_RISP_WGS.shp"
}
MAP_FOLDER = os.path.join(app.static_folder, "img")
os.makedirs(MAP_FOLDER, exist_ok=True)

# Colunas de cada shapefile
COLUMN_MAPPING = {
    "mcirc": "CD_MUN",   # municípios
    "cisp": "cisp",
    "aisp": "aisp",
    "risp": "risp"
}

@app.route("/api/map_image/<group_by>")
def map_image(group_by):
    df = load_data()
    if df.empty:
        return jsonify({"error": "No data available"}), 404

    shapefile = SHAPEFILES.get(group_by)
    if not shapefile:
        return jsonify({"error": "Agrupamento inválido"}), 400

    shapefile_col = COLUMN_MAPPING.get(group_by)
    if shapefile_col is None:
        return jsonify({"error": f"Não há coluna configurada para {group_by}"}), 400

    gdf = gpd.read_file(shapefile)

    if group_by not in df.columns:
        return jsonify({"error": f"Coluna {group_by} não encontrada no dataset"}), 400

    # Agrupar CSV
    df_grouped = df.groupby(group_by)["letalidade_violenta"].sum().reset_index()

    # Padronizar tipos
    df_grouped[group_by] = df_grouped[group_by].astype(int)
    gdf[shapefile_col] = gdf[shapefile_col].astype(int)

    # Merge
    gdf = gdf.merge(df_grouped, left_on=shapefile_col, right_on=group_by, how="left")

    # Salvar imagem
    map_path = os.path.join(MAP_FOLDER, f"{group_by}.png")
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    gdf.plot(column="letalidade_violenta", cmap="Reds", legend=True, ax=ax,
             edgecolor="black", linewidth=0.5)
    ax.axis("off")
    plt.savefig(map_path, bbox_inches="tight")
    plt.close(fig)

    return jsonify({"image_url": f"/static/img/{group_by}.png"})

if __name__ == '__main__':
    app.run(debug=True)
