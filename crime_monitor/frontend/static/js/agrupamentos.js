let chartInstance = null;

async function gerarGraficos() {
    const k = document.getElementById("num-clusters").value;

    try {
        const res = await fetch(`/api/agrupamentos_data?k=${k}`);
        const data = await res.json();

        if (data.error) { 
            alert(data.error); 
            return; 
        }

        // -------------------------
        // Atualiza métricas
        // -------------------------
        document.getElementById("metric-silhouette").textContent = data.silhouette;
        document.getElementById("metric-ch").textContent = data.calinski_harabasz;
        document.getElementById("metric-db").textContent = data.davies_bouldin;

        // -------------------------
        // PCA Scatter
        // -------------------------
        const canvas = document.getElementById("pca-scatter");
        const ctx = canvas.getContext("2d");

        const clustersUnicos = [...new Set(data.pca_data.map(d => d.cluster))];
        const datasets = clustersUnicos.map(c => ({
            label: `Cluster ${c}`,
            data: data.pca_data
                     .filter(d => d.cluster === c)
                     .map(p => ({ x: p.pca1, y: p.pca2 })),
            pointRadius: 4,
            backgroundColor: `hsl(${(c * 60) % 360}, 70%, 50%)`
        }));

        if (chartInstance) chartInstance.destroy();

        chartInstance = new Chart(ctx, {
            type: "scatter",
            data: { datasets },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: "right" },
                    title: { display: true, text: "Distribuição dos Clusters (PCA 2D)" }
                },
                scales: {
                    x: { title: { display: true, text: "Componente Principal 1" } },
                    y: { title: { display: true, text: "Componente Principal 2" } }
                }
            }
        });

        // -------------------------
        // Atualiza imagens do backend
        // -------------------------
        document.getElementById("cluster-profile").src = `${data.perfil_medio_img}?v=${new Date().getTime()}`;
        document.getElementById("elbow-plot").src = `${data.cotovelo_img}?v=${new Date().getTime()}`;

    } catch (err) {
        console.error("Erro ao carregar dados de agrupamento:", err);
        alert("Erro ao carregar dados. Veja o console para detalhes.");
    }
}

// -------------------------
// Exporta PCA como PDF
// -------------------------
document.getElementById("btn-export-pdf").addEventListener("click", async () => {
    const canvas = document.getElementById("pca-scatter");
    if (!canvas) return;

    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ orientation: "landscape", unit: "px", format: [canvas.width, canvas.height] });
    await pdf.html(canvas.parentNode, {
        callback: doc => doc.save("PCA_Clusters.pdf"),
        x: 0,
        y: 0
    });
});

// -------------------------
// Eventos
// -------------------------
document.getElementById("btn-aplicar").addEventListener("click", gerarGraficos);
document.addEventListener("DOMContentLoaded", gerarGraficos);
