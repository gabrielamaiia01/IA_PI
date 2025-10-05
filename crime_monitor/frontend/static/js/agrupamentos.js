let chartInstance = null;
let municipios = [];

document.addEventListener("DOMContentLoaded", async () => {
    const inputMunicipio = document.getElementById("municipio");
    const datalist = document.getElementById("lista-municipios");
    const mapImg = document.getElementById("map-img"); // caso tenha mapa

    // ===========================
    // Carregar municípios
    // ===========================
    try {
        const response = await fetch("/api/municipios");
        municipios = await response.json();
    } catch (err) {
        console.error("Erro ao carregar municípios:", err);
    }

    // Preencher datalist conforme o usuário digita
    inputMunicipio.addEventListener("input", () => {
        const valor = inputMunicipio.value.toLowerCase();
        datalist.innerHTML = "";
        municipios
            .filter(m => m.toLowerCase().startsWith(valor))
            .forEach(m => {
                const option = document.createElement("option");
                option.value = m;
                datalist.appendChild(option);
            });
    });

    // ===========================
    // Função para gerar gráficos
    // ===========================
    async function gerarGraficos() {
        const k = document.getElementById("num-clusters").value;
        const inicio = document.getElementById("data-inicio").value;
        const fim = document.getElementById("data-fim").value;
        const municipio = inputMunicipio.value;

        try {
            const params = new URLSearchParams();
            params.append("k", k);
            if (inicio) params.append("inicio", inicio);
            if (fim) params.append("fim", fim);
            if (municipio) params.append("municipio", municipio);

            const res = await fetch(`/api/agrupamentos_data?${params.toString()}`);
            const data = await res.json();

            if (data.error) {
                alert(data.error);
                return;
            }

            // ===========================
            // PCA Scatter
            // ===========================
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

            // Atualiza imagens do backend
            if (document.getElementById("cluster-profile") && data.perfil_medio_img)
                document.getElementById("cluster-profile").src = `${data.perfil_medio_img}?v=${new Date().getTime()}`;
            if (document.getElementById("elbow-plot") && data.cotovelo_img)
                document.getElementById("elbow-plot").src = `${data.cotovelo_img}?v=${new Date().getTime()}`;

        } catch (err) {
            console.error("Erro ao carregar dados de agrupamento:", err);
            alert("Erro ao carregar dados. Veja o console para detalhes.");
        }
    }

    // ===========================
    // Função para atualizar mapa (opcional)
    // ===========================
    async function loadMapImage() {
        if (!mapImg) return;

        const inicio = document.getElementById("data-inicio")?.value;
        const fim = document.getElementById("data-fim")?.value;
        const municipio = inputMunicipio.value;

        const params = new URLSearchParams();
        if (inicio) params.append("inicio", inicio);
        if (fim) params.append("fim", fim);
        if (municipio) params.append("municipio", municipio);

        try {
            const response = await fetch(`/api/map_image/mcirc?${params.toString()}`);
            const data = await response.json();
            if (data.image_url) mapImg.src = data.image_url;
        } catch (err) {
            console.error("Erro ao carregar mapa:", err);
        }
    }

    // ===========================
    // Aplicar filtros
    // ===========================
    async function aplicarFiltros() {
        const municipioValido = municipios.find(
            m => m.toLowerCase() === inputMunicipio.value.toLowerCase()
        );

        // Só aplica se o município for válido ou vazio
        if (municipioValido || inputMunicipio.value === "") {
            await gerarGraficos();
            await loadMapImage();
        } else {
            alert("Município inválido. Selecione um da lista.");
        }
    }

    // ===========================
    // Evento apenas no botão “Aplicar”
    // ===========================
    document.getElementById("btn-aplicar").addEventListener("click", aplicarFiltros);

    // ===========================
    // Exportar PCA como PDF
    // ===========================
    document.getElementById("btn-export-pdf").addEventListener("click", async () => {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF("landscape", "px", "a4");
        const margin = 10;
        const pageWidth = pdf.internal.pageSize.getWidth() - margin * 2;
        let yOffset = margin;

        // Seleciona todos os gráficos que você quer exportar
        const elementos = document.querySelectorAll("canvas, #cluster-profile, #elbow-plot");

        for (let el of elementos) {
            try {
                const canvasImg = await html2canvas(el, { scale: 2 });
                const imgData = canvasImg.toDataURL("image/png");
                const imgProps = pdf.getImageProperties(imgData);
                const pdfWidth = pageWidth;
                const pdfHeight = (imgProps.height * pdfWidth) / imgProps.width;

                if (yOffset + pdfHeight > pdf.internal.pageSize.getHeight()) {
                    pdf.addPage();
                    yOffset = margin;
                }

                pdf.addImage(imgData, "PNG", margin, yOffset, pdfWidth, pdfHeight);
                yOffset += pdfHeight + 10;
            } catch (err) {
                console.error("Erro ao capturar elemento para PDF:", err);
            }
        }

        pdf.save("dashboard.pdf");
    });

});
