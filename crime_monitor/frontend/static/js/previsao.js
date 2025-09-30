
document.addEventListener("DOMContentLoaded", function() {
    fetch("/api/previsao_data")
        .then(response => response.json())
        .then(data => {
            document.getElementById("previsao_proxima_leitura").textContent = data.previsao_proxima_leitura.toLocaleString("pt-BR");
            document.getElementById("intervalo_95").textContent = data.intervalo_95;
            document.getElementById("tendencia").textContent = data.tendencia;
            document.getElementById("previsao_leitura").textContent = data.previsao_proxima_leitura.toLocaleString("pt-BR");
            document.getElementById("detalhes_previsao").textContent = data.detalhes_previsao;
            // Chart data will be rendered here using a charting library (e.g., Chart.js, D3.js)
        })
        .catch(error => console.error("Erro ao buscar dados de previsão:", error));
});

