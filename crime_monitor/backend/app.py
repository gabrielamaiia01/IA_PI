from flask import Flask, render_template, jsonify, request, request, send_file, session, flash, redirect, url_for
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


import re
from db import get_connection
# ----------------------------
# Config: modelo de geração
# ----------------------------
# Usa FLAN-T5 small por ser leve e gerar textos coerentes.
# Se quiser outro modelo (pt-br), substitua o string abaixo.

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

df_clusters_global = None
dados_scaled_global = None
dados_cluster_global = None

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
            INSERT INTO public.dados_previstos
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

def generate_distinct_colors(k, fixed_colors=None):
    """
    Gera k cores distintas, evitando colisão com uma lista de cores fixas.
    Retorna cores em hexadecimal.
    :param k: número de cores a gerar
    :param fixed_colors: lista de cores hex existentes a evitar
    :return: lista de cores hex
    """
    if fixed_colors is None:
        fixed_colors = []

    # Converte cores fixas para RGB
    print(f"Fixed colors: {fixed_colors}")
    fixed_rgb = [mcolors.to_rgb(c) for c in fixed_colors.values()]

    colors = []
    attempt = 0
    while len(colors) < k and attempt < k * 10:
        # HSV equidistante
        h = random.random()
        s = 0.7 + 0.3 * random.random()  # saturação entre 0.7 e 1
        v = 0.8 + 0.2 * random.random()  # valor entre 0.8 e 1
        rgb = colorsys.hsv_to_rgb(h, s, v)

        # Verifica se está suficientemente distante das cores fixas e já geradas
        def is_distinct(rgb_new):
            threshold = 0.3  # distância mínima Euclidiana no espaço RGB
            for r in fixed_rgb + [mcolors.to_rgb(c) for c in colors]:
                dist = sum((a - b) ** 2 for a, b in zip(rgb_new, r)) ** 0.5
                if dist < threshold:
                    return False
            return True

        if is_distinct(rgb):
            colors.append('#{:02x}{:02x}{:02x}'.format(int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)))

        attempt += 1

    # Se não conseguiu gerar suficientes, completa com cores aleatórias
    while len(colors) < k:
        colors.append('#{:06x}'.format(random.randint(0, 0xFFFFFF)))

    return colors

# ----------------------------
# Função que usa o modelo para gerar descrições por gráfico
# ----------------------------
# --- Inicializa modelo local (uma vez) ---

# Caminho local do modelo Mistral-7B-Instruct-v0.3
# CORREÇÃO 2: Função de geração com fallback
def gerar_texto_gpt4o(prompt, max_tokens=800, temperature=0.7, retries=2, wait=3):
    """
    Gera texto com o modelo LLaMA 3 (meta-llama/llama-3-8b-instruct) via OpenRouter.
    Permite retries em caso de falha temporária.
    
    Args:
        prompt (str): Prompt de entrada.
        max_tokens (int): Máximo de tokens.
        temperature (float): Criatividade do modelo.
        retries (int): Número de tentativas em caso de falha.
        wait (int): Segundos para aguardar entre tentativas.
        
    Returns:
        str: Texto gerado ou mensagem de erro.
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
            print(f"[ERRO LLAMA3] Tentativa {attempt+1} de {retries+1}: {e}")
            if attempt < retries:
                time.sleep(wait)
            else:
                return "Não foi possível gerar análise automática no momento. Consulte os gráficos."
        except Exception as e:
            print(f"[ERRO LLAMA3] Problema ao processar resposta: {e}")
            return "Não foi possível gerar análise automática no momento. Consulte os gráficos."
            
# =========================
# FUNÇÃO DE ANÁLISES
# =========================
def gerar_descricoes_dashboard(payload, group_by):
    """
    Gera descrições automáticas para os gráficos, dividindo prompts para cada gráfico.
    """
    descricoes = {
        "linha_evolucao": "Análise não disponível.",
        "barras_correlacao": "Análise não disponível.",
        "scatter": "Análise não disponível.",
        "mapa": "Análise não disponível."
    }

    base_url = "http://localhost:5000"
    params_map = {
        "inicio": payload.get("inicio", "2003-01-01"),
        "fim": payload.get("fim", "2025-07-31"),
        "municipio": payload.get("municipio"),
        "group_by": group_by
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
    map_data = {}
    try:
        resp_map = requests.get(f"{base_url}/api/map_image/{group_by}", params=params_map, timeout=10)
        resp_map.raise_for_status()
        map_data = resp_map.json()
    except:
        map_data = {}

    # map_data é o JSON retornado pelo map_image
    group_label = {
        "mcirc": "município",
        "cisp": "CISP",
        "aisp": "AISP",
        "risp": "RISP"
    }.get(group_by, "agrupamento")

    if map_data.get("data"):
        texto_map = f"Letalidade violenta por {group_label}:\n" + "\n".join([
            f"• {item.get('NM_MUN', item.get(group_by, 'Desconhecido'))} "
            f"({item.get('CD_MUN', '-')}) — {int(item.get('letalidade_violenta', 0))}"
            for item in map_data["data"]
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
    # 🗺️ Mapa (pega diretamente do endpoint map_image)
    # ===============================
    try:
        base_url = "http://localhost:5000"  # ajuste se usar outra porta/host
        params = {
            "inicio": payload.get("inicio", "2003-01-01"),
            "fim": payload.get("fim", "2025-07-31"),
            "municipio": payload.get("municipio")
        }
        resp = requests.get(f"{base_url}/api/map_image/{group_by}", params=params, timeout=20)
        if resp.status_code == 200:
            map_json = resp.json()
            map_url = f"{base_url}{map_json.get('image_url')}"
            if map_url:
                r = requests.get(map_url, timeout=10)
                if r.status_code == 200:
                    caminho = os.path.join(tmp_dir, "mapa.png")
                    with open(caminho, "wb") as f:
                        f.write(r.content)
                    saved["mapa"] = caminho
    except Exception as e:
        print(f"[ERRO mapa]: {e}")

    return saved

def gerar_descricoes_agrupamentos(payload, group_by):
    """
    Gera descrições automáticas para os gráficos de agrupamentos:
    - Scatter PCA
    - Perfil médio dos clusters
    - Importância das variáveis
    - Mapa dos clusters
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
        # MAPA DOS CLUSTERS
        # =====================
        base_url = f"http://{IP_OR_HOST}:5000"
        params = {
            "inicio": payload.get("inicio", "2003-01-01"),
            "fim": payload.get("fim", "2025-07-31"),
            "municipio": payload.get("municipio", ""),
            "group_by": group_by,
            "k": payload.get("k", 4)
        }

        resumo_mapa = "Dados de mapa não disponíveis."
        try:
            resp = requests.get(f"{base_url}/api/mapa_clusters", params=params, timeout=20)
            resp.raise_for_status()
            map_data = resp.json()
            if map_data.get("data"):
                resumo_mapa = ""
                shapefile_col = [c for c in map_data["data"][0].keys() if c != "cluster"][0]
                for item in map_data["data"]:
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
        clusters = [p.get("cluster", 0) for p in pca_data]  # pega o cluster de cada ponto

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
    # Mapa temático dos clusters
    # ===============================
    try:
        base_url = f"http://{IP_OR_HOST}:5000"
        params = {
            "inicio": payload.get("inicio", "2003-01-01"),
            "fim": payload.get("fim", "2025-07-31"),
            "municipio": payload.get("municipio", ""),
            "group_by": group_by,  # USA O PARÂMETRO RECEBIDO, NÃO O DO PAYLOAD
            "k": payload.get("k", 4)
        }
        resp = requests.get(f"{base_url}/api/mapa_clusters", params=params, timeout=20)
        if resp.status_code == 200:
            map_json = resp.json()
            map_url = f"{base_url}{map_json.get('mapa_clusters')}"
            if map_url:
                r = requests.get(map_url, timeout=10)
                if r.status_code == 200:
                    caminho = os.path.join(tmp_dir, "mapa_clusters.png")
                    with open(caminho, "wb") as f:
                        f.write(r.content)
                    saved["mapa_clusters"] = caminho
    except Exception as e:
        print(f"[ERRO mapa clusters]: {e}")

    return saved


@app.route('/captcha')
def captcha():
    from captcha.image import ImageCaptcha
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    session['captcha_text'] = captcha_text  # salva no session para validação

    image = ImageCaptcha()
    data = image.generate(captcha_text)
    return send_file(data, mimetype='image/png')


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
    if df.empty:
        return jsonify({"error": "Nenhum dado disponível"}), 404

    medias = {k: int(round(v)) for k, v in df.mean(numeric_only=True).items()}
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

    # 🔹 Filtro por data
    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")
    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]

    # 🔹 Soma letalidade por agrupamento
    df_grouped = df.groupby(group_by)["letalidade_violenta"].sum().reset_index()
    df_grouped[group_by] = df_grouped[group_by].astype(str)
    gdf[shapefile_col] = gdf[shapefile_col].astype(str)
    gdf = gdf.merge(df_grouped, left_on=shapefile_col, right_on=group_by, how="left")
    gdf["letalidade_violenta"] = gdf["letalidade_violenta"].fillna(0)

    # 🔹 Caso o filtro seja por município
    if municipio:
        municipios_gdf = gpd.read_file(SHAPEFILES["mcirc"])
        if municipios_gdf.crs is None:
            municipios_gdf = municipios_gdf.set_crs(epsg=4326)

        # Garante mesmo CRS
        municipios_gdf = municipios_gdf.to_crs(gdf.crs)

        # Seleciona o polígono do município desejado
        municipio_geom = municipios_gdf.loc[municipios_gdf["NM_MUN"] == municipio, "geometry"]
        if not municipio_geom.empty:
            municipio_geom = municipio_geom.iloc[0]

            # 🔹 Recorta o shapefile das CISPs apenas dentro do município
            gdf = gpd.clip(gdf, municipio_geom)

            # Atribui nome do município
            gdf["NM_MUN"] = municipio
        else:
            return jsonify({"error": f"Município '{municipio}' não encontrado no shapefile"}), 404

    # 🔹 Gera o mapa
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

    # 🔹 Prepara os dados para JSON
    gdf["letalidade_violenta"] = gdf["letalidade_violenta"].fillna(0)
    gdf["NM_MUN"] = gdf.get("NM_MUN", "")
    gdf[shapefile_col] = gdf[shapefile_col].fillna("")

    data_saida = gdf[[shapefile_col, "NM_MUN", "letalidade_violenta"]].drop_duplicates().to_dict(orient="records")

    return jsonify({
        "image_url": f"/static/img/{image_name}",
        "data": data_saida
    })

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
                FROM public.dados_previstos
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

@app.route('/api/valores_select', methods=['GET'])
def get_cisps():
    try:
        # Lê o shapefile CISP
        mapa_cisp = gpd.read_file(SHAPEFILES["cisp"])
        coluna_cisp = "cisp"
        codigos_cisp = sorted(mapa_cisp[coluna_cisp].dropna().unique())

        # Lê o shapefile MCIRC
        mapa_mcirc = gpd.read_file(SHAPEFILES["mcirc"])
        coluna_mcirc = "CD_MUN"
        codigos_mcirc = sorted(mapa_mcirc[coluna_mcirc].dropna().unique())

        # ✅ Converte todos os valores para tipos nativos do Python
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
def agrupamentos_data():
    df = load_data()
    k = int(request.args.get("k", 4))
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    municipio = request.args.get("municipio")

    global df_clusters_global, dados_scaled_global, dados_cluster_global

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
    ], errors="ignore")

    print(dados_cluster.columns)

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
    global kmeans
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

    # --- Imagem 1: sem 'registro_ocorrencias' ---
    perfil_img_sem = os.path.join(MAP_FOLDER, f"perfil_medio_sem_registro_ocorrencias_{k}.png")
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    df_cluster_profile.drop(columns=['registro_ocorrencias'], errors='ignore').plot(kind="bar", ax=ax1)
    ax1.set_title("Perfil médio dos clusters (sem registro_ocorrencias)")
    ax1.set_ylabel("Intensidade relativa (normalizada)")
    ax1.set_xticklabels([f"Cluster {i}" for i in df_cluster_profile.drop(columns=['registro_ocorrencias'], errors='ignore').index], rotation=0)
    # Legenda fora do gráfico
    legend1 = ax1.legend(frameon=True, bbox_to_anchor=(1.02, 1), loc='upper left')  # fora à direita
    legend1.get_frame().set_facecolor('none')  # fundo transparente
    plt.tight_layout()
    fig1.savefig(perfil_img_sem, dpi=150, bbox_inches='tight')
    plt.close(fig1)

    # --- Imagem 2: com 'registro_ocorrencias' ---
    perfil_img_com = os.path.join(MAP_FOLDER, f"perfil_medio_com_registro_ocorrencias_{k}.png")
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    df_cluster_profile.plot(kind="bar", ax=ax2)
    ax2.set_title("Perfil médio dos clusters (com registro_ocorrencias)")
    ax2.set_ylabel("Intensidade relativa (normalizada)")
    ax2.set_xticklabels([f"Cluster {i}" for i in df_cluster_profile.index], rotation=0)
    # Legenda fora do gráfico
    legend2 = ax2.legend(frameon=True, bbox_to_anchor=(1.02, 1), loc='upper left')
    legend2.get_frame().set_facecolor('none')
    plt.tight_layout()
    fig2.savefig(perfil_img_com, dpi=150, bbox_inches='tight')
    plt.close(fig2)

    # Importância das variáveis
    importances = {}
    for col in dados_cluster.columns:
        group_means = df.groupby('cluster')[col].mean()
        inter = np.var(group_means)
        intra = np.mean(df.groupby('cluster')[col].var())
        importances[col] = inter / (intra + 1e-6)
    importances_series = pd.Series(importances).sort_values(ascending=False)

    df_clusters_global = df.copy()

    return jsonify({
        "media_clusters": media_clusters,
        "pca_data": pca_data,
        "explained_variance": [round(v, 3) for v in pca.explained_variance_ratio_],
        "perfil_medio_img_sem_registro_ocorrencias": f"/static/img/perfil_medio_sem_registro_ocorrencias_{k}.png",
        "perfil_medio_img_com_registro_ocorrencias": f"/static/img/perfil_medio_com_registro_ocorrencias_{k}.png",
        "perfil_medio_data": df_cluster_profile.to_dict(orient="index"),
        "importancias": importances_series.to_dict()
    })

# cache global para shapefiles já lidos (chave: group_by)
_gdf_cache = {}

# ===========================
# API - Mapa de Clusters
# ===========================
@app.route("/api/mapa_clusters")
def mapa_clusters():
    global kmeans, df_clusters_global  # usa os objetos globais já criados

    if "kmeans" not in globals() or "df_clusters_global" not in globals():
        return jsonify({"error": "Os clusters ainda não foram gerados. Execute /api/agrupamentos_data primeiro."}), 400

    group_by = request.args.get("group_by", "mcirc")
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")

    print(f"Gerando mapa de clusters agrupados por {group_by}...")
    shapefile = SHAPEFILES.get(group_by)
    shapefile_col = COLUMN_MAPPING.get(group_by)
    if not shapefile or not shapefile_col:
        return jsonify({"error": "Agrupamento inválido"}), 400

    # carrega shapefile e garante CRS
    gdf = gpd.read_file(shapefile)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    # copia apenas os clusters calculados anteriormente
    df = df_clusters_global.copy()

    # === Filtros de data (para consistência visual) ===
    df["data"] = pd.to_datetime(df["ano"].astype(str) + "-" + df["mes"].astype(str) + "-01")
    if inicio:
        df = df[df["data"] >= pd.to_datetime(inicio)]
    if fim:
        df = df[df["data"] <= pd.to_datetime(fim)]

    # === Prepara dados agrupados por região ===
    if group_by not in df.columns:
        return jsonify({"error": f"Coluna '{group_by}' não encontrada nos dados."}), 400

    df_grouped = df.groupby(group_by).agg({
        "cluster": lambda x: x.mode()[0] if not x.mode().empty else -1  # cluster predominante
    }).reset_index()

    # === Merge com shapefile ===
    gdf[shapefile_col] = gdf[shapefile_col].astype(str)
    df_grouped[group_by] = df_grouped[group_by].astype(str)
    gdf = gdf.merge(df_grouped, left_on=shapefile_col, right_on=group_by, how="left")
    gdf["cluster"] = gdf["cluster"].fillna(-1).astype(int)

    # === Paleta de cores fixa ===
    default_fixed = {
        0:  "#1f77b4",  # azul forte
        1:  "#ff7f0e",  # laranja vibrante
        2:  "#2ca02c",  # verde médio
        3:  "#d62728",  # vermelho
        4:  "#9467bd",  # roxo
        5:  "#8c564b",  # marrom
        6:  "#e377c2",  # rosa
        7:  "#17becf",  # ciano
        8:  "#bcbd22",  # oliva
        9:  "#7f7f7f",  # cinza neutro
        10: "#000000",  # preto
        11: "#ff1493",  # pink neon
        12: "#228b22",  # verde floresta
        13: "#ffd700",  # amarelo ouro
        14: "#00ffff",  # ciano puro
        15: "#ff4500",  # laranja avermelhado
        16: "#4169e1",  # azul royal
        17: "#ff00ff",  # magenta
        18: "#ff8c00",  # laranja escuro (substitui o verde escuro)
        19: "#a52a2a",  # marrom escuro
        20: "#00ff00",  # verde neon
        21: "#ff6347",  # tomate
        22: "#40e0d0",  # turquesa
        23: "#b22222",  # vermelho ferrugem
        24: "#9932cc",  # roxo violeta
        25: "#ffa500",  # laranja puro
        26: "#4682b4",  # azul aço
        27: "#adff2f",  # verde-limão
        28: "#dc143c",  # carmesim
        29: "#00ced1",  # azul-petróleo
        30: "#8b008b",  # púrpura escuro
        31: "#ff69b4",  # rosa claro
        32: "#9acd32",  # verde amarelado
        33: "#6495ed",  # azul claro
        34: "#ffb6c1",  # rosa bebê
        35: "#8b0000",  # vermelho escuro
        36: "#2f4f4f",  # cinza-azulado escuro
        -1: "#cccccc"   # neutro
    }

    clusters_in_data = sorted(gdf["cluster"].unique())

    fixed_colors = {}
    for cluster in clusters_in_data:
        fixed_colors[cluster] = default_fixed.get(cluster, f"#{np.random.randint(0, 0xFFFFFF):06x}")

    gdf["color"] = gdf["cluster"].map(fixed_colors)

    # === Plot ===
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    gdf.plot(color=gdf["color"], linewidth=0.8, edgecolor='0.8', ax=ax)
    ax.set_axis_off()
    plt.title("Mapa de Clusters de Criminalidade", fontsize=15)

    legend_elements = [
        Patch(facecolor=fixed_colors[i], edgecolor='0.8', label=f"Cluster {i}" if i >= 0 else "Sem dados")
        for i in sorted(fixed_colors.keys())
    ]
    ax.legend(handles=legend_elements, title="Clusters", loc="lower left")

    # nome do arquivo baseado nos filtros
    params_str = f"clusters_{group_by}_{inicio}_{fim}".replace(" ", "_").replace(":", "_")
    image_name = f"{params_str}.png"
    image_path = os.path.join(MAP_FOLDER, image_name)

    plt.savefig(image_path, bbox_inches="tight")
    plt.close(fig)

    return jsonify({"mapa_clusters": f"/static/img/{image_name}", "data": gdf[[shapefile_col, "cluster"]].to_dict(orient="records")})

@app.route("/api/predizer_cluster", methods=["POST"])
def predizer_cluster():
    try:
        data = request.get_json()
        features = data.get("features")
        if not features:
            return jsonify({"error": "Nenhum dado fornecido."}), 400

        k = int(data.get("k", 4))
        feature_names_cluster= [
            'cisp', 'mes', 'ano', 'mcirc', 'letalidade_violenta', 'tentat_hom', 'estupro',
            'lesao_corp_culposa', 'roubo_veiculo', 'estelionato',
            'apreensao_drogas', 'trafico_drogas', 'apf',
            'pessoas_desaparecidas', 'encontro_cadaver', 'registro_ocorrencias'
        ]
        # Prepara os dados do usuário
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
# Rota principal: gera o PDF e retorna
# ----------------------------
@app.route("/api/export_dashboard_pdf")
def export_dashboard_pdf():
    inicio = request.args.get("inicio") or "2003-01-01"
    fim = request.args.get("fim") or "2025-07-31"
    municipio = request.args.get("municipio")
    group_by = request.args.get("group_by") or "mcirc"
    params = {"inicio":inicio,"fim":fim,"municipio":municipio,"group_by":group_by}

    # 1) Obter dados do dashboard
    try:
        base_url = request.url_root.rstrip('/')
        response = requests.get(f"{base_url}/api/dashboard_data", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        print(f"[ERRO API /dashboard_data] {e}")
        return jsonify({"erro":str(e)}), 500

    # 2) Gerar descrições automáticas
    try:
        descricoes = gerar_descricoes_dashboard(payload, group_by)
    except:
        descricoes = {
            "linha_evolucao": "Consulte o gráfico de evolução temporal.",
            "barras_correlacao": "Consulte o gráfico de correlações.",
            "scatter": "Consulte o gráfico de dispersão.",
            "mapa": "Consulte o mapa temático."
        }

    # 3) Criar PDF
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_imgs = criar_graficos_temp_dashboard(payload,tmpdir,group_by)
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # Cabeçalho
            story.append(Paragraph("<b>Relatório do Dashboard - Monitor de Criminalidade RJ</b>", styles["Title"]))
            story.append(Spacer(1,12))
            story.append(Paragraph(f"<b>Período:</b> {params['inicio']} – {params['fim']}", styles["Normal"]))
            story.append(Paragraph(f"<b>Município:</b> {params['municipio'] or 'Todos'}", styles["Normal"]))
            story.append(Spacer(1,20))

            # KPIs principais
            story.append(Paragraph("<b>Indicadores Principais</b>", styles["Heading2"]))
            story.append(Paragraph(f"• Letalidade Violenta Total: {payload.get('letalidade_violenta_total',0)}", styles["Normal"]))
            story.append(Paragraph(f"• Homicídios Dolosos (média): {payload.get('homicidios_dolosos',0)}", styles["Normal"]))
            story.append(Paragraph(f"• Soma de latrocínios: {payload.get('latrocinios',0)}", styles["Normal"]))
            story.append(Paragraph(f"• Homícidios Por Intervenção Policial: {payload.get('mortes_intervencao_policial',0)}", styles["Normal"]))
            story.append(Spacer(1,20))

            # Seções
            sections = [
                ("linha_evolucao","Evolução Temporal da Letalidade Violenta"),
                ("barras_correlacao","Correlação entre Crimes e Letalidade"),
                ("scatter","Relação entre Roubo na Rua e Letalidade"),
                ("mapa","Distribuição Geográfica da Letalidade")
            ]

            for chave,titulo in sections:
                story.append(Paragraph(f"<b>{titulo}</b>", styles["Heading2"]))
                story.append(Spacer(1,6))
                story.append(Paragraph(descricoes.get(chave,"Análise não disponível."), styles["Normal"]))
                story.append(Spacer(1,8))
                if saved_imgs.get(chave):
                    story.append(Image(saved_imgs[chave], width=480, height=240 if chave!="scatter" else 300))
                story.append(Spacer(1,16))

            story.append(Spacer(1,20))
            story.append(Paragraph("<i>Relatório gerado automaticamente com IA (LLaMA 3) - Monitor RJ.</i>", styles["Normal"]))

            doc.build(story)
            buffer.seek(0)
            nome_pdf = f"relatorio_dashboard_{params.get('inicio','sem_data')}.pdf"
            return send_file(buffer, as_attachment=True, download_name=nome_pdf, mimetype="application/pdf")
    except Exception as e:
        print(f"[ERRO PDF] {e}")
        return jsonify({"erro":"Falha ao gerar PDF"}), 500

@app.route("/api/export_agrupamentos_pdf")
def export_agrupamentos_pdf():
    inicio = request.args.get("inicio") or "2003-01-01"
    fim = request.args.get("fim") or "2025-07-31"
    municipio = request.args.get("municipio")
    group_by = request.args.get("group_by") or "mcirc"
    k = request.args.get("k") or 4
    params = {"inicio":inicio,"fim":fim,"municipio":municipio,"group_by":group_by, "k": k}

    # 1) Obter dados dos agrupamentos
    try:
        base_url = request.url_root.rstrip('/')
        response = requests.get(f"{base_url}/api/agrupamentos_data", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        print(f"[ERRO API /agrupamentos_data] {e}")
        return jsonify({"erro":str(e)}), 500

    # 2) Gerar descrições automáticas
    try:
        descricoes = gerar_descricoes_agrupamentos(payload, group_by)
    except:
        descricoes = {
            "scatter_pca": "Consulte o gráfico de projeção PCA.",
            "perfil_medio_clusters": "Consulte o gráfico de perfil médio dos clusters.",
            "importancia_variaveis": "Consulte o gráfico de importância das variáveis.",
            "mapa_clusters": "Consulte o mapa temático dos clusters."
        }

    # 3) Criar PDF
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_imgs = criar_graficos_temp_agrupamentos(payload,tmpdir,group_by)
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # Cabeçalho
            story.append(Paragraph("<b>Relatório de Agrupamentos - Monitor de Criminalidade RJ</b>", styles["Title"]))
            story.append(Spacer(1,12))
            story.append(Paragraph(f"<b>Período:</b> {params['inicio']} – {params['fim']}", styles["Normal"]))
            story.append(Paragraph(f"<b>Município:</b> {params['municipio'] or 'Todos'}", styles["Normal"]))
            story.append(Spacer(1,20))

            # Seções
            sections = [
                ("scatter_pca","Projeção PCA dos Clusters"),
                ("perfil_medio_clusters","Perfil Médio dos Clusters"),
                ("importancia_variaveis","Importância das Variáveis nos Clusters"),
                ("mapa_clusters","Mapa Temático dos Clusters")
            ]

            for chave,titulo in sections:
                story.append(Paragraph(f"<b>{titulo}</b>", styles["Heading2"]))
                story.append(Spacer(1,6))
                story.append(Paragraph(descricoes.get(chave,"Análise não disponível."), styles["Normal"]))
                story.append(Spacer(1,8))
                if saved_imgs.get(chave):
                    story.append(Image(saved_imgs[chave], width=480, height=240))
                story.append(Spacer(1,16))

            story.append(Spacer(1,20))
            story.append(Paragraph("<i>Relatório gerado automaticamente com IA (LLaMA 3) - Monitor RJ.</i>", styles["Normal"]))

            doc.build(story)
            buffer.seek(0)
            nome_pdf = f"relatorio_agrupamentos.pdf"
            return send_file(buffer, as_attachment=True, download_name=nome_pdf, mimetype="application/pdf")
    except Exception as e:
        print(f"[ERRO PDF AGRUPAMENTOS] {e}")
        return jsonify({"erro":"Falha ao gerar PDF"}), 500

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_captcha = request.form.get('captcha', '').upper()  # pega captcha digitado

        # validação do captcha
        if user_captcha != session.get('captcha_text', ''):
            flash("Captcha incorreto!")
            return redirect(url_for('login'))

        
        # Conectar ao banco de dados
        conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST,
                port=DB_PORT
            )
        from db import get_connection

        conn = get_connection()
        cur = conn.cursor()
        # validação do usuário no banco
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
        user = cur.fetchone()
        if not user:
            flash("Usuário ou senha incorretos!")
            return redirect(url_for('login'))

        # login bem-sucedido
        session['user_id'] = user[0]
        flash("Login realizado com sucesso!")
        return redirect(url_for('index'))

    return render_template('login.html')
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
 
        # Validação simples de senha
        if password != confirm_password:
            flash("As senhas não coincidem!")
            return redirect(url_for("cadastro"))
 
        try:
            conn = get_connection()
            cur = conn.cursor()
           
            # Inserção na tabela users
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
            # Caso tente inserir email ou username duplicado
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
            user_captcha = request.form.get('captcha', '').upper()  # pega captcha digitado
 
            # validação do captcha
            if user_captcha != session.get('captcha_text', ''):
                flash("Captcha incorreto!")
                return redirect(url_for('login'))
 
           
            # Conectar ao banco de dados
            conn = psycopg2.connect(
                    dbname=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    host=DB_HOST,
                    port=DB_PORT
                )
            from db import get_connection
 
            conn = get_connection()
            cur = conn.cursor()
            # validação do usuário no banco
            cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
            user = cur.fetchone()
            if not user:
                flash("Usuário ou senha incorretos!")
                return redirect(url_for('login'))
 
            # login bem-sucedido
            session['user_id'] = user[0]
            flash("Login realizado com sucesso!")
            return redirect(url_for('index'))
 
        return render_template('login.html')

def gerar_descricoes_previsao(payload):
    """
    Gera descrições automáticas para a página de previsão.
    Agora o prompt de soma e média foi unificado.
    """
    descricoes = {
        "historico": "Análise não disponível.",
        "feature_importance": "Análise não disponível.",
        "intervalo_confianca": "Análise não disponível.",
        "soma_media_comparacao": "Análise não disponível."
    }

    try:
        # =====================
        # HISTÓRICO E PREVISÃO
        # =====================
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
Analise a seguinte previsão de criminalidade e produza uma resposta curta (3-4 frases) em português:

[PREVISÃO DE CRIMINALIDADE]
{resumo_historico}
"""
        descricoes["historico"] = gerar_texto_gpt4o(prompt_historico)

        # =====================
        # IMPORTÂNCIA DAS FEATURES
        # =====================
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

        # =====================
        # INTERVALO DE CONFIANÇA
        # =====================
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

        # =====================
        # COMPARAÇÃO UNIFICADA (SOMA + MÉDIA)
        # =====================
        soma_hist = sum(payload.get("historico_valores", []))
        soma_prev = sum(payload.get("prev_valores", []))
        media_hist = np.mean(payload.get("historico_valores", [])) if payload.get("historico_valores") else 0
        media_prev = np.mean(payload.get("prev_valores", [])) if payload.get("prev_valores") else 0

        prompt_soma_media = f"""
Você é um analista de segurança pública.
Compare o comportamento da letalidade violenta entre o histórico e as previsões,
considerando tanto a soma total quanto a média mensal dos casos.
Explique brevemente se há tendência de aumento, estabilidade ou redução,
e interprete o que isso pode significar para o cenário de segurança.

[SOMA E MÉDIA]
Soma - Histórico: {soma_hist:.1f} | Previsões: {soma_prev:.1f}
Média - Histórico: {media_hist:.1f} | Previsões: {media_prev:.1f}
"""
        descricoes["soma_media_comparacao"] = gerar_texto_gpt4o(prompt_soma_media)

        return descricoes

    except Exception as e:
        print(f"Erro ao gerar descrições de previsão: {e}")
        return descricoes


def criar_graficos_temp_previsao(payload, tmp_dir):
    """
    Cria dois gráficos:
      1. Histórico vs Previsões (Soma e Média ao longo do tempo)
      2. Contribuição por Fator (importância das variáveis)
    """
    saved = {}

    historico = payload.get("historico_valores", [])
    previsoes = payload.get("prev_valores", [])
    media_hist = payload.get("media_historica_valores", [])
    media_prev = payload.get("media_previsoes_valores", [])
    labels_hist = payload.get("historico_labels", [])
    feature_importance = payload.get("feature_importance", {})

    print("historicos_valores: ", historico)
    print("prev_valores: ", previsoes)
    print("media_hist: ", media_hist)
    print("media_prev: ", media_prev)
    print("labels_hist: ", labels_hist)

    # ===============================
    # 1️⃣ Gráfico: Histórico vs Previsões — Soma e Média
    # ===============================
    if historico:
        plt.figure(figsize=(10, 6))

        # Série 1: soma histórica
        plt.plot(labels_hist, historico, label="Soma Histórica", linewidth=2)

        # Série 2: soma prevista (se existir)
        if previsoes:
            plt.plot(labels_hist[-len(previsoes):], previsoes,
                     label="Soma Prevista", linestyle="--", linewidth=2)

        # Série 3: médias (só adiciona se existirem)
        if media_hist:
            plt.plot(labels_hist, media_hist, label="Média Histórica", linewidth=2, alpha=0.7)
        if media_prev:
            plt.plot(labels_hist[-len(media_prev):], media_prev,
                     label="Média Prevista", linestyle="--", linewidth=2, alpha=0.7)

        plt.title("Histórico vs Previsões — Soma e Média ao longo do tempo", fontsize=14)
        plt.xlabel("Período (Ano-Mês)")
        plt.ylabel("Número de Casos")
        plt.legend()
        plt.grid(True, linestyle="--", alpha=0.6)

        # --- 🔹 Mostrar apenas alguns rótulos no eixo X ---
        if len(labels_hist) > 12:
            passo = max(1, len(labels_hist) // 12)  # mostra ~12 rótulos no máximo
            plt.xticks(range(0, len(labels_hist), passo), labels_hist[::passo], rotation=45, ha='right')
        else:
            plt.xticks(range(len(labels_hist)), labels_hist, rotation=45, ha='right')

        plt.tight_layout()

        caminho = os.path.join(tmp_dir, "historico_previsoes_soma_media.png")
        plt.savefig(caminho, dpi=150)
        plt.close()
        saved["historico_previsoes_soma_media"] = caminho

    # ===============================
    # 2️⃣ Gráfico: Contribuição por Fator
    # ===============================
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
def export_previsao_pdf():
    payload = request.get_json()

    # --- 1️⃣ Gera análises textuais ---
    descricoes = gerar_descricoes_previsao(payload)

    # --- 2️⃣ Gera gráficos temporários ---
    tmp_dir = tempfile.mkdtemp()
    try:
        print(payload)
        graficos = criar_graficos_temp_previsao(payload, tmp_dir)
        print(graficos)
    except Exception as e:
        print("Erro ao criar gráficos temporários:", e)
        graficos = {}

    # --- 3️⃣ Cria o PDF ---
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    story = []

    # === Cabeçalho ===
    story.append(Paragraph("<b>Relatório de Previsão de Letalidade Violenta</b>", styles["Title"]))
    story.append(Spacer(1, 8))

    # ----------------------------
    # Aqui: insere os valores de todas as variáveis (no início do PDF)
    # ----------------------------
    # Primeiro tenta obter features_dict diretamente do payload (ideal, vindo do frontend)
    features_dict = payload.get("features_dict")
    # Se não existir, tenta reconstruir a partir de payload["features"] e feature_names (caso feature_names esteja no escopo)
    if not features_dict:
        features_list = payload.get("features") or payload.get("features_array") or []
        try:
            # feature_names deve existir no módulo (definido no servidor)
            features_dict = dict(zip(feature_names, features_list))
        except Exception:
            # fallback: cria chaves genéricas
            features_dict = {f"feature_{i}": v for i, v in enumerate(features_list)}

    # Título da seção de variáveis
    story.append(Paragraph("<b>Valores das Variáveis (entrada)</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))

    # Constrói uma tabela com duas colunas: variável | valor
    table_data = [["Variável", "Valor"]]
    # Garante ordem estável (ordenamos pela chave para previsibilidade)
    for k in sorted(features_dict.keys()):
        # Formata números com 3 casas decimais quando forem float/numéricos
        v = features_dict[k]
        if isinstance(v, float):
            v_str = f"{v:.3f}"
        else:
            v_str = str(v)
        table_data.append([k.replace('_', ' '), v_str])

    # Cria Table com estilo simples
    tbl = Table(table_data, colWidths=[200, 200])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f2f2f2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('BOX', (0,0), (-1,-1), 0.25, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 12))

    story.append(Paragraph(f"Previsão: {payload.get('previsao_leitura', '-')}", styles["Normal"]))
    story.append(Paragraph(f"Intervalo 95%: {payload.get('intervalo_95', '-')}", styles["Normal"]))
    story.append(Paragraph(f"Tendência: {payload.get('tendencia', '-')}", styles["Normal"]))
    story.append(Paragraph(f"Risco: {payload.get('risco', '-')}", styles["Normal"]))
    story.append(Spacer(1, 12))
    
    # --- Drivers principais (colocar logo após os valores) ---
    drivers = payload.get("drivers", [])
    story.append(Paragraph("<b>Drivers Principais</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))
    if drivers:
        # se for lista, coloca em bullets; se string, só imprime
        if isinstance(drivers, (list, tuple)):
            for d in drivers:
                story.append(Paragraph(f"• {d}", styles["Normal"]))
        else:
            story.append(Paragraph(str(drivers), styles["Normal"]))
    else:
        story.append(Paragraph("Nenhum driver identificado.", styles["Normal"]))
    story.append(Spacer(1, 12))

    # === Análise textual ===
    story.append(Paragraph("<b>Análise da Previsão</b>", styles["Heading2"]))
    story.append(Paragraph(descricoes.get("historico", "—"), styles["Normal"]))
    story.append(Spacer(1, 12))

    # === Importância das Variáveis (gráfico) ===
    story.append(Paragraph("<b>Importância das Variáveis / Contribuição por Fator</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))
    if "feature_importance" in graficos:
        try:
            story.append(Image(graficos["feature_importance"], width=450, height=300))
            story.append(Spacer(1, 10))
        except Exception as e:
            print("Erro ao adicionar imagem feature_importance:", e)
    # também escreve o resumo textual gerado
    story.append(Paragraph(descricoes.get("feature_importance", "—"), styles["Normal"]))
    story.append(Spacer(1, 12))

    # === Intervalo de confiança ===
    story.append(Paragraph("<b>Intervalo de Confiança</b>", styles["Heading2"]))
    story.append(Paragraph(descricoes.get("intervalo_confianca", "—"), styles["Normal"]))
    story.append(Spacer(1, 12))

    # === Gráfico único: Histórico vs Previsões (Soma e Média) ===
    if "historico_previsoes_soma_media" in graficos:
      story.append(Paragraph("<b>Histórico vs Previsões — Soma e Média ao longo do tempo</b>", styles["Heading2"]))
      story.append(Image(graficos["historico_previsoes_soma_media"], width=450, height=300))
      story.append(Spacer(1, 6))
      story.append(Paragraph(descricoes.get("soma_media_comparacao", "—"), styles["Normal"]))
      story.append(Spacer(1, 12))

    # Finaliza documento
    doc.build(story)

    buffer.seek(0)

    # Limpa arquivos temporários
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass

    return send_file(buffer, as_attachment=True, download_name='relatorio_previsao.pdf', mimetype='application/pdf')
  
# ===========================
# Main
# ===========================
if __name__ == "__main__":
    app.run(host=IP_OR_HOST, port=5000, debug=True)
