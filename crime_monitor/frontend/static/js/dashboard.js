
document.addEventListener("DOMContentLoaded", function() {
    fetch("/api/dashboard_data")
        .then(response => response.json())
        .then(data => {
            document.getElementById("total_letalidade").textContent = data.letalidade_violenta_total.toLocaleString("pt-BR");
            document.getElementById("homicidios_dolosos").textContent = data.homicidios_dolosos.toLocaleString("pt-BR");
            document.getElementById("latrocinios").textContent = data.latrocinios.toLocaleString("pt-BR");
            document.getElementById("mortes_policial").textContent = data.mortes_intervencao_policial.toLocaleString("pt-BR");
            // Chart data will be rendered here using a charting library (e.g., Chart.js, D3.js)
            // For now, we just update the KPIs
        })
        .catch(error => console.error("Erro ao buscar dados do dashboard:", error));
});

