/**
 * Agrupa um array de objetos por uma chave específica.
 * @param {Array<Object>} data - O array de dados.
 * @param {string} key - A chave pela qual agrupar.
 * @returns {Object} Um objeto onde as chaves são os valores da chave e os valores são arrays de objetos.
 */
function groupDataByKey(data, key) {
    if (!Array.isArray(data) || data.length === 0) {
        return {};
    }
    return data.reduce((acc, item) => {
        const groupKey = item[key];
        if (!acc[groupKey]) {
            acc[groupKey] = [];
        }
        acc[groupKey].push(item);
        return acc;
    }, {});
}

/**
 * Calcula a soma de uma coluna numérica em um array de objetos.
 * @param {Array<Object>} data - O array de dados.
 * @param {string} column - O nome da coluna a ser somada.
 * @returns {number} A soma total.
 */
function calculateSum(data, column) {
    if (!Array.isArray(data) || data.length === 0) {
        return 0;
    }
    return data.reduce((sum, item) => sum + (item[column] || 0), 0);
}

/**
 * Filtra um array de objetos com base em uma chave e um valor.
 * @param {Array<Object>} data - O array de dados.
 * @param {string} key - A chave para filtrar.
 * @param {*} value - O valor que a chave deve ter.
 * @returns {Array<Object>} O array de objetos filtrado.
 */
function filterData(data, key, value) {
    if (!Array.isArray(data) || data.length === 0) {
        return [];
    }
    return data.filter(item => item[key] === value);
}

//  Código dos Testes Unitários (Jest) 

describe('Testes Unitários para Funções de Agrupamento e Manipulação de Dados', () => {

    const mockData = [
        { mes: 'Jan', regiao: 'Centro', letalidade: 100, roubo: 50 },
        { mes: 'Fev', regiao: 'Centro', letalidade: 120, roubo: 60 },
        { mes: 'Jan', regiao: 'Zona Sul', letalidade: 80, roubo: 40 },
        { mes: 'Fev', regiao: 'Zona Sul', letalidade: 90, roubo: 45 },
    ];

    // Teste 1: Agrupamento de dados por mês
    describe('groupDataByKey', () => {
        test('Deve agrupar os dados corretamente pela chave "mes"', () => {
            const grouped = groupDataByKey(mockData, 'mes');
            expect(Object.keys(grouped)).toEqual(['Jan', 'Fev']);
            expect(grouped['Jan'].length).toBe(2);
            expect(grouped['Fev'].length).toBe(2);
        });

        test('Deve retornar um objeto vazio para dados vazios', () => {
            expect(groupDataByKey([], 'mes')).toEqual({});
        });

        test('Deve agrupar os dados corretamente pela chave "regiao"', () => {
            const grouped = groupDataByKey(mockData, 'regiao');
            expect(Object.keys(grouped)).toEqual(['Centro', 'Zona Sul']);
            expect(grouped['Centro'].length).toBe(2);
            expect(grouped['Zona Sul'].length).toBe(2);
        });
    });

    // Teste 2: Cálculo da soma de uma coluna
    describe('calculateSum', () => {
        test('Deve calcular a soma total da coluna "letalidade"', () => {
            // 100 + 120 + 80 + 90 = 390
            expect(calculateSum(mockData, 'letalidade')).toBe(390);
        });

        test('Deve calcular a soma total da coluna "roubo"', () => {
            // 50 + 60 + 40 + 45 = 195
            expect(calculateSum(mockData, 'roubo')).toBe(195);
        });

        test('Deve retornar 0 para um array de dados vazio', () => {
            expect(calculateSum([], 'letalidade')).toBe(0);
        });
    });

    // Teste 3: Filtragem de dados por região
    describe('filterData', () => {
        test('Deve filtrar os dados para retornar apenas a região "Centro"', () => {
            const filtered = filterData(mockData, 'regiao', 'Centro');
            expect(filtered.length).toBe(2);
            expect(filtered.every(item => item.regiao === 'Centro')).toBe(true);
        });

        test('Deve retornar um array vazio se o valor do filtro não for encontrado', () => {
            const filtered = filterData(mockData, 'regiao', 'Zona Oeste');
            expect(filtered).toEqual([]);
        });

        test('Deve filtrar os dados para retornar apenas o mês "Jan"', () => {
            const filtered = filterData(mockData, 'mes', 'Jan');
            expect(filtered.length).toBe(2);
            expect(filtered.every(item => item.mes === 'Jan')).toBe(true);
        });
    });

    // Teste 4: Combinação de Agrupamento e Soma (Agregação)
    describe('Agregação Combinada', () => {
        test('Deve calcular a letalidade total por mês', () => {
            const grouped = groupDataByKey(mockData, 'mes');
            const janSum = calculateSum(grouped['Jan'], 'letalidade'); // 100 + 80 = 180
            const fevSum = calculateSum(grouped['Fev'], 'letalidade'); // 120 + 90 = 210

            expect(janSum).toBe(180);
            expect(fevSum).toBe(210);
        });
    });

    // Teste 5: Filtragem e Soma (Agregação Condicional)
    describe('Filtragem e Soma', () => {
        test('Deve calcular a letalidade total apenas para a "Zona Sul"', () => {
            const filtered = filterData(mockData, 'regiao', 'Zona Sul');
            const sum = calculateSum(filtered, 'letalidade'); // 80 + 90 = 170
            expect(sum).toBe(170);
        });
    });
});