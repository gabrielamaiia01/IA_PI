
from flask import Flask, render_template, jsonify, request
import pandas as pd
import os

app = Flask(__name__, static_folder='../frontend/static', template_folder='../frontend/pages')

DATA_PATH = 'data/crime_data.csv'

def load_data():
    if os.path.exists(DATA_PATH):
        return pd.read_csv(DATA_PATH)
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

    # For simplicity, let's aggregate the latest month's data for now
    # In a real application, this would involve filtering by period/region
    latest_data = df.iloc[-1] # Get the last row as latest data

    data = {
        "letalidade_violenta_total": int(latest_data["Letalidade_Violenta_Total"]),
        "homicidios_dolosos": int(latest_data["Homicidios_Dolosos"]),
        "latrocinios": int(latest_data["Latrocinios"]),
        "mortes_intervencao_policial": int(latest_data["Mortes_Intervencao_Policial"]),
        "evolucao_temporal": [], # Placeholder for chart data
        "correlacao_crimes": [] # Placeholder for chart data
    }
    return jsonify(data)

@app.route('/api/previsao_data')
def previsao_data():
    # Mock data for now
    data = {
        "previsao_proxima_leitura": 1190,
        "intervalo_95": "1.120 - 1.260",
        "tendencia": "Leve queda",
        "detalhes_previsao": "Com base em séries temporais e correlações. Drivers principais: queda de roubos de rua (-4%), sazonalidade pós-feriado, operações policiais estáveis."
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)

