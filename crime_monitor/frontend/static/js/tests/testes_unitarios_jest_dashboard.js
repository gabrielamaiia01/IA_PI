function formatNumber(number) {
    if (typeof number !== 'number') {
        return 'N/A';
    }
    // Simulação da formatação pt-BR
    return number.toLocaleString('pt-BR', { maximumFractionDigits: 2 });
}

function isFilterSelected(value) {
    return value !== null && value !== undefined && value !== '' && value !== 'Selecione';
}

function getTrend(currentValue, previousValue) {
    if (currentValue === previousValue) {
        return 'Estável';
    }
    if (currentValue < previousValue) {
        const diff = previousValue - currentValue;
        const percentage = (diff / previousValue) * 100;
        if (percentage > 5) {
            return 'Queda acentuada';
        }
        return 'Leve queda';
    }
   
    const diff = currentValue - previousValue;
    const percentage = (diff / previousValue) * 100;
    if (percentage > 5) {
        return 'Aumento acentuado';
    }
    return 'Leve aumento';
}

// Código dos Testes Unitários (Jest) 

describe('Testes Unitários para Funções Auxiliares do Frontend (Foco em Dashboard)', () => {

    // Teste 1: Validação da função formatNumber (Usada para formatar os KPIs do Dashboard)
    describe('formatNumber (Usado em dashboard.js para KPIs)', () => {
        test('Deve formatar o KPI de Letalidade Violenta Total (1.238) corretamente', () => {
            expect(formatNumber(1238)).toBe('1.238');
        });

        test('Deve formatar o KPI de Homicídios Dolosos (842) corretamente', () => {
            expect(formatNumber(842)).toBe('842');
        });

        test('Deve formatar o KPI de Mortes por Intervenção Policial (339) corretamente', () => {
            expect(formatNumber(339)).toBe('339');
        });

        test('Deve retornar "N/A" se o valor do KPI for nulo', () => {
            expect(formatNumber(null)).toBe('N/A');
        });
    });

    // Teste 2: Validação de campos obrigatórios (isFilterSelected) para filtros do Dashboard
    describe('isFilterSelected (Usado para filtros do Dashboard)', () => {
        test('Deve retornar true para um período selecionado', () => {
            expect(isFilterSelected('2024/01')).toBe(true);
        });

        test('Deve retornar true para uma região selecionada', () => {
            expect(isFilterSelected('Centro')).toBe(true);
        });

        test('Deve retornar false se o filtro de período estiver vazio', () => {
            expect(isFilterSelected('')).toBe(false);
        });

        test('Deve retornar false se o filtro de região estiver com o valor padrão "Selecione"', () => {
            expect(isFilterSelected('Selecione')).toBe(false);
        });
    });

    // Teste 3: Validação da lógica de tendência (getTrend) - Queda (Simulando o "-3%" da imagem)
    describe('getTrend - Simulação de "-3%" (Leve queda)', () => {
        test('Deve retornar "Leve queda" para uma variação de -3%', () => {
            // Exemplo: Mês anterior 1000, Mês atual 970 (queda de 3%)
            expect(getTrend(970, 1000)).toBe('Leve queda');
        });
    });

    // Teste 4: Validação da lógica de tendência (getTrend) - Aumento (Simulando o "+2%" da imagem)
    describe('getTrend - Simulação de "+2%" (Leve aumento)', () => {
        test('Deve retornar "Leve aumento" para uma variação de +2%', () => {
            // Exemplo: Ano anterior 1000, Ano atual 1020 (aumento de 2%)
            expect(getTrend(1020, 1000)).toBe('Leve aumento');
        });
    });

    // Teste 5: Validação da lógica de tendência (getTrend) - Estável (Simulando a "tendência: estável" da imagem)
    describe('getTrend - Simulação de "Estável"', () => {
        test('Deve retornar "Estável" quando a variação é zero', () => {
            expect(getTrend(500, 500)).toBe('Estável');
        });
    });
});
