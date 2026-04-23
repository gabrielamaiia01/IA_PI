from flask import Flask, render_template, jsonify, request, send_file, session, flash, redirect, url_for
import random
import string
import pandas as pd
import numpy as np
import os
import geopandas as gpd
import warnings
from shapely import speedups
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.decomposition import PCA
import pickle
import psycopg2
from dotenv import load_dotenv
import random
import colorsys
# -*- coding: utf-8 -*-
import io 
import tempfile
import requests
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                PageBreak, Table, TableStyle)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

import json

from mlxtend.frequent_patterns import apriori, association_rules

import re
import os
import sys
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
# adiciona o diretório raiz ao path para resolver imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if os.getenv("RENDER") == "true":
    from backend.db import get_connection
else:
    from db import get_connection

from functools import wraps
import shutil  # Para limpar arquivos temporários
import time    # Para time.sleep em gerar_texto_gpt4o
from datetime import datetime
from captcha.image import ImageCaptcha
import shap

import networkx as nx

# ===========================
# Variáveis globais de estado
# ===========================
map_data = {}
mapa_clusters_data = {}
payload_dashboard = {}
payload_agrupamentos = {}
kmeans = None
df_clusters_global = None
dados_scaled_global = None
dados_cluster_global = None

# ===========================
# Decorator de Autenticação
# ===========================
def login_required(f):
    """
    Decorator para proteger rotas que exigem autenticação.
    Redireciona para login se o usuário não estiver autenticado.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Você precisa fazer login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

warnings.filterwarnings("ignore")

if speedups.available:
    speedups.enable()

# === 1. Carregar variáveis do arquivo .env ===
load_dotenv()
app = Flask(
    __name__,
    static_folder='../frontend/static',
    template_folder='../frontend/pages'
)

app.secret_key = os.getenv("FLASK_SECRET_KEY")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
OPENROUTER_API_KEY= os.getenv("OPENROUTER_API_KEY")
IP_OR_HOST= os.getenv("IP_OR_HOST")
DATABASE_URL = os.getenv("DATABASE_URL")

# ===========================
# Paths e configurações
# ===========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f"Base directory: {BASE_DIR}")
DATA_PATH = os.path.join(BASE_DIR, 'data', 'BaseDPEvolucaoMensalCisp.csv')
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'model.pkl')

SHAPEFILES = {
    "mcirc": os.path.join(BASE_DIR, 'data', 'RJ_Municipios_2024.shp'),
    "cisp": os.path.join(BASE_DIR, 'data', 'lm_cisp_bd.shp'),
    "aisp": os.path.join(BASE_DIR, 'data', 'lm_aisp_072024.shp'),
    "risp": os.path.join(BASE_DIR, 'data', 'Limite_RISP_WGS.shp')
}

SHAPEFILES_GPKG = {
    "cisp": "lm_cisp_bd.gpkg",
    "aisp": "lm_aisp_bd.gpkg",
    "risp": "lm_risp_bd.gpkg",
    "mcirc": "lm_municipio_bd.gpkg"
}

MAP_FOLDER = os.path.join(app.static_folder, "img")
os.makedirs(MAP_FOLDER, exist_ok=True)

COLUMN_MAPPING = {
    "mcirc": "CD_MUN",
    "cisp": "cisp",
    "aisp": "aisp",
    "risp": "risp"
}

for key, shp_path in SHAPEFILES.items():
    if not os.path.exists(SHAPEFILES_GPKG[key]):
        print(f"Gerando {SHAPEFILES_GPKG[key]} a partir de {shp_path}...")
        gdf = gpd.read_file(shp_path)
        gdf.to_file(SHAPEFILES_GPKG[key], layer=key, driver="GPKG")
    else:
        print(f"{SHAPEFILES_GPKG[key]} já existe. Pulando...")

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

def gerar_drivers_principais(modelo, df, features_dict, n_drivers=3):
    """
    Identifica as variáveis que mais influenciaram a MUDANÇA da previsão
    entre o mês atual e o mês anterior usando delta-SHAP.
    """
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame([df])

    for col in ['mes', 'ano']:
        if col not in df.columns:
            raise ValueError(f"Coluna '{col}' não encontrada no DataFrame.")

    df['mes'] = df['mes'].astype(int)
    df['ano'] = df['ano'].astype(int)

    X_current = pd.DataFrame([features_dict])
    mes = int(features_dict['mes'])
    ano = int(features_dict['ano'])

    mes_ant = mes - 1
    ano_ant = ano
    if mes_ant == 0:
        mes_ant = 12
        ano_ant -= 1

    X_prev = df[(df['mes'] == mes_ant) & (df['ano'] == ano_ant)].copy()

    if X_prev.empty:
        X_prev = df[df['ano'] <= ano].sort_values(['ano', 'mes']).tail(1)

    X_prev_numeric = X_prev.select_dtypes(include=['number'])
    X_prev_mean = X_prev_numeric.mean().to_frame().T
    X_prev_mean = X_prev_mean.reindex(columns=X_current.columns, fill_value=0)

    explainer = shap.Explainer(modelo, X_prev_mean)
    shap_current = explainer(X_current)
    shap_prev = explainer(X_prev_mean)

    sh_current = shap_current.values[0]
    sh_prev = shap_prev.values[0]

    delta_shap = {}
    for i, feature in enumerate(X_current.columns):
        if feature in ['mes', 'ano', 'cisp']:
            continue
        delta_shap[feature] = abs(sh_current[i] - sh_prev[i])

    top = sorted(delta_shap.items(), key=lambda x: x[1], reverse=True)[:n_drivers]

    drivers = []
    for feature, score in top:
        old = X_prev_mean[feature].iloc[0]
        new = X_current[feature].iloc[0]

        if old == 0:
            change_pct = 0
        else:
            change_pct = ((new - old) / old) * 100

        fname = feature.replace("_", " ")

        if change_pct > 3:
            desc = f"aumento de {fname} (+{round(change_pct)}%)"
        elif change_pct < -3:
            desc = f"queda de {fname} ({round(change_pct)}%)"
        else:
            desc = f"{fname} estável"

        drivers.append(desc)

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

    if not DATABASE_URL and not all([DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT]):
        print("Configurações de banco ausentes — pulando salvamento no banco.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO dados_previstos
            (cisp, mcirc, mes, ano, letalidade_violenta, tentat_hom, estupro,
             lesao_corp_culposa, roubo_veiculo, estelionato, apreensao_drogas,
             trafico_drogas, apf, pessoas_desaparecidas, encontro_cadaver,
             registro_ocorrencias)
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

def generate_distinct_colors(k, fixed_colors=None):
    """
    Gera k cores distintas, evitando colisão com uma lista de cores fixas.
    """
    if fixed_colors is None:
        fixed_colors = []

    print(f"Fixed colors: {fixed_colors}")
    fixed_rgb = [mcolors.to_rgb(c) for c in fixed_colors.values()]

    colors_list = []
    attempt = 0
    while len(colors_list) < k and attempt < k * 10:
        h = random.random()
        s = 0.7 + 0.3 * random.random()
        v = 0.8 + 0.2 * random.random()
        rgb = colorsys.hsv_to_rgb(h, s, v)

        def is_distinct(rgb_new):
            threshold = 0.3
            for r in fixed_rgb + [mcolors.to_rgb(c) for c in colors_list]:
                dist = sum((a - b) ** 2 for a, b in zip(rgb_new, r)) ** 0.5
                if dist < threshold:
                    return False
            return True

        if is_distinct(rgb):
            colors_list.append('#{:02x}{:02x}{:02x}'.format(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)))

        attempt += 1

    while len(colors_list) < k:
        colors_list.append('#{:06x}'.format(random.randint(0, 0xFFFFFF)))

    return colors_list


def gerar_texto_gpt4o(prompt, max_tokens=800, temperature=0.7, retries=2, wait=3):
    """
    Gera texto com o modelo GPT 4o (openai/gpt-4o-mini) via OpenRouter.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    }
    data = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    for attempt in range(retries + 1):
        try:
            resp = requests.post(url, json=data, headers=headers, timeout=60)
            resp.raise_for_status()
            resposta = resp.json()
            texto = resposta["choices"][0]["message"]["content"]
            return texto.strip()
        except requests.exceptions.RequestException as e:
            print(f"[ERRO GPT4O] Tentativa {attempt+1} de {retries+1}: {e}")
            if attempt < retries:
                time.sleep(wait)
            else:
                return "Não foi possível gerar análise automática no momento. Consulte os gráficos."
        except Exception as e:
            print(f"[ERRO GPT4O] Problema ao processar resposta: {e}")
            return "Não foi possível gerar análise automática no momento. Consulte os gráficos."

            
# =========================
# FUNÇÃO DE ANÁLISES
# =========================
def gerar_descricoes_dashboard(payload, group_by):
    """
    Gera descrições automáticas para os gráficos do dashboard.
    """
    descricoes = {
        "linha_evolucao": "Análise não disponível.",
        "barras_correlacao": "Análise não disponível.",
        "scatter": "Análise não disponível.",
        "mapa": "Análise não disponível."
    }

    # ================== EVOLUÇÃO TEMPORAL ==================
    evo = payload.get("evolucao_temporal", [])
    if evo:
        xs = [r.get("x", "") for r in evo]
        ys = [r.get("y", 0) for r in evo if isinstance(r.get("y"), (int, float))]
        if len(ys) > 2:
            coef = float(np.polyfit(range(len(ys)), ys, 1)[0])
            media = float(np.mean(ys))
            pico = xs[int(np.argmax(ys))] if xs else "N/A"
            vale = xs[int(np.argmin(ys))] if xs else "N/A"
            resumo_evo = f"Tendência linear {coef:.2f}, média {media:.2f}, pico em {pico}, mínimo em {vale}."
        else:
            resumo_evo = "Dados insuficientes para análise temporal."
    else:
        resumo_evo = "Sem dados de evolução temporal."

    prompt_evo = f"""
Você é um analista de segurança pública.
Analise os seguintes dados de evolução temporal e produza uma resposta curta (2-3 frases) em português:

[EVOLUÇÃO TEMPORAL]
{resumo_evo}
"""
    descricoes["linha_evolucao"] = gerar_texto_gpt4o(prompt_evo)

    # ================== CORRELAÇÃO ENTRE CRIMES ==================
    corr = payload.get("correlacao_crimes", {})
    resumo_corr = f"Correlação entre crimes: { {k:v for k,v in corr.items() if v is not None and not np.isnan(v)} }" if corr else "Sem dados de correlação."
    prompt_corr = f"""
Você é um analista de segurança pública.
Analise os seguintes dados de correlação entre a variável letalidade e os crimes e produza uma resposta curta (2-3 frases) em português:

[CORRELAÇÃO ENTRE CRIMES]
{resumo_corr}
"""
    descricoes["barras_correlacao"] = gerar_texto_gpt4o(prompt_corr)

    # ================== SCATTER ==================
    scatter = payload.get("scatter_data", [])
    if scatter:
        xs_s = [p.get("x", 0) for p in scatter]
        ys_s = [p.get("y", 0) for p in scatter]
        if len(xs_s) > 2 and len(ys_s) > 2:
            corrcoef = float(np.corrcoef(xs_s, ys_s)[0, 1])
            resumo_scatter = f"Correlação de Pearson: {corrcoef:.2f}"
        else:
            resumo_scatter = "Dados insuficientes para dispersão."
    else:
        resumo_scatter = "Sem dados de dispersão."

    prompt_scatter = f"""
Você é um analista de segurança pública.
Analise os dados de dispersão e produza uma resposta curta (2-3 frases) em português:

[DISPERSÃO ROUBO x LETALIDADE]
{resumo_scatter}
"""
    descricoes["scatter"] = gerar_texto_gpt4o(prompt_scatter)

    # ================== MAPA TEMÁTICO ==================
    group_label = {
        "mcirc": "município",
        "cisp": "CISP",
        "aisp": "AISP",
        "risp": "RISP"
    }.get(group_by, "agrupamento")

    # Usa map_data do payload ou da variável global
    md = payload.get("map_data") or map_data

    if md and md.get("data"):
        texto_map = f"Letalidade violenta por {group_label}:\n" + "\n".join([
            f"• {item.get('NM_MUN', item.get(group_by, 'Desconhecido'))} "
            f"({item.get('CD_MUN', '-')}) — {int(item.get('letalidade_violenta', 0))}"
            for item in md["data"]
            if item.get('letalidade_violenta', 0) > 0
        ])
        resumo_mapa = texto_map.strip() or f"Nenhuma letalidade registrada por {group_label}."
    else:
        resumo_mapa = f"Dados de mapa por {group_label} não disponíveis."

    prompt_mapa = f"""
Você é um analista de segurança pública.
Analise os dados do mapa temático e produza uma resposta curta (2-3 frases) em português:

[MAPA TEMÁTICO]
{resumo_mapa}
"""
    print(prompt_mapa)
    descricoes["mapa"] = gerar_texto_gpt4o(prompt_mapa)

    return descricoes

# =========================
# FUNÇÃO PARA CRIAR GRÁFICOS
# =========================
def criar_graficos_temp_dashboard(payload, tmp_dir, group_by): 
    saved = {}

    # ===============================
    # Linha de evolução
    # ===============================
    evo = payload.get("evolucao_temporal", [])
    if evo:
        xs = [r["x"] for r in evo]
        ys = [r["y"] for r in evo]

        xs_fmt = []
        for s in xs:
            try:
                dt = pd.to_datetime(s)
                xs_fmt.append(dt.strftime("%b/%y"))
            except:
                xs_fmt.append(s)

        plt.figure(figsize=(8,4))
        plt.plot(xs_fmt, ys, marker='o', linewidth=2)
        plt.title("Evolução temporal da Letalidade Violenta")
        plt.xlabel("Período")
        plt.ylabel("Letalidade Violenta")

        step = max(1, len(xs_fmt) // 10)
        plt.xticks(ticks=range(0, len(xs_fmt), step), 
                   labels=[xs_fmt[i] for i in range(0, len(xs_fmt), step)], rotation=45)
        plt.grid(True, linestyle='--', alpha=0.6)

        caminho = os.path.join(tmp_dir, "linha_evolucao.png")
        plt.tight_layout()
        plt.savefig(caminho)
        plt.close()
        saved["linha_evolucao"] = caminho

    # ===============================
    # Correlação
    # ===============================
    corr = payload.get("correlacao_crimes", {})
    if corr:
        keys = list(corr.keys())
        vals = [corr[k] for k in keys]
        plt.figure(figsize=(8,4))
        plt.bar(range(len(vals)), vals)
        plt.xticks(range(len(vals)), [k.replace("_"," ") for k in keys], rotation=45)
        plt.ylim(-1,1)
        plt.title("Correlação com Letalidade Violenta")
        plt.grid(axis='y', linestyle='--', alpha=0.6)
        caminho = os.path.join(tmp_dir, "barras_correlacao.png")
        plt.tight_layout()
        plt.savefig(caminho)
        plt.close()
        saved["barras_correlacao"] = caminho

    # ===============================
    # Dispersão
    # ===============================
    scatter = payload.get("scatter_data", [])
    if scatter:
        xs = [p["x"] for p in scatter]
        ys = [p["y"] for p in scatter]
        plt.figure(figsize=(6,6))
        plt.scatter(xs, ys)
        plt.title("Roubo na rua x Letalidade Violenta")
        plt.xlabel("Roubo na rua")
        plt.ylabel("Letalidade Violenta")
        plt.grid(True, linestyle='--', alpha=0.6)
        caminho = os.path.join(tmp_dir, "scatter.png")
        plt.tight_layout()
        plt.savefig(caminho)
        plt.close()
        saved["scatter"] = caminho

    # ===============================
    # Mapa — usa map_data do payload ou global
    # ===============================
    try:
        md = payload.get("map_data") or map_data
        if md and md.get("geojson"):
            # Gerar imagem do mapa usando geopandas e matplotlib
            geojson_str = md.get("geojson")

            if isinstance(geojson_str, str):
                geojson_data = json.loads(geojson_str)
            else:
                geojson_data = geojson_str  # segurança extra

            gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
            coluna = md.get("coluna", "letalidade_violenta")
            if coluna in gdf.columns and not gdf.empty:
                fig, ax = plt.subplots(1, 1, figsize=(10, 8))
                gdf.plot(column=coluna, ax=ax, legend=True, cmap='Reds', edgecolor='black', linewidth=0.5)
                ax.set_title(f"Distribuição Geográfica da {coluna.replace('_', ' ').title()}")
                ax.set_axis_off()  # Remove os eixos para um mapa limpo
                caminho = os.path.join(tmp_dir, "mapa.png")
                plt.savefig(caminho, dpi=150, bbox_inches='tight')
                plt.close(fig)
                saved["mapa"] = caminho
            else:
                print("[AVISO] Dados insuficientes para gerar mapa no PDF — coluna não encontrada ou GDF vazio.")
        else:
            print("[AVISO] map_data não disponível ou sem geojson — mapa ignorado no PDF.")
    except Exception as e:
        print(f"[ERRO mapa]: {e}")
        import traceback
        traceback.print_exc()

    return saved

def gerar_descricoes_agrupamentos(payload, group_by):
    """
    Gera descrições automáticas para os gráficos de agrupamentos.
    """
    descricoes = {
        "scatter_pca": "Análise não disponível.",
        "perfil_medio_clusters": "Análise não disponível.",
        "importancia_variaveis": "Análise não disponível.",
        "mapa_clusters": "Análise não disponível."
    }

    try:
        # =====================
        # SCATTER PCA
        # =====================
        pca_data = payload.get("pca_data", [])
        resumo_scatter = "Sem dados de PCA para dispersão."
        if pca_data and len(pca_data) > 1:
            xs = [p.get("pca1", 0) for p in pca_data]
            ys = [p.get("pca2", 0) for p in pca_data]
            clusters = [p.get("cluster", 0) for p in pca_data]
            if len(xs) > 2 and len(ys) > 2:
                corrcoef = float(np.corrcoef(xs, ys)[0, 1])
                resumo_scatter = f"Correlação PCA1 x PCA2: {corrcoef:.2f}. Total de clusters: {len(set(clusters))}."

        prompt_scatter = f"""
Você é um analista de segurança pública.
Analise os seguintes dados de PCA e produza uma resposta curta (2-3 frases) em português:

[DISPERSÃO PCA]
{resumo_scatter}
"""
        descricoes["scatter_pca"] = gerar_texto_gpt4o(prompt_scatter)

        # =====================
        # PERFIL MÉDIO DOS CLUSTERS
        # =====================
        perfil_medio_data = payload.get("perfil_medio_data", {})
        resumo_perfil = "Sem dados de perfil médio dos clusters."
        if perfil_medio_data:
            resumo_perfil = ""
            for cluster, medias in perfil_medio_data.items():
                resumo_perfil += f"Cluster {cluster}: " + ", ".join([f"{k}={v}" for k, v in medias.items()]) + "; "
            resumo_perfil = resumo_perfil.strip()

        prompt_perfil = f"""
Você é um analista de segurança pública.
Analise os dados de perfil médio dos clusters e produza uma resposta curta (2-3 frases) em português:

[PERFIL MÉDIO DOS CLUSTERS]
{resumo_perfil}
"""
        descricoes["perfil_medio_clusters"] = gerar_texto_gpt4o(prompt_perfil)

        # =====================
        # IMPORTÂNCIA DAS VARIÁVEIS
        # =====================
        importancias = payload.get("importancias", {})
        resumo_importancias = "Sem dados de importâncias."
        if importancias:
            top_vars = sorted(importancias.items(), key=lambda x: x[1], reverse=True)[:5]
            resumo_importancias = ", ".join([f"{k} ({v:.2f})" for k, v in top_vars])

        prompt_importancia = f"""
Você é um analista de segurança pública.
Analise as importâncias das variáveis e produza uma resposta curta (2-3 frases) em português:

[IMPORTÂNCIA DAS VARIÁVEIS]
{resumo_importancias}
"""
        descricoes["importancia_variaveis"] = gerar_texto_gpt4o(prompt_importancia)

        # =====================
        # MAPA DOS CLUSTERS — usa mapa_clusters_data global
        # =====================
        mc = payload.get("mapa_clusters_data") or mapa_clusters_data

        resumo_mapa = "Dados de mapa não disponíveis."
        try:
            if mc.get("data"):
                resumo_mapa = ""
                shapefile_col = [c for c in mc["data"][0].keys() if c != "cluster"][0]
                for item in mc["data"]:
                    regiao = item.get(shapefile_col, "N/A")
                    valor = item.get("cluster", -1)
                    resumo_mapa += f"{regiao}: cluster {valor}; "
                resumo_mapa = resumo_mapa.strip()
        except Exception as e:
            print(f"[Erro mapa_clusters] {e}")

        prompt_mapa = f"""
Você é um analista de segurança pública.
Analise os dados do mapa dos clusters e produza uma resposta curta (2-3 frases) em português:

[MAPA DOS CLUSTERS]
{resumo_mapa}
"""
        descricoes["mapa_clusters"] = gerar_texto_gpt4o(prompt_mapa)

        return descricoes

    except Exception as e:
        print(f"Erro geral ao gerar descrições de agrupamentos: {e}")
        return {
            "scatter_pca": "Erro",
            "perfil_medio_clusters": "Erro",
            "importancia_variaveis": "Erro",
            "mapa_clusters": "Erro"
        }

def criar_graficos_temp_agrupamentos(payload, tmp_dir, group_by):
    saved = {}

    # ===============================
    # Scatter PCA com cores por cluster
    # ===============================
    pca_data = payload.get("pca_data", [])
    if pca_data:
        xs = [p.get("pca1", 0) for p in pca_data]
        ys = [p.get("pca2", 0) for p in pca_data]
        clusters = [p.get("cluster", 0) for p in pca_data]

        plt.figure(figsize=(6,6))
        scatter = plt.scatter(xs, ys, c=clusters, cmap='tab10', alpha=0.7)
        plt.title("Projeção PCA dos Clusters")
        plt.xlabel("Componente Principal 1")
        plt.ylabel("Componente Principal 2")
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.legend(*scatter.legend_elements(), title="Clusters")
        caminho = os.path.join(tmp_dir, "scatter_pca.png")
        plt.tight_layout()
        plt.savefig(caminho)
        plt.close()
        saved["scatter_pca"] = caminho

    # ===============================
    # Perfil médio dos clusters
    # ===============================
    perfil_medio_data = payload.get("perfil_medio_data", {})
    if perfil_medio_data:
        df_perfil = pd.DataFrame(perfil_medio_data).T
        plt.figure(figsize=(12,6))
        df_perfil.plot(kind="bar")
        plt.title("Perfil Médio dos Clusters")
        plt.ylabel("Intensidade relativa")
        plt.xlabel("Cluster")
        plt.xticks(rotation=0)
        plt.legend(frameon=True, bbox_to_anchor=(1.02,1), loc='upper left')
        plt.tight_layout()
        caminho = os.path.join(tmp_dir, "perfil_medio_clusters.png")
        plt.savefig(caminho, dpi=150, bbox_inches='tight')
        plt.close()
        saved["perfil_medio_clusters"] = caminho

    # ===============================
    # Importância das variáveis
    # ===============================
    importancias = payload.get("importancias", {})
    if importancias:
        importancias_sorted = dict(sorted(importancias.items(), key=lambda x: x[1], reverse=True))
        plt.figure(figsize=(10,6))
        plt.bar(range(len(importancias_sorted)), list(importancias_sorted.values()))
        plt.xticks(range(len(importancias_sorted)), list(importancias_sorted.keys()), rotation=45)
        plt.title("Importância das Variáveis nos Clusters")
        plt.ylabel("Importância relativa")
        plt.tight_layout()
        caminho = os.path.join(tmp_dir, "importancia_variaveis.png")
        plt.savefig(caminho, dpi=150, bbox_inches='tight')
        plt.close()
        saved["importancia_variaveis"] = caminho

    # ===============================
    # Mapa temático dos clusters — usa mapa_clusters_data global
    # ===============================
    try:
        mc = payload.get("mapa_clusters_data") or mapa_clusters_data

        if mc and mc.get("geojson"):
            import json

            geojson_data = mc["geojson"]

            # 🔥 segurança (caso venha string)
            if isinstance(geojson_data, str):
                geojson_data = json.loads(geojson_data)

            gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])

            if not gdf.empty and "cluster" in gdf.columns:
                fig, ax = plt.subplots(1, 1, figsize=(10, 8))

                gdf.plot(
                    column="cluster",
                    ax=ax,
                    cmap="tab10",
                    legend=True,
                    edgecolor="black",
                    linewidth=0.5
                )

                ax.set_title("Distribuição Geográfica dos Clusters")
                ax.set_axis_off()

                caminho = os.path.join(tmp_dir, "mapa_clusters.png")
                plt.savefig(caminho, dpi=150, bbox_inches='tight')
                plt.close(fig)

                saved["mapa_clusters"] = caminho
            else:
                print("[AVISO] GDF vazio ou sem coluna 'cluster'")
        else:
            print("[AVISO] mapa_clusters_data sem geojson")
            
    except Exception as e:
        print(f"[ERRO mapa clusters]: {e}")
    return saved

@app.route('/captcha')
def captcha():
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    session['captcha_text'] = captcha_text

    image = ImageCaptcha()
    data = image.generate(captcha_text)
    return send_file(data, mimetype='image/png')


# ===========================
# Rotas de páginas
# ===========================
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/previsao')
@login_required
def previsao():
    return render_template('previsao.html')

@app.route('/agrupamentos')
@login_required
def agrupamentos():
    return render_template('agrupamentos.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('login'))

# ===========================
# API - Dashboard
# ===========================
@app.route('/api/dashboard_data')
@login_required
def dashboard_data():
    global payload_dashboard

    df = load_data()
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    municipio = request.args.get("municipio")

    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")

    if municipio:
        gdf_mun = gpd.read_file(SHAPEFILES["mcirc"])[["CD_MUN", "NM_MUN"]]
        gdf_mun["CD_MUN"] = gdf_mun["CD_MUN"].astype(str)
        df["mcirc"] = df["mcirc"].astype(str)
        df = df.merge(gdf_mun, left_on="mcirc", right_on="CD_MUN", how="left")
        df = df[df["NM_MUN"] == municipio]

    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]

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
    }).reset_index().sort_values(["ano", "mes"]).reset_index(drop=True)

    letalidade_total = int(df_grouped["letalidade_violenta"].sum())

    homicidios_dolosos = df["hom_doloso"].mean() if not df.empty else 0

    homicidios_dolosos_pct = None
    if inicio:
        inicio_dt = pd.to_datetime(inicio)
        mes_prev = inicio_dt.month - 1
        ano_prev = inicio_dt.year
        if mes_prev == 0:
            mes_prev = 12
            ano_prev -= 1

        df_prev = load_data()
        df_prev["data"] = pd.to_datetime(df_prev["ano"].astype(str) + "-" + df_prev["mes"].astype(str) + "-01")

        if municipio:
            gdf_mun = gpd.read_file(SHAPEFILES["mcirc"])[["CD_MUN", "NM_MUN"]]
            gdf_mun["CD_MUN"] = gdf_mun["CD_MUN"].astype(str)
            df_prev["mcirc"] = df_prev["mcirc"].astype(str)
            df_prev = df_prev.merge(gdf_mun, left_on="mcirc", right_on="CD_MUN", how="left")
            df_prev = df_prev[df_prev["NM_MUN"] == municipio]

        df_grouped_periodo = df.groupby(["ano", "mes"])["hom_doloso"].mean().reset_index()
        homicidios_dolosos = df_grouped_periodo["hom_doloso"].mean()

        df_grouped_prev = df_prev.groupby(["ano", "mes"])["hom_doloso"].mean().reset_index()
        df_mes_prev = df_grouped_prev[(df_grouped_prev["ano"] == ano_prev) & (df_grouped_prev["mes"] == mes_prev)]

        if not df_mes_prev.empty:
            media_prev = df_mes_prev["hom_doloso"].iloc[0]
            if media_prev > 0:
                homicidios_dolosos_pct = ((homicidios_dolosos - media_prev) / media_prev) * 100

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

    df_grouped["Periodo"] = df_grouped["ano"].astype(str) + "-" + df_grouped["mes"].astype(str).str.zfill(2)
    evolucao_temporal = df_grouped[["Periodo", "letalidade_violenta"]].rename(
        columns={"Periodo": "x", "letalidade_violenta": "y"}
    ).to_dict(orient="records")

    col_corr = ["tentat_hom", "lesao_corp_culposa", "estupro", "estelionato",
                "apreensao_drogas", "trafico_drogas", "apf", "pessoas_desaparecidas",
                "encontro_cadaver", "registro_ocorrencias"]
    correlacao_dict = df_grouped[["letalidade_violenta"] + col_corr].corr()["letalidade_violenta"] \
        .drop("letalidade_violenta").to_dict()

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

    if not inicio or pd.to_datetime(inicio) < pd.Timestamp("2003-01-01"):
        homicidios_dolosos_pct = None
        variacao_latrocinio_anual_pct = None

    payload_dashboard = {
        "letalidade_violenta_total": letalidade_total,
        "homicidios_dolosos": round(homicidios_dolosos, 2),
        "homicidios_dolosos_pct": homicidios_dolosos_pct,
        "latrocinios": latrocinios,
        "variacao_latrocinio_anual_pct": variacao_latrocinio_anual_pct,
        "mortes_intervencao_policial": round(mortes_intervencao_policial or 0, 2),
        "tendencia_mortes_intervencao_policial": tendencia_interv,
        "evolucao_temporal": evolucao_temporal,
        "correlacao_crimes": correlacao_dict,
        "scatter_data": scatter_data,
        "map_data": map_data  # inclui map_data atual no payload
    }

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

# Ignorar captcha quando em TEST_MODE
@app.before_request
def desabilitar_captcha_em_teste():
    if os.environ.get("TEST_MODE") == "1":
        session['captcha_text'] = "TESTE"

@app.route('/api/medias')
@login_required
def api_medias():
    df = load_data()
    if df.empty:
        return jsonify({"error": "Nenhum dado disponível"}), 404

    medias = {k: int(round(v)) for k, v in df.mean(numeric_only=True).items()}
    return jsonify(medias)

# ===========================
# API - Municípios
# ===========================
@app.route("/api/municipios")
@login_required
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
@app.route("/api/map_image/<group_by>/<coluna>")
@login_required
def map_image(group_by, coluna="letalidade_violenta"):
    global map_data

    df = load_data()

    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    municipio = request.args.get("municipio")

    COLUNAS_VALIDAS = [
        "letalidade_violenta",
        "hom_doloso", "latrocinio", "hom_por_interv_policial",
        "tentat_hom", "lesao_corp_dolosa", "estupro",
        "lesao_corp_culposa", "roubo_veiculo", "roubo_rua",
        "roubo_comercio", "roubo_residencia", "estelionato",
        "apreensao_drogas", "trafico_drogas", "apf",
        "pessoas_desaparecidas", "encontro_cadaver",
        "registro_ocorrencias", "furto_veiculos"
    ]

    if coluna not in COLUNAS_VALIDAS:
        return jsonify({"error": "Coluna inválida"}), 400

    shapefile = SHAPEFILES.get(group_by)
    if not shapefile:
        return jsonify({"error": "Agrupamento inválido"}), 400

    shapefile_col = COLUMN_MAPPING.get(group_by)

    gdf = gpd.read_file(shapefile)

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    df["data"] = pd.to_datetime(
        df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01"
    )

    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]

    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]

    df_grouped = (
        df.groupby(group_by)[coluna]
        .mean()
        .reset_index()
    )

    df_grouped[coluna] = df_grouped[coluna].round(2)

    df_grouped[group_by] = df_grouped[group_by].astype(str)
    gdf[shapefile_col] = gdf[shapefile_col].astype(str)

    gdf = gdf.merge(
        df_grouped,
        left_on=shapefile_col,
        right_on=group_by,
        how="left"
    )

    gdf[coluna] = gdf[coluna].fillna(0)
    gdf[coluna] = gdf[coluna].astype(float)

    if municipio:
        municipios_gdf = gpd.read_file(SHAPEFILES["mcirc"])

        if municipios_gdf.crs is None:
            municipios_gdf = municipios_gdf.set_crs(epsg=4326)

        municipios_gdf = municipios_gdf.to_crs(gdf.crs)

        municipio_geom = municipios_gdf.loc[
            municipios_gdf["NM_MUN"] == municipio,
            "geometry"
        ]

        if not municipio_geom.empty:
            gdf = gpd.clip(gdf, municipio_geom.iloc[0])
            gdf["NM_MUN"] = municipio
        else:
            return jsonify({"error": "Município não encontrado"}), 404

    if "NM_MUN" in gdf.columns:
        gdf["nome"] = gdf["NM_MUN"]
    else:
        gdf["nome"] = gdf[shapefile_col]

    geojson = gdf.to_json()

    # Extrair dados resumidos para uso no PDF
    cols_para_dados = [shapefile_col, coluna, "nome"]
    if "NM_MUN" in gdf.columns:
        cols_para_dados.append("NM_MUN")
    cols_existentes = [c for c in cols_para_dados if c in gdf.columns]
    dados_resumo = json.loads(gdf[cols_existentes].to_json(orient="records"))

    result = {
        "geojson": geojson,
        "coluna": coluna,
        "data": dados_resumo
    }

    # Salva na variável global para uso no PDF
    map_data = result

    return jsonify(result)

# ===========================
# API - Features do modelo
# ===========================
@app.route('/api/model_features')
@login_required
def model_features():
    return jsonify(feature_names)

# ===========================
# API - Previsão
# ===========================
@app.route('/api/previsao', methods=['POST'])
@login_required
def previsao_api():
    global model
    df = load_data()
    data = request.get_json()

    if not model:
        return jsonify({"error": "Modelo não carregado"}), 500

    X = pd.DataFrame([data['features']], columns=feature_names)
    pred = int(round(model.predict(X)[0]))

    df_hist = df.groupby(['ano', 'mes'])['letalidade_violenta'].sum().reset_index()
    df_hist = df_hist.sort_values(['ano', 'mes'])

    preds_boot = []
    for _ in range(1000):
        sample = df_hist['letalidade_violenta'].sample(len(df_hist), replace=True)
        preds_boot.append(pred + (sample.mean() - df_hist['letalidade_violenta'].mean()))
    lower = max(np.percentile(preds_boot, 2.5), 0)
    upper = np.percentile(preds_boot, 97.5)

    df_hist_media = df.groupby(['ano', 'mes'])['letalidade_violenta'].mean().reset_index()
    df_hist_media = df_hist_media.sort_values(['ano', 'mes'])
    media_historica_valores = df_hist_media['letalidade_violenta'].tolist()

    prev_sum_map = {}
    prev_avg_map = {}
    prev_labels = []

    if DATABASE_URL or all([DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT]):
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ano, mes, SUM(letalidade_violenta), AVG(letalidade_violenta)
                FROM dados_previstos
                GROUP BY ano, mes
                ORDER BY ano, mes
            """)
            prev_data = cursor.fetchall()
            print(prev_data)
            for row in prev_data:
                ano = int(row[0])
                mes = int(row[1])
                key = f"{ano}-{mes:02d}"
                prev_sum_map[key] = float(row[2]) if row[2] is not None else 0.0
                prev_avg_map[key] = float(row[3]) if row[3] is not None else 0.0
            prev_labels = list(prev_sum_map.keys())
            cursor.close()
            conn.close()
        except Exception as e:
            print("Erro ao buscar previsões no banco:", e)

    historico_labels = [f"{int(a)}-{int(m):02d}" for a, m in zip(df_hist['ano'], df_hist['mes'])]
    historico_valores = df_hist['letalidade_violenta'].tolist()

    prev_valores_alinhados = [prev_sum_map.get(lbl, 0.0) for lbl in historico_labels]
    media_previsoes_alinhada = [prev_avg_map.get(lbl, 0.0) for lbl in historico_labels]

    mes = int(data['features'][1])
    ano = int(data['features'][2])
    media_mes_proximo = get_media_mes_proximo(df, mes, ano)
    tendencia = classificar_tendencia(pred, media_mes_proximo)
    risco = classificar_risco(pred, df)

    try:
        importance = list(model.feature_importances_)
    except Exception:
        try:
            importance = list(model.booster_.feature_importance(importance_type='gain'))
        except Exception:
            importance = [0] * len(feature_names)
    importance_dict = dict(zip(feature_names, importance))

    drivers = gerar_drivers_principais(
        model,
        df,
        dict(zip(feature_names, data['features'])),
    )

    try:
        salvar_previsao_banco(dict(zip(feature_names, data['features'])), pred)
    except Exception as e:
        print("Erro ao salvar previsão (não fatal):", e)

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
        "prev_valores": prev_valores_alinhados,
        "media_previsoes_valores": media_previsoes_alinhada,
        "prev_labels": prev_labels
    })

@app.route('/api/valores_select', methods=['GET'])
@login_required
def get_cisps():
    try:
        mapa_cisp = gpd.read_file(SHAPEFILES["cisp"])
        coluna_cisp = "cisp"
        codigos_cisp = sorted(mapa_cisp[coluna_cisp].dropna().unique())

        mapa_mcirc = gpd.read_file(SHAPEFILES["mcirc"])
        coluna_mcirc = "CD_MUN"
        codigos_mcirc = sorted(mapa_mcirc[coluna_mcirc].dropna().unique())

        codigos_cisp = [int(c) if isinstance(c, (np.integer, int)) else str(c) for c in codigos_cisp]
        codigos_mcirc = [int(m) if isinstance(m, (np.integer, int)) else str(m) for m in codigos_mcirc]

        return jsonify({
            "cisps": codigos_cisp,
            "mcircs": codigos_mcirc
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===========================
# API - Agrupamentos
# ===========================
@app.route("/api/agrupamentos_data")
@login_required
def agrupamentos_data():
    global df_clusters_global, dados_scaled_global, dados_cluster_global, payload_agrupamentos, kmeans

    df = load_data()
    k = int(request.args.get("k", 4))
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    municipio = request.args.get("municipio")

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
    ], errors="ignore")

    print(dados_cluster.columns)

    if dados_cluster.empty:
        return jsonify({"error": "Sem dados numéricos para agrupar."}), 400

    colunas = dados_cluster.columns
    dados_imp = pd.DataFrame(
        SimpleImputer(strategy="mean").fit_transform(dados_cluster),
        columns=colunas
    )
    dados_scaled = StandardScaler().fit_transform(dados_imp)

    kmeans = KMeans(n_clusters=k, random_state=42)
    clusters = kmeans.fit_predict(dados_scaled)
    df['cluster'] = clusters
    media_clusters = df.groupby('cluster')[colunas].mean().round(2).to_dict(orient="index")

    pca = PCA(n_components=2)
    pca_result = pca.fit_transform(dados_scaled)
    pca_df = pd.DataFrame(pca_result, columns=["pca1", "pca2"])
    pca_df["cluster"] = clusters
    pca_data = pca_df.to_dict(orient="records")

    df_cluster_profile = df.groupby("cluster")[colunas].mean()

    for col_geo in ["cisp", "aisp", "risp", "mcirc", "ano", "mes"]:
        if col_geo in df_cluster_profile.columns:
            df_cluster_profile = df_cluster_profile.drop(columns=[col_geo])

    perfil_img_sem = os.path.join(MAP_FOLDER, f"perfil_medio_sem_registro_ocorrencias_{k}.png")
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    df_cluster_profile.drop(columns=['registro_ocorrencias'], errors='ignore').plot(kind="bar", ax=ax1)
    ax1.set_title("Perfil médio dos clusters (sem registro_ocorrencias)")
    ax1.set_ylabel("Intensidade relativa (normalizada)")
    ax1.set_xticklabels([f"Cluster {i}" for i in df_cluster_profile.drop(columns=['registro_ocorrencias'], errors='ignore').index], rotation=0)
    legend1 = ax1.legend(frameon=True, bbox_to_anchor=(1.02, 1), loc='upper left')
    legend1.get_frame().set_facecolor('none')
    plt.tight_layout()
    fig1.savefig(perfil_img_sem, dpi=150, bbox_inches='tight')
    plt.close(fig1)

    perfil_img_com = os.path.join(MAP_FOLDER, f"perfil_medio_com_registro_ocorrencias_{k}.png")
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    df_cluster_profile.plot(kind="bar", ax=ax2)
    ax2.set_title("Perfil médio dos clusters (com registro_ocorrencias)")
    ax2.set_ylabel("Intensidade relativa (normalizada)")
    ax2.set_xticklabels([f"Cluster {i}" for i in df_cluster_profile.index], rotation=0)
    legend2 = ax2.legend(frameon=True, bbox_to_anchor=(1.02, 1), loc='upper left')
    legend2.get_frame().set_facecolor('none')
    plt.tight_layout()
    fig2.savefig(perfil_img_com, dpi=150, bbox_inches='tight')
    plt.close(fig2)

    importances = {}
    for col in dados_cluster.columns:
        group_means = df.groupby('cluster')[col].mean()
        inter = np.var(group_means)
        intra = np.mean(df.groupby('cluster')[col].var())
        importances[col] = inter / (intra + 1e-6)
    importances_series = pd.Series(importances).sort_values(ascending=False)

    df_clusters_global = df.copy()

    payload_agrupamentos = {
        "media_clusters": media_clusters,
        "pca_data": pca_data,
        "explained_variance": [round(v, 3) for v in pca.explained_variance_ratio_],
        "perfil_medio_img_sem_registro_ocorrencias": f"/static/img/perfil_medio_sem_registro_ocorrencias_{k}.png",
        "perfil_medio_img_com_registro_ocorrencias": f"/static/img/perfil_medio_com_registro_ocorrencias_{k}.png",
        "perfil_medio_data": df_cluster_profile.to_dict(orient="index"),
        "importancias": importances_series.to_dict(),
        "mapa_clusters_data": mapa_clusters_data  # inclui dados do mapa de clusters
    }

    return jsonify({
        "media_clusters": media_clusters,
        "pca_data": pca_data,
        "explained_variance": [round(v, 3) for v in pca.explained_variance_ratio_],
        "perfil_medio_img_sem_registro_ocorrencias": f"/static/img/perfil_medio_sem_registro_ocorrencias_{k}.png",
        "perfil_medio_img_com_registro_ocorrencias": f"/static/img/perfil_medio_com_registro_ocorrencias_{k}.png",
        "perfil_medio_data": df_cluster_profile.to_dict(orient="index"),
        "importancias": importances_series.to_dict()
    })

# cache global para shapefiles já lidos
_gdf_cache = {}

# ===========================
# API - Mapa de Clusters
# ===========================
@app.route("/api/mapa_clusters")
@login_required
def api_mapa_clusters():
    global kmeans, df_clusters_global, mapa_clusters_data, payload_agrupamentos

    if kmeans is None or df_clusters_global is None:
        return jsonify({"error": "Execute /api/agrupamentos_data primeiro."}), 400

    group_by = request.args.get("group_by", "mcirc")
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")

    shapefile = SHAPEFILES.get(group_by)
    shapefile_col = COLUMN_MAPPING.get(group_by)

    if not shapefile or not shapefile_col:
        return jsonify({"error": "Agrupamento inválido"}), 400

    gdf = gpd.read_file(shapefile)

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    df = df_clusters_global.copy()

    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")

    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]

    if group_by not in df.columns:
        return jsonify({"error": f"Coluna '{group_by}' não encontrada."}), 400

    df_grouped = df.groupby(group_by).agg({
        "cluster": lambda x: x.mode()[0] if not x.mode().empty else -1
    }).reset_index()

    gdf[shapefile_col] = gdf[shapefile_col].astype(str)
    df_grouped[group_by] = df_grouped[group_by].astype(str)

    gdf = gdf.merge(df_grouped, left_on=shapefile_col, right_on=group_by, how="left")
    gdf["cluster"] = gdf["cluster"].fillna(-1).astype(int)

    if "NM_MUN" in gdf.columns:
        gdf["nome"] = gdf["NM_MUN"]
    elif "NM_ESTADO" in gdf.columns:
        gdf["nome"] = gdf["NM_ESTADO"]
    else:
        gdf["nome"] = gdf[shapefile_col]

    default_fixed = {
        0:"#1f77b4",1:"#ff7f0e",2:"#2ca02c",3:"#d62728",
        4:"#9467bd",5:"#8c564b",6:"#e377c2",7:"#17becf",
        8:"#bcbd22",9:"#7f7f7f",-1:"#888888"
    }

    clusters_in_data = sorted(gdf["cluster"].unique())
    fixed_colors = {}

    for cluster in clusters_in_data:
        fixed_colors[int(cluster)] = default_fixed.get(
            int(cluster),
            f"#{np.random.randint(0, 0xFFFFFF):06x}"
        )

    gdf["color"] = gdf["cluster"].map(fixed_colors)

    gdf["geometry"] = gdf["geometry"].simplify(0.01, preserve_topology=True)

    geojson = json.loads(gdf.to_json())

    # Extrair dados resumidos para PDF
    cols_dados = [shapefile_col, "cluster", "nome"]
    cols_existentes = [c for c in cols_dados if c in gdf.columns]
    dados_resumo = [
        {c: row[c] for c in cols_existentes}
        for _, row in gdf[cols_existentes].iterrows()
    ]

    result = {
        "geojson": geojson,
        "colors": fixed_colors,
        "data": dados_resumo
    }

    # Salva na variável global
    mapa_clusters_data = result

    # Atualiza o payload de agrupamentos com os dados mais recentes do mapa
    if payload_agrupamentos:
        payload_agrupamentos["mapa_clusters_data"] = mapa_clusters_data

    return jsonify(result)

@app.route("/api/predizer_cluster", methods=["POST"])
@login_required
def predizer_cluster():
    try:
        data = request.get_json()
        features = data.get("features")
        if not features:
            return jsonify({"error": "Nenhum dado fornecido."}), 400

        k = int(data.get("k", 4))
        feature_names_cluster = [
            'cisp', 'mes', 'ano', 'mcirc', 'letalidade_violenta','tentat_hom', 
            'estupro', 'lesao_corp_culposa', 'roubo_veiculo', 'estelionato',
            'apreensao_drogas', 'trafico_drogas', 'apf',
            'pessoas_desaparecidas', 'encontro_cadaver', 'registro_ocorrencias'
        ]
        X_novo = pd.DataFrame([features], columns=feature_names_cluster)
        print(f"Predizendo cluster para k={k} com features: {X_novo.columns.tolist()}")
        cluster_predito = int(kmeans.predict(X_novo)[0])

        return jsonify({
            "cluster": cluster_predito,
            "mensagem": f"O registro informado pertence ao cluster {cluster_predito}.",
            "k": k
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Rota: gera o PDF do dashboard
# ----------------------------
@app.route("/api/export_dashboard_pdf")
@login_required
def export_dashboard_pdf():
    global payload_dashboard
    
    inicio = request.args.get("inicio") or "2003-01-01"
    fim = request.args.get("fim") or "2025-07-31"
    municipio = request.args.get("municipio")
    group_by = request.args.get("group_by") or "mcirc"
    params = {"inicio": inicio, "fim": fim, "municipio": municipio, "group_by": group_by}

    # Garante que map_data mais recente esteja no payload
    payload_dashboard["map_data"] = map_data

    try:
        descricoes = gerar_descricoes_dashboard(payload_dashboard, group_by)
    except Exception as e:
        print(f"Erro ao gerar descrições: {e}")
        descricoes = {
            "linha_evolucao": "Consulte o gráfico de evolução temporal.",
            "barras_correlacao": "Consulte o gráfico de correlações.",
            "scatter": "Consulte o gráfico de dispersão.",
            "mapa": "Consulte o mapa temático."
        }

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_imgs = criar_graficos_temp_dashboard(payload_dashboard, tmpdir, group_by)
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("<b>Relatório do Dashboard - Monitor de Criminalidade RJ</b>", styles["Title"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"<b>Período:</b> {params['inicio']} – {params['fim']}", styles["Normal"]))
            story.append(Paragraph(f"<b>Município:</b> {params['municipio'] or 'Todos'}", styles["Normal"]))
            story.append(Spacer(1, 20))

            story.append(Paragraph("<b>Indicadores Principais</b>", styles["Heading2"]))
            story.append(Paragraph(f"• Letalidade Violenta Total: {payload_dashboard.get('letalidade_violenta_total', 0)}", styles["Normal"]))
            story.append(Paragraph(f"• Homicídios Dolosos (média): {payload_dashboard.get('homicidios_dolosos', 0)}", styles["Normal"]))
            story.append(Paragraph(f"• Soma de latrocínios: {payload_dashboard.get('latrocinios', 0)}", styles["Normal"]))
            story.append(Paragraph(f"• Homicídios Por Intervenção Policial: {payload_dashboard.get('mortes_intervencao_policial', 0)}", styles["Normal"]))
            story.append(Spacer(1, 20))

            sections = [
                ("linha_evolucao", "Evolução Temporal da Letalidade Violenta"),
                ("barras_correlacao", "Correlação entre Crimes e Letalidade"),
                ("scatter", "Relação entre Roubo na Rua e Letalidade"),
                ("mapa", "Distribuição Geográfica da Letalidade")
            ]

            for chave, titulo in sections:
                story.append(Paragraph(f"<b>{titulo}</b>", styles["Heading2"]))
                story.append(Spacer(1, 6))
                story.append(Paragraph(descricoes.get(chave, "Análise não disponível."), styles["Normal"]))
                story.append(Spacer(1, 8))
                if saved_imgs.get(chave):
                    story.append(Image(saved_imgs[chave], width=480, height=240 if chave != "scatter" else 300))
                story.append(Spacer(1, 16))

            story.append(Spacer(1, 20))
            story.append(Paragraph("<i>Relatório gerado automaticamente com IA (GPT-4o Mini) - Monitor RJ.</i>", styles["Normal"]))

            doc.build(story)
            buffer.seek(0)
            nome_pdf = f"relatorio_dashboard_{params.get('inicio', 'sem_data')}.pdf"
            return send_file(buffer, as_attachment=True, download_name=nome_pdf, mimetype="application/pdf")
    except Exception as e:
        print(f"[ERRO PDF] {e}")
        return jsonify({"erro": "Falha ao gerar PDF"}), 500

@app.route("/api/export_agrupamentos_pdf")
@login_required
def export_agrupamentos_pdf():
    global payload_agrupamentos

    inicio = request.args.get("inicio") or "2003-01-01"
    fim = request.args.get("fim") or "2025-07-31"
    municipio = request.args.get("municipio")
    group_by = request.args.get("group_by") or "mcirc"
    k = request.args.get("k") or 4
    params = {"inicio": inicio, "fim": fim, "municipio": municipio, "group_by": group_by, "k": k}

    # Garante que mapa_clusters_data mais recente esteja no payload
    payload_agrupamentos["mapa_clusters_data"] = mapa_clusters_data

    try:
        descricoes = gerar_descricoes_agrupamentos(payload_agrupamentos, group_by)
    except Exception as e:
        print(f"Erro ao gerar descrições: {e}")
        descricoes = {
            "scatter_pca": "Consulte o gráfico de projeção PCA.",
            "perfil_medio_clusters": "Consulte o gráfico de perfil médio dos clusters.",
            "importancia_variaveis": "Consulte o gráfico de importância das variáveis.",
            "mapa_clusters": "Consulte o mapa temático dos clusters."
        }

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_imgs = criar_graficos_temp_agrupamentos(payload_agrupamentos, tmpdir, group_by)
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("<b>Relatório de Agrupamentos - Monitor de Criminalidade RJ</b>", styles["Title"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"<b>Período:</b> {params['inicio']} – {params['fim']}", styles["Normal"]))
            story.append(Paragraph(f"<b>Município:</b> {params['municipio'] or 'Todos'}", styles["Normal"]))
            story.append(Spacer(1, 20))

            sections = [
                ("scatter_pca", "Projeção PCA dos Clusters"),
                ("perfil_medio_clusters", "Perfil Médio dos Clusters"),
                ("importancia_variaveis", "Importância das Variáveis nos Clusters"),
                ("mapa_clusters", "Mapa Temático dos Clusters")
            ]

            for chave, titulo in sections:
                story.append(Paragraph(f"<b>{titulo}</b>", styles["Heading2"]))
                story.append(Spacer(1, 6))
                story.append(Paragraph(descricoes.get(chave, "Análise não disponível."), styles["Normal"]))
                story.append(Spacer(1, 8))
                if saved_imgs.get(chave):
                    story.append(Image(saved_imgs[chave], width=480, height=240))
                story.append(Spacer(1, 16))

            story.append(Spacer(1, 20))
            story.append(Paragraph("<i>Relatório gerado automaticamente com IA (GPT-4o Mini) - Monitor RJ.</i>", styles["Normal"]))

            doc.build(story)
            buffer.seek(0)
            nome_pdf = f"relatorio_agrupamentos.pdf"
            return send_file(buffer, as_attachment=True, download_name=nome_pdf, mimetype="application/pdf")
    except Exception as e:
        print(f"[ERRO PDF AGRUPAMENTOS] {e}")
        return jsonify({"erro": "Falha ao gerar PDF"}), 500

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
 
        if password != confirm_password:
            flash("As senhas não coincidem!")
            return redirect(url_for("cadastro"))
 
        try:
            conn = get_connection()
            cur = conn.cursor()
           
            cur.execute("""
                INSERT INTO users (nome, email, username, password)
                VALUES (%s, %s, %s, %s)
            """, (nome, email, username, password))
 
            conn.commit()
            cur.close()
            conn.close()
 
            flash("Cadastro realizado com sucesso!")
            return redirect(url_for("login"))
 
        except psycopg2.IntegrityError:
            conn.rollback()
            flash("Email ou usuário já cadastrado!")
            return redirect(url_for("cadastro"))
 
        except Exception as e:
            flash(f"Erro ao cadastrar: {e}")
            return redirect(url_for("cadastro"))
 
    return render_template("cadastro.html")
 
 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_captcha = request.form.get('captcha', '').upper()

        if os.getenv("TEST_MODE") == "1":
            print("⚠ TEST_MODE ATIVO → Ignorando captcha do login!")
        else:
            if user_captcha != session.get('captcha_text', ''):
                flash("Captcha incorreto!")
                return redirect(url_for('login'))
        
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",
                    (username, password))
        user = cur.fetchone()

        if not user:
            flash("Usuário ou senha incorretos!")
            return redirect(url_for('login'))

        session['user_id'] = user[0]
        flash("Login realizado com sucesso!")
        return redirect(url_for('index'))

    return render_template('login.html')
    
def gerar_descricoes_previsao(payload):
    """
    Gera descrições automáticas para a página de previsão.
    """
    descricoes = {
        "historico": "Análise não disponível.",
        "feature_importance": "Análise não disponível.",
        "intervalo_confianca": "Análise não disponível.",
        "soma_media_comparacao": "Análise não disponível."
    }

    try:
        previsao = payload.get("previsao_leitura", 0)
        intervalo = payload.get("intervalo_95", [0, 0])
        tendencia = payload.get("tendencia", "Indefinida")
        risco = payload.get("risco", "Baixo")
        drivers = payload.get("drivers", "Nenhum driver identificado")

        resumo_historico = f"""
        Previsão: {previsao} casos de letalidade violenta.
        Intervalo de confiança (95%): [{intervalo[0]:.1f}, {intervalo[1]:.1f}]
        Tendência: {tendencia}
        Nível de risco: {risco}
        Principais drivers: {drivers}
        """

        prompt_historico = f"""
Você é um analista de segurança pública.
Analise a seguinte previsão de criminalidade e produza uma resposta em português:
Mande em texto corrido, não em markdown.
[PREVISÃO DE CRIMINALIDADE]
{resumo_historico}
"""
        descricoes["historico"] = gerar_texto_gpt4o(prompt_historico)

        feature_importance = payload.get("feature_importance", {})
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]
        resumo_features = ", ".join([f"{k.replace('_', ' ')} ({v:.3f})" for k, v in top_features])

        prompt_features = f"""
Você é um analista de segurança pública.
Analise as principais variáveis que influenciam a previsão e produza uma resposta curta (2-3 frases) em português:

[IMPORTÂNCIA DAS VARIÁVEIS]
{resumo_features}
"""
        descricoes["feature_importance"] = gerar_texto_gpt4o(prompt_features)

        lower, upper = intervalo
        amplitude = upper - lower
        resumo_intervalo = f"Intervalo: [{lower:.1f}, {upper:.1f}], amplitude: {amplitude:.1f}"

        prompt_intervalo = f"""
Você é um analista de segurança pública.
Analise o intervalo de confiança da previsão e produza uma resposta curta (2-3 frases) em português:

[INTERVALO DE CONFIANÇA]
{resumo_intervalo}
"""
        descricoes["intervalo_confianca"] = gerar_texto_gpt4o(prompt_intervalo)

        soma_hist = sum(payload.get("historico_valores", []))
        soma_prev = sum(payload.get("prev_valores", []))
        media_hist = np.mean(payload.get("historico_valores", [])) if payload.get("historico_valores") else 0
        media_prev_val = np.mean(payload.get("prev_valores", [])) if payload.get("prev_valores") else 0

        prompt_soma_media = f"""
Você é um analista de segurança pública.
Compare o comportamento da letalidade violenta entre o histórico e as previsões,
considerando tanto a soma total quanto a média mensal dos casos.
Explique brevemente se há tendência de aumento, estabilidade ou redução,
e interprete o que isso pode significar para o cenário de segurança.
Mande em texto corrido, não em markdown.
[SOMA E MÉDIA]
Soma - Histórico: {soma_hist:.1f} | Previsões: {soma_prev:.1f}
Média - Histórico: {media_hist:.1f} | Previsões: {media_prev_val:.1f}
"""
        descricoes["soma_media_comparacao"] = gerar_texto_gpt4o(prompt_soma_media)

        return descricoes

    except Exception as e:
        print(f"Erro ao gerar descrições de previsão: {e}")
        return descricoes

def criar_graficos_temp_previsao(payload, tmp_dir):
    """
    Cria gráficos para o relatório de previsão.
    """
    saved = {}

    historico = payload.get("historico_valores", [])
    previsoes = payload.get("prev_valores", [])
    media_hist = payload.get("media_historica_valores", [])
    media_prev = payload.get("media_previsoes_valores", [])
    labels_hist = payload.get("historico_labels", [])
    prev_labels = payload.get("prev_labels", [])
    feature_importance = payload.get("feature_importance", {})
    media_prev = [
        0 if (x is None or pd.isna(x)) else x
        for x in media_prev
    ]

    def to_nan_list(lista):
        return [np.nan if (v is None or v == "None") else v for v in lista]

    previsoes = to_nan_list(previsoes)
    media_hist = to_nan_list(media_hist)
    media_prev = to_nan_list(media_prev)

    if len(media_hist) < len(historico):
        diff = len(historico) - len(media_hist)
        media_hist = [np.nan] * diff + media_hist

    def to_date(label_list):
        return [datetime.strptime(x, "%Y-%m") for x in label_list]

    if historico:
        plt.figure(figsize=(10, 6))

        hist_dates = to_date(labels_hist)
        prev_dates = to_date(prev_labels)

        plt.plot(hist_dates, historico, label="Soma Histórica", linewidth=2, color="#1f77b4")

        previsoes_clean = [(d, v) for d, v in zip(prev_dates, previsoes) if not np.isnan(v)]
        if previsoes_clean:
            plt.scatter(
                [d for d, _ in previsoes_clean],
                [v for _, v in previsoes_clean],
                label="Soma Prevista",
                color="#d62728"
            )

        if media_hist:
            plt.plot(hist_dates, media_hist, label="Média Histórica", linewidth=2, alpha=0.7, color="#2ca02c")

        media_prev_clean = [(d, v) for d, v in zip(prev_dates, media_prev) if not np.isnan(v)]
        if media_prev_clean:
            plt.scatter(
                [d for d, _ in media_prev_clean],
                [v for _, v in media_prev_clean],
                label="Média Prevista",
                alpha=0.7,
                color="#ff7f0e"
            )
        else:
            print("⚠ Média Prevista NÃO possui valores válidos (todos são None/NaN).")

        plt.title("Histórico vs Previsões — Soma e Média ao longo do tempo", fontsize=14)
        plt.xlabel("Período (Ano-Mês)")
        plt.ylabel("Número de Casos")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.6)
        plt.gcf().autofmt_xdate()

        caminho = os.path.join(tmp_dir, "historico_previsoes_soma_media.png")
        plt.savefig(caminho, dpi=150)
        plt.close()

        saved["historico_previsoes_soma_media"] = caminho

    if feature_importance:
        fatores = list(feature_importance.keys())
        importancias = list(feature_importance.values())

        fatores_ordenados = [x for _, x in sorted(zip(importancias, fatores), reverse=True)]
        importancias_ordenadas = sorted(importancias, reverse=True)

        plt.figure(figsize=(10, 6))
        plt.barh(fatores_ordenados, importancias_ordenadas, color="#9467bd", alpha=0.85)
        plt.xlabel("Importância")
        plt.title("Contribuição por Fator (Feature Importance)", fontsize=14)
        plt.gca().invert_yaxis()
        plt.grid(axis="x", linestyle="--", alpha=0.6)
        plt.tight_layout()

        caminho = os.path.join(tmp_dir, "contribuicao_fatores.png")
        plt.savefig(caminho, dpi=150)
        plt.close()

        saved["feature_importance"] = caminho

    return saved

@app.route('/api/export_previsao_pdf', methods=['POST'])
@login_required
def export_previsao_pdf():
    payload = request.get_json()

    descricoes = gerar_descricoes_previsao(payload)

    tmp_dir = tempfile.mkdtemp()
    try:
        print(payload)
        graficos = criar_graficos_temp_previsao(payload, tmp_dir)
        print(graficos)
    except Exception as e:
        print("Erro ao criar gráficos temporários:", e)
        graficos = {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>Relatório de Previsão de Letalidade Violenta</b>", styles["Title"]))
    story.append(Spacer(1, 8))

    features_dict = payload.get("features_dict")
    if not features_dict:
        features_list = payload.get("features") or payload.get("features_array") or []
        try:
            features_dict = dict(zip(feature_names, features_list))
        except Exception:
            features_dict = {f"feature_{i}": v for i, v in enumerate(features_list)}

    story.append(Paragraph("<b>Valores das Variáveis (entrada)</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))

    table_data = [["Variável", "Valor"]]
    for k in sorted(features_dict.keys()):
        v = features_dict[k]
        if isinstance(v, float):
            v_str = f"{v:.3f}"
        else:
            v_str = str(v)
        table_data.append([k.replace('_', ' '), v_str])

    tbl = Table(table_data, colWidths=[200, 200])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f2f2f2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('BOX', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"Previsão: {payload.get('previsao_leitura', '-')}", styles["Normal"]))
    story.append(Paragraph(f"Intervalo 95%: {payload.get('intervalo_95', '-')}", styles["Normal"]))
    story.append(Paragraph(f"Tendência: {payload.get('tendencia', '-')}", styles["Normal"]))
    story.append(Paragraph(f"Risco: {payload.get('risco', '-')}", styles["Normal"]))
    story.append(Spacer(1, 12))
    
    drivers = payload.get("drivers", [])
    story.append(Paragraph("<b>Drivers Principais</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))
    if drivers:
        if isinstance(drivers, (list, tuple)):
            for d in drivers:
                story.append(Paragraph(f"• {d}", styles["Normal"]))
        else:
            story.append(Paragraph(str(drivers), styles["Normal"]))
    else:
        story.append(Paragraph("Nenhum driver identificado.", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Análise da Previsão</b>", styles["Heading2"]))
    story.append(Paragraph(descricoes.get("historico", "—"), styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Importância das Variáveis / Contribuição por Fator</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))
    if "feature_importance" in graficos:
        try:
            story.append(Image(graficos["feature_importance"], width=450, height=300))
            story.append(Spacer(1, 10))
        except Exception as e:
            print("Erro ao adicionar imagem feature_importance:", e)
    story.append(Paragraph(descricoes.get("feature_importance", "—"), styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Intervalo de Confiança</b>", styles["Heading2"]))
    story.append(Paragraph(descricoes.get("intervalo_confianca", "—"), styles["Normal"]))
    story.append(Spacer(1, 12))

    if "historico_previsoes_soma_media" in graficos:
        story.append(Paragraph("<b>Histórico vs Previsões — Soma e Média ao longo do tempo</b>", styles["Heading2"]))
        story.append(Image(graficos["historico_previsoes_soma_media"], width=450, height=300))
        story.append(Spacer(1, 6))
        story.append(Paragraph(descricoes.get("soma_media_comparacao", "—"), styles["Normal"]))
        story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)

    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    return send_file(buffer, as_attachment=True, download_name='relatorio_previsao.pdf', mimetype='application/pdf')


# ===========================
# API - Regras de Associação (Apriori)
# ===========================
@app.route("/api/associacao_data")
@login_required
def associacao_data():
    """
    Executa o algoritmo Apriori para descobrir regras de associação entre
    tipos de crime registrados por CISP/período.
    """
    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder

    df = load_data()

    inicio     = request.args.get("inicio")
    fim        = request.args.get("fim")
    municipio  = request.args.get("municipio")
    min_sup    = float(request.args.get("min_support", 0.05))
    min_conf   = float(request.args.get("min_conf",    0.50))
    min_lift   = float(request.args.get("min_lift",    1.20))
    top_n      = int(request.args.get("top_n",         30))
    group_by   = request.args.get("group_by",          "cisp")

    df["data"] = pd.to_datetime(
        df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01"
    )
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
            print("Erro ao filtrar município:", e)

    if df.empty:
        return jsonify({"error": "Sem dados após os filtros aplicados."}), 400

    colunas_crime = [
        "hom_doloso", "latrocinio", "hom_por_interv_policial",
        "tentat_hom", "lesao_corp_dolosa", "estupro",
        "lesao_corp_culposa", "roubo_veiculo", "roubo_rua",
        "roubo_comercio", "roubo_residencia", "estelionato",
        "apreensao_drogas", "trafico_drogas", "apf",
        "pessoas_desaparecidas", "encontro_cadaver",
        "registro_ocorrencias", "furto_veiculos"
    ]
    colunas_disponiveis = [c for c in colunas_crime if c in df.columns]

    grupo_cols = [group_by, "ano", "mes"] if group_by in df.columns else ["ano", "mes"]
    df_agg = df.groupby(grupo_cols)[colunas_disponiveis].sum().reset_index()

    df_bin = df_agg[colunas_disponiveis].copy()
    for col in colunas_disponiveis:
        mediana = df_bin[col].median()
        df_bin[col] = (df_bin[col] > mediana).astype(bool)

    df_bin = df_bin.loc[:, df_bin.nunique() > 1]

    if df_bin.shape[1] < 2:
        return jsonify({"error": "Dados insuficientes para gerar regras de associação."}), 400

    try:
        freq_items = apriori(df_bin, min_support=min_sup, use_colnames=True, max_len=4)
        if freq_items.empty:
            return jsonify({"error": f"Nenhum itemset frequente com suporte ≥ {min_sup}. Tente reduzir o suporte mínimo."}), 400

        rules = association_rules(freq_items, metric="lift", min_threshold=min_lift)
        rules = rules[rules["confidence"] >= min_conf]

        if rules.empty:
            return jsonify({"error": "Nenhuma regra encontrada com os parâmetros informados."}), 400

        rules = rules.sort_values("lift", ascending=False).head(top_n)

        rules_list = []
        for _, row in rules.iterrows():
            rules_list.append({
                "antecedentes": list(row["antecedents"]),
                "consequentes": list(row["consequents"]),
                "support":    round(float(row["support"]),    4),
                "confidence": round(float(row["confidence"]), 4),
                "lift":       round(float(row["lift"]),        4),
                "conviction": round(float(row.get("conviction", 1.0)), 4),
                "leverage":   round(float(row.get("leverage",  0.0)), 4),
            })

        freq_items["itemset_label"] = freq_items["itemsets"].apply(
            lambda x: " + ".join(sorted(x))
        )
        freq_items_sorted = (
            freq_items.sort_values("support", ascending=False)
            .head(20)
        )
        itemsets_freq = freq_items_sorted[["itemset_label", "support"]].to_dict(orient="records")

        cooc = {}
        for col_a in df_bin.columns:
            cooc[col_a] = {}
            for col_b in df_bin.columns:
                cooc[col_a][col_b] = round(
                    float((df_bin[col_a] & df_bin[col_b]).mean()), 4
                )

        stats = {
            "total_transacoes":    int(len(df_bin)),
            "total_itemsets":      int(len(freq_items)),
            "total_regras":        int(len(rules_list)),
            "lift_medio":          round(float(rules["lift"].mean()),       3),
            "confianca_media":     round(float(rules["confidence"].mean()), 3),
            "suporte_medio":       round(float(rules["support"].mean()),    3),
            "periodo_inicio":      str(df["data"].min().date()),
            "periodo_fim":         str(df["data"].max().date()),
        }

        return jsonify({
            "rules":         rules_list,
            "itemsets_freq": itemsets_freq,
            "coocorrencia":  cooc,
            "stats":         stats,
            "colunas":       list(df_bin.columns),
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Erro ao executar Apriori: {str(e)}"}), 500


@app.route('/associacao')
@login_required
def associacao():
    return render_template('associacao.html')

def gerar_descricoes_associacao(payload):
    descricoes = {
        "regras": "Análise não disponível.",
        "itemsets": "Análise não disponível.",
        "heatmap": "Análise não disponível.",
        "resumo": "Análise não disponível."
    }

    rules = payload.get("rules", [])
    itemsets = payload.get("itemsets_freq", [])
    stats = payload.get("stats", {})

    if rules:
        top = rules[0]
        resumo_regras = (
            f"Regra mais forte: {top['antecedentes']} → {top['consequentes']} "
            f"(lift={top['lift']}, confiança={top['confidence']})"
        )
    else:
        resumo_regras = "Sem regras relevantes."

    prompt_regras = f"""
Você é um analista de segurança pública.
Explique brevemente (2-3 frases) o significado das regras de associação:

{resumo_regras}
"""
    descricoes["regras"] = gerar_texto_gpt4o(prompt_regras)

    if itemsets:
        top_items = itemsets[:5]
        resumo_items = ", ".join([f"{i['itemset_label']} ({i['support']})" for i in top_items])
    else:
        resumo_items = "Sem itemsets relevantes."

    prompt_items = f"""
Analise os conjuntos frequentes abaixo e gere uma explicação curta (2-3 frases):

{resumo_items}
"""
    descricoes["itemsets"] = gerar_texto_gpt4o(prompt_items)

    cooc = payload.get("coocorrencia", {})
    if cooc:
        resumo_heat = "Existe co-ocorrência relevante entre alguns crimes."
    else:
        resumo_heat = "Sem dados de co-ocorrência."

    prompt_heat = f"""
Explique brevemente o padrão de co-ocorrência entre crimes:

{resumo_heat}
"""
    descricoes["heatmap"] = gerar_texto_gpt4o(prompt_heat)

    resumo = f"""
Total de regras: {stats.get('total_regras', 0)},
Lift médio: {stats.get('lift_medio', 0)},
Confiança média: {stats.get('confianca_media', 0)}
"""

    prompt_resumo = f"""
Faça um resumo executivo (2-3 frases):

{resumo}
"""
    descricoes["resumo"] = gerar_texto_gpt4o(prompt_resumo)

    if rules:
        top = rules[0]
        resumo_rede = f"{top['antecedentes']} levam a {top['consequentes']} com lift {top['lift']}"
    else:
        resumo_rede = "Sem conexões fortes."

    prompt_rede = f"""
    Explique a rede de associações entre crimes em poucas frases:

    {resumo_rede}
    """
    descricoes["rede"] = gerar_texto_gpt4o(prompt_rede)

    return descricoes

def criar_graficos_temp_associacao(payload, tmp_dir):
    saved = {}

    itemsets = payload.get("itemsets_freq", [])
    if itemsets:
        labels = [i["itemset_label"] for i in itemsets[:15]]
        values = [i["support"] for i in itemsets[:15]]

        plt.figure(figsize=(8,4))
        plt.barh(labels, values)
        plt.title("Itemsets Frequentes")
        plt.xlabel("Suporte")
        plt.tight_layout()

        caminho = os.path.join(tmp_dir, "itemsets.png")
        plt.savefig(caminho)
        plt.close()
        saved["itemsets"] = caminho

    rules = payload.get("rules", [])
    if rules:
        xs = [r["support"] for r in rules]
        ys = [r["confidence"] for r in rules]

        plt.figure(figsize=(6,6))
        plt.scatter(xs, ys)
        plt.xlabel("Suporte")
        plt.ylabel("Confiança")
        plt.title("Regras: Suporte x Confiança")
        plt.grid(True)

        caminho = os.path.join(tmp_dir, "scatter.png")
        plt.savefig(caminho)
        plt.close()
        saved["scatter"] = caminho

    cooc = payload.get("coocorrencia", {})
    if cooc:
        df = pd.DataFrame(cooc)

        plt.figure(figsize=(8,6))
        plt.imshow(df, cmap="Blues")
        plt.colorbar()
        plt.xticks(range(len(df.columns)), df.columns, rotation=45)
        plt.yticks(range(len(df.index)), df.index)
        plt.title("Heatmap de Co-ocorrência")

        caminho = os.path.join(tmp_dir, "heatmap.png")
        plt.tight_layout()
        plt.savefig(caminho)
        plt.close()
        saved["heatmap"] = caminho

    rules = payload.get("rules", [])
    if rules:
        G = nx.DiGraph()

        for r in rules[:30]:
            for ant in r["antecedentes"]:
                for cons in r["consequentes"]:
                    G.add_edge(
                        ant,
                        cons,
                        weight=r["lift"],
                        confidence=r["confidence"]
                    )

        plt.figure(figsize=(8,6))

        pos = nx.spring_layout(G, seed=42)

        edges = G.edges(data=True)
        weights = [d["weight"] for (_, _, d) in edges]

        nx.draw_networkx_nodes(G, pos, node_size=800)
        nx.draw_networkx_labels(G, pos, font_size=8)

        nx.draw_networkx_edges(
            G, pos,
            width=[w * 1.5 for w in weights],
            alpha=0.6,
            arrows=True
        )

        plt.title("Rede de Associações entre Crimes")
        plt.axis("off")

        caminho = os.path.join(tmp_dir, "rede.png")
        plt.tight_layout()
        plt.savefig(caminho)
        plt.close()

        saved["rede"] = caminho

    return saved

@app.route("/api/export_associacao_pdf")
@login_required
def export_associacao_pdf():
    try:
        response = associacao_data()
        payload = response.get_json()

        descricoes = gerar_descricoes_associacao(payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            imgs = criar_graficos_temp_associacao(payload, tmpdir)

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            story.append(Paragraph("<b>Relatório de Regras de Associação</b>", styles["Title"]))
            story.append(Spacer(1, 12))

            stats = payload.get("stats", {})

            story.append(Paragraph("<b>Resumo Geral</b>", styles["Heading2"]))
            story.append(Paragraph(f"• Total de regras: {stats.get('total_regras', 0)}", styles["Normal"]))
            story.append(Paragraph(f"• Lift médio: {stats.get('lift_medio', 0)}", styles["Normal"]))
            story.append(Paragraph(f"• Confiança média: {stats.get('confianca_media', 0)}", styles["Normal"]))
            story.append(Spacer(1, 20))

            sections = [
                ("itemsets", "Itemsets Frequentes"),
                ("scatter", "Relação Suporte x Confiança"),
                ("heatmap", "Co-ocorrência entre Crimes"),
                ("rede", "Rede de Associações"),
            ]

            for chave, titulo in sections:
                story.append(Paragraph(f"<b>{titulo}</b>", styles["Heading2"]))
                story.append(Spacer(1, 6))

                story.append(Paragraph(descricoes.get(chave, ""), styles["Normal"]))
                story.append(Spacer(1, 8))

                if imgs.get(chave):
                    story.append(Image(imgs[chave], width=480, height=260))

                story.append(Spacer(1, 16))

            story.append(Paragraph("<b>Resumo Executivo</b>", styles["Heading2"]))
            story.append(Paragraph(descricoes["resumo"], styles["Normal"]))
            story.append(Spacer(1, 20))

            rules = payload.get("rules", [])

            if rules:
                rules = sorted(rules, key=lambda x: x["lift"], reverse=True)

                story.append(Paragraph("<b>Principais Regras de Associação</b>", styles["Heading2"]))
                story.append(Spacer(1, 6))

                story.append(Paragraph(descricoes.get("regras", ""), styles["Normal"]))
                story.append(Spacer(1, 10))

                data_table = [["Antecedente", "Consequente", "Support", "Confidence", "Lift"]]

                for r in rules[:10]:
                    data_table.append([
                        ", ".join(r["antecedentes"]),
                        ", ".join(r["consequentes"]),
                        f"{r['support']:.3f}",
                        f"{r['confidence']:.3f}",
                        f"{r['lift']:.3f}",
                    ])

                table = Table(data_table, repeatRows=1)

                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (2, 1), (-1, -1), "CENTER"),
                ]))

                story.append(table)
                story.append(Spacer(1, 20))

            else:
                story.append(Paragraph("<b>Principais Regras de Associação</b>", styles["Heading2"]))
                story.append(Paragraph("Nenhuma regra encontrada com os parâmetros selecionados.", styles["Normal"]))
                story.append(Spacer(1, 20))

            doc.build(story)
            buffer.seek(0)

            return send_file(
                buffer,
                as_attachment=True,
                download_name="relatorio_associacao.pdf",
                mimetype="application/pdf"
            )

    except Exception as e:
        print("Erro:", e)
        return jsonify({"erro": "Falha ao gerar PDF"}), 500
        
if __name__ == "__main__":
    if os.getenv("RENDER") != "true":
        host = os.getenv("IP_OR_HOST", "127.0.0.1")
        port = int(os.getenv("PORT", 5000))
        debug = os.getenv("FLASK_DEBUG", "1") == "1"
        app.run(host=host, port=port, debug=debug)
