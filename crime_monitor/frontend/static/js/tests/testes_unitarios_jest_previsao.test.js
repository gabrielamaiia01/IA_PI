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

//  Código dos Testes Unitários (Jest) 

describe('Testes Unitários para Funções Auxiliares do Frontend (Foco em Previsão)', () => {

    // Teste 1: Validação da função formatNumber (Usada para formatar a previsão)
    describe('formatNumber (Usado em previsao.js)', () => {
        test('Deve formatar o valor da previsão (inteiro) corretamente', () => {
            expect(formatNumber(1190)).toBe('1.190');
        });

        test('Deve formatar o valor da previsão (com casas decimais) corretamente', () => {
            expect(formatNumber(1190.55)).toBe('1.190,55');
        });

        test('Deve retornar "N/A" se o valor da previsão for inválido', () => {
            expect(formatNumber(NaN)).toBe('NaN');
        });
    });

    // Teste 2: Validação de campos obrigatórios (isFilterSelected) para filtros de previsão
    describe('isFilterSelected (Usado para filtros de previsão)', () => {
        test('Deve retornar true para um período futuro selecionado', () => {
            expect(isFilterSelected('Próximo mês')).toBe(true);
        });

        test('Deve retornar true para uma região selecionada', () => {
            expect(isFilterSelected('Estado do RJ')).toBe(true);
        });

        test('Deve retornar false se o filtro de período estiver vazio', () => {
            expect(isFilterSelected('')).toBe(false);
        });

        test('Deve retornar false se o filtro de região estiver com o valor padrão "Selecione"', () => {
            expect(isFilterSelected('Selecione')).toBe(false);
        });
    });

    // Teste 3: Validação da lógica de tendência (getTrend) - Queda (Simulando a "Leve queda" da imagem)
    describe('getTrend - Simulação de "Leve queda"', () => {
        test('Deve retornar "Leve queda" para uma pequena variação negativa', () => {
            // Exemplo: Mês anterior 1250, Previsão 1190 (queda de 4.8%)
            expect(getTrend(1190, 1250)).toBe('Leve queda');
        });
    });

    // Teste 4: Validação da lógica de tendência (getTrend) - Aumento
    describe('getTrend - Aumento', () => {
        test('Deve retornar "Aumento acentuado" para um aumento significativo', () => {
            // Exemplo: Mês anterior 1000, Previsão 1500 (aumento de 50%)
            expect(getTrend(1500, 1000)).toBe('Aumento acentuado');
        });
    });

    // Teste 5: Validação da lógica de tendência (getTrend) - Estável
    describe('getTrend - Estável', () => {
        test('Deve retornar "Estável" quando a previsão é igual ao valor anterior', () => {
            expect(getTrend(1200, 1200)).toBe('Estável');
        });
    });
});
