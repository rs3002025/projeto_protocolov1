/**
 * Script principal para a aplicação de Protocolos (MPA Version)
 * Contém a lógica para inicialização de páginas, manipulação de modais,
 * chamadas de API e outras interações dinâmicas.
 */

// --- Evento Principal ---
document.addEventListener('DOMContentLoaded', function () {
    // Inicializa a lógica específica da página com base em um elemento único da página
    if (document.getElementById('dashboard-header')) {
        initializeDashboard();
    }
    if (document.getElementById('protocol-form')) {
        initializeProtocolForm();
    }
    if (document.querySelector('.protocolos-table')) { // Elemento presente na listagem de protocolos
        initializeProtocolosPage();
    }
});


// --- Inicializadores de Página ---

/**
 * Prepara a página do Dashboard, definindo datas padrão e carregando os dados.
 */
function initializeDashboard() {
    const dataInicioInput = document.getElementById('dashDataInicio');
    const dataFimInput = document.getElementById('dashDataFim');

    if (!dataInicioInput.value) {
        const hoje = new Date();
        const trintaDiasAtras = new Date(new Date().setDate(hoje.getDate() - 30));
        dataInicioInput.value = trintaDiasAtras.toISOString().split('T')[0];
    }
    if (!dataFimInput.value) {
        dataFimInput.value = new Date().toISOString().split('T')[0];
    }

    document.getElementById('filter-btn').addEventListener('click', fetchAndRenderDashboard);
    fetchAndRenderDashboard(); // Carga inicial
}

/**
 * Prepara o formulário de Novo Protocolo, populando dropdowns e adicionando listeners.
 */
function initializeProtocolForm() {
    // Popula dropdowns dinâmicos
    populateDropdown('/api/lotacoes', 'lotacao');
    populateDropdown('/api/tipos_requerimento', 'tipo');
    populateDropdown('/api/bairros', 'bairro');

    // Adiciona listeners para eventos de campo
    document.getElementById('matricula').addEventListener('blur', fetchServidorByMatricula);
    document.getElementById('cep').addEventListener('blur', fetchCep);
    document.getElementById('buscaNomeInput').addEventListener('input', searchServidorByName);

    // Gera o número do protocolo se for um novo formulário (sem 'protocolo' preenchido)
    if (!document.getElementById('numeroProtocolo').value) {
        gerarNumeroProtocolo();
        document.getElementById('dataSolicitacao').value = new Date().toISOString().split('T')[0];
    }
}

/**
 * Adiciona listeners aos modais na página de listagem de protocolos.
 */
function initializeProtocolosPage() {
    const updateStatusModal = document.getElementById('modalAtualizarStatus');
    if (updateStatusModal) {
        updateStatusModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const protocoloId = button.getAttribute('data-protocolo-id');
            updateStatusModal.querySelector('#atualizarProtocoloId').value = protocoloId;
        });
    }

    const forwardModal = document.getElementById('modalEncaminhar');
    if (forwardModal) {
        forwardModal.addEventListener('show.bs.modal', async function (event) {
            const button = event.relatedTarget;
            const protocoloId = button.getAttribute('data-protocolo-id');
            forwardModal.querySelector('#encaminharProtocoloId').value = protocoloId;

            const userSelect = forwardModal.querySelector('#selectUsuarioEncaminhar');
            userSelect.innerHTML = '<option>Carregando...</option>';
            try {
                const response = await fetch('/api/usuarios');
                const users = await response.json();
                userSelect.innerHTML = '<option value="">Selecione um usuário</option>';
                users.forEach(user => {
                    const option = new Option(`${user.nome} (${user.login})`, user.login);
                    userSelect.add(option);
                });
            } catch (error) {
                console.error('Falha ao carregar usuários:', error);
                userSelect.innerHTML = '<option>Erro ao carregar</option>';
            }
        });
    }
}


// --- Funções de API e Lógica de Negócio ---

// DASHBOARD
let tiposChartInstance, statusChartInstance, evolucaoChartInstance;

async function fetchAndRenderDashboard() {
    const dataInicio = document.getElementById('dashDataInicio').value;
    const dataFim = document.getElementById('dashDataFim').value;
    const url = `/api/dashboard-data?dataInicio=${dataInicio}&dataFim=${dataFim}`;

    try {
        const response = await fetch(url);
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `Erro HTTP ${response.status}`);

        updateDashboardCards(data);
        updateDashboardCharts(data);

    } catch (error) {
        console.error("Erro ao carregar dados do dashboard:", error);
        alert("Não foi possível carregar os dados do dashboard: " + error.message);
    }
}

function updateDashboardCards(stats) {
    document.getElementById('stat-novos').textContent = stats.novosNoPeriodo || 0;
    document.getElementById('stat-pendentes').textContent = stats.pendentesAntigos || 0;
    document.getElementById('stat-finalizados').textContent = stats.totalFinalizados || 0;
}

function updateDashboardCharts(stats) {
    if (tiposChartInstance) tiposChartInstance.destroy();
    tiposChartInstance = new Chart(document.getElementById('tiposChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: stats.topTipos.map(item => item.tipo_requerimento),
            datasets: [{ data: stats.topTipos.map(item => item.total), backgroundColor: ['#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B', '#FFC107'] }]
        },
        options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
    });

    if (statusChartInstance) statusChartInstance.destroy();
    statusChartInstance = new Chart(document.getElementById('statusChart').getContext('2d'), {
        type: 'pie',
        data: {
            labels: stats.statusProtocolos.map(item => item.status),
            datasets: [{ data: stats.statusProtocolos.map(item => item.total), backgroundColor: ['#2196F3', '#FF9800', '#4CAF50', '#F44336', '#9C27B0'] }]
        },
        options: { responsive: true, plugins: { legend: { position: 'top' } } }
    });

    if (evolucaoChartInstance) evolucaoChartInstance.destroy();
    evolucaoChartInstance = new Chart(document.getElementById('evolucaoChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: stats.evolucaoProtocolos.map(item => new Date(item.intervalo + 'T00:00:00').toLocaleDateString('pt-BR')),
            datasets: [{ data: stats.evolucaoProtocolos.map(item => item.total), borderColor: '#4CAF50', fill: true }]
        },
        options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
    });
}


// FORMULÁRIO DE PROTOCOLO
async function fetchCep() {
    const cep = document.getElementById('cep').value.replace(/\D/g, '');
    if (cep.length !== 8) return;

    try {
        const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const data = await response.json();
        if (data.erro) {
            console.warn('CEP não encontrado');
            return;
        }
        document.getElementById('endereco').value = data.logradouro || '';
        document.getElementById('municipio').value = data.localidade || '';
        document.getElementById('bairro').value = data.bairro || '';
    } catch (error) {
        console.error('Erro ao buscar CEP:', error);
    }
}

async function fetchServidorByMatricula() {
    const matricula = document.getElementById('matricula').value.trim();
    if (!matricula) return;
    try {
        const response = await fetch(`/api/servidor/${matricula}`);
        const data = await response.json();
        if (response.ok) {
            preencherCamposServidor(data);
        } else {
            console.warn('Servidor não encontrado pela matrícula.');
        }
    } catch (error) {
        console.error('Erro ao buscar servidor por matrícula:', error);
    }
}

function preencherCamposServidor(servidor) {
    document.getElementById('nome').value = servidor.nome || '';
    document.getElementById('lotacao').value = servidor.lotacao || '';
    document.getElementById('cargo').value = servidor.cargo || '';
    document.getElementById('unidade').value = servidor.unidade_de_exercicio || '';
}

async function searchServidorByName() {
    const searchTerm = this.value.trim();
    const resultadosDiv = document.getElementById('buscaNomeResultados');
    if (searchTerm.length < 3) {
        resultadosDiv.innerHTML = '';
        return;
    }
    try {
        const response = await fetch(`/api/servidores/search?nome=${encodeURIComponent(searchTerm)}`);
        const servidores = await response.json();
        resultadosDiv.innerHTML = '';
        if (servidores.error || servidores.length === 0) {
            resultadosDiv.innerHTML = `<p class="text-center text-muted">${servidores.error || 'Nenhum servidor encontrado.'}</p>`;
            return;
        }
        servidores.forEach(servidor => {
            const div = document.createElement('a');
            div.href = '#';
            div.className = 'list-group-item list-group-item-action';
            div.innerHTML = `<strong>${servidor.nome}</strong><br><small>Matrícula: ${servidor.matricula}</small>`;
            div.onclick = (e) => {
                e.preventDefault();
                document.getElementById('matricula').value = servidor.matricula;
                preencherCamposServidor(servidor);
                const modal = bootstrap.Modal.getInstance(document.getElementById('modalBuscaServidor'));
                modal.hide();
            };
            resultadosDiv.appendChild(div);
        });
    } catch (error) {
        console.error('Erro ao buscar servidor:', error);
        resultadosDiv.innerHTML = '<p class="text-center text-danger">Erro de conexão.</p>';
    }
}

async function gerarNumeroProtocolo() {
    try {
        const ano = new Date().getFullYear();
        const res = await fetch(`/protocolos/ultimoNumero/${ano}`);
        const data = await res.json();
        document.getElementById('numeroProtocolo').value = `${String((data.ultimo || 0) + 1).padStart(4, '0')}/${ano}`;
    } catch (error) {
        console.error("Erro ao gerar número do protocolo:", error);
    }
}


// --- Funções de Modal (Ações) ---
window.openServidorSearchModal = function() {
    const modalElement = document.getElementById('modalBuscaServidor');
    if (modalElement) {
        const modal = new bootstrap.Modal(modalElement);
        modal.show();
    }
};

window.handleStatusChange = function(selectElement) {
    document.getElementById('statusCustomContainer').style.display = selectElement.value === 'Outro' ? 'block' : 'none';
};

window.confirmarEncaminhamento = async function() {
    const protocoloId = document.getElementById('encaminharProtocoloId').value;
    const novoResponsavel = document.getElementById('selectUsuarioEncaminhar').value;
    if (!novoResponsavel) return alert('Selecione um usuário para encaminhar.');

    const data = {
        protocoloId,
        novoStatus: 'Encaminhado',
        novoResponsavel,
        observacao: document.getElementById('observacaoEncaminhamento').value
    };

    try {
        const response = await fetch('/protocolos/atualizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (!result.sucesso) throw new Error(result.mensagem);

        alert('Protocolo encaminhado com sucesso!');
        window.location.reload();
    } catch (error) {
        alert(`Erro ao encaminhar protocolo: ${error.message}`);
    }
};

window.confirmarAtualizacaoStatus = async function() {
    let novoStatus = document.getElementById('statusSelect').value;
    if (novoStatus === 'Outro') {
        novoStatus = document.getElementById('statusCustom').value.trim();
        if (!novoStatus) return alert('Digite o status personalizado.');
    }

    const data = {
        protocoloId: document.getElementById('atualizarProtocoloId').value,
        novoStatus,
        observacao: document.getElementById('observacaoAtualizacao').value
    };

    try {
        const response = await fetch('/protocolos/atualizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (!result.sucesso) throw new Error(result.mensagem);

        alert('Status atualizado com sucesso!');
        window.location.reload();
    } catch (error) {
        alert(`Erro ao atualizar status: ${error.message}`);
    }
};


// --- Funções de PDF ---
let protocoloParaGerar = null;

window.previsualizarPDF = async function(id = null, isFromForm = false) {
    try {
        if (isFromForm) {
            protocoloParaGerar = {
                numero: document.getElementById('numeroProtocolo').value,
                data_solicitacao: document.getElementById('dataSolicitacao').value,
                nome: document.getElementById('nome').value,
                matricula: document.getElementById('matricula').value,
                cpf: document.getElementById('cpf').value,
                rg: document.getElementById('rg').value,
                endereco: document.getElementById('endereco').value,
                bairro: document.getElementById('bairro').value,
                municipio: document.getElementById('municipio').value,
                cep: document.getElementById('cep').value,
                telefone: document.getElementById('telefone').value,
                cargo: document.getElementById('cargo').value,
                lotacao: document.getElementById('lotacao').value,
                unidade_exercicio: document.getElementById('unidade').value,
                tipo_requerimento: document.getElementById('tipo').value,
                requer_ao: document.getElementById('requerAo').value,
                observacoes: document.getElementById('complemento').value
            };
        } else {
            const res = await fetch(`/api/protocolo/${id}`);
            if (!res.ok) throw new Error('Protocolo não encontrado');
            protocoloParaGerar = await res.json();
        }
        renderizarConteudoPDF(protocoloParaGerar);
        new bootstrap.Modal(document.getElementById('pdfModal')).show();
    } catch (error) {
        alert('Erro ao preparar pré-visualização do PDF: ' + error.message);
    }
};

function renderizarConteudoPDF(protocolo) {
    const pdfContentDiv = document.getElementById('pdfContent');
    const modeloDiv = document.getElementById('modeloProtocolo');
    if (!pdfContentDiv || !modeloDiv) return;

    const clone = modeloDiv.cloneNode(true);
    // ... (código de preenchimento dos campos do PDF, que já estava correto)
    Object.keys(protocolo).forEach(key => {
        const elem = clone.querySelector(`#doc_${key}`);
        if (elem) {
            if (key === 'data_solicitacao' && protocolo[key]) {
                elem.textContent = new Date(protocolo[key] + 'T00:00:00').toLocaleDateString('pt-BR');
            } else {
                elem.textContent = protocolo[key] || '';
            }
        }
    });
    clone.querySelector('#doc_unidade').textContent = protocolo.unidade_exercicio || '';
    clone.querySelector('#doc_tipo').textContent = protocolo.tipo_requerimento || '';
    clone.querySelector('#doc_requerAo').textContent = protocolo.requer_ao || '';
    clone.querySelector('#doc_complemento').innerHTML = (protocolo.observacoes || '').replace(/\n/g, '<br>');

    pdfContentDiv.innerHTML = clone.innerHTML;
}

window.gerarPDF = function() {
    if (!protocoloParaGerar) return alert("Nenhum protocolo para gerar.");
    const element = document.getElementById('pdfContent');
    const opt = {
        margin: 0,
        filename: `Protocolo_${(protocoloParaGerar.numero || 'Novo').replace(/[\/\\]/g, '-')}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save().then(() => {
        const modal = bootstrap.Modal.getInstance(document.getElementById('pdfModal'));
        if (modal) modal.hide();
    });
};


// --- Funções Utilitárias ---
async function populateDropdown(apiUrl, elementId) {
    const select = document.getElementById(elementId);
    if (!select) return;
    try {
        const response = await fetch(apiUrl);
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        const currentValue = select.value; // Salva o valor atual (para edição)
        select.innerHTML = `<option value="">Selecione...</option>`;
        data.forEach(item => {
            const option = new Option(item, item);
            select.add(option);
        });
        if (currentValue) { // Restaura o valor se ele existia
            select.value = currentValue;
        }
    } catch (error) {
        console.error(`Falha ao popular o dropdown ${elementId}:`, error);
    }
}
