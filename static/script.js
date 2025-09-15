// This script will be rewritten to support the MPA pattern.
// It will only contain logic for enhancing the UI, not for rendering entire pages.

document.addEventListener('DOMContentLoaded', function () {

    // --- Dashboard Logic ---
    if (document.getElementById('dashboard-header')) {
        initializeDashboard();
    }

    // --- Protocol Form Logic ---
    if (document.getElementById('protocol-form')) {
        initializeProtocolForm();
    }

    // --- Modal Logic ---
    // This will be expanded to handle all modals.
    // Example for the "Atualizar Status" modal
    const updateStatusModal = document.getElementById('modalAtualizarStatus');
    if (updateStatusModal) {
        updateStatusModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const protocoloId = button.getAttribute('data-protocolo-id');
            const modalProtocoloIdInput = updateStatusModal.querySelector('#atualizarProtocoloId');
            modalProtocoloIdInput.value = protocoloId;
        });
    }

    const forwardModal = document.getElementById('modalEncaminhar');
    if(forwardModal) {
        forwardModal.addEventListener('show.bs.modal', async function(event) {
            const button = event.relatedTarget;
            const protocoloId = button.getAttribute('data-protocolo-id');
            const modalProtocoloIdInput = forwardModal.querySelector('#encaminharProtocoloId');
            modalProtocoloIdInput.value = protocoloId;

            // Fetch users and populate select
            const userSelect = forwardModal.querySelector('#selectUsuarioEncaminhar');
            userSelect.innerHTML = '<option>Carregando...</option>';
            try {
                const response = await fetch('/api/usuarios');
                const users = await response.json();
                userSelect.innerHTML = '';
                users.forEach(user => {
                    const option = new Option(`${user.nome} (${user.login})`, user.login);
                    userSelect.add(option);
                });
            } catch (error) {
                console.error('Failed to fetch users:', error);
                userSelect.innerHTML = '<option>Erro ao carregar usuários</option>';
            }
        });
    }

});

// --- Dashboard Functions ---
function initializeDashboard() {
    let tiposChartInstance = null;
    let statusChartInstance = null;
    let evolucaoChartInstance = null;
    const filterBtn = document.getElementById('filter-btn');

    async function fetchDashboardData() {
        const dataInicio = document.getElementById('dashDataInicio').value;
        const dataFim = document.getElementById('dashDataFim').value;
        const params = new URLSearchParams({ dataInicio, dataFim });

        try {
            const response = await fetch(`/api/dashboard-data?${params.toString()}`);
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            updateDashboardUI(data);
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error);
        }
    }

    function updateDashboardUI(data) {
        document.getElementById('stat-novos').textContent = data.novosNoPeriodo;
        document.getElementById('stat-pendentes').textContent = data.pendentesAntigos;
        document.getElementById('stat-finalizados').textContent = data.totalFinalizados;

        if (tiposChartInstance) tiposChartInstance.destroy();
        const tiposCtx = document.getElementById('tiposChart').getContext('2d');
        tiposChartInstance = new Chart(tiposCtx, {
            type: 'bar',
            data: {
                labels: data.topTipos.map(item => item.tipo_requerimento),
                datasets: [{ label: 'Total', data: data.topTipos.map(item => item.total), backgroundColor: '#4CAF50' }]
            },
            options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
        });

        if (statusChartInstance) statusChartInstance.destroy();
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        statusChartInstance = new Chart(statusCtx, {
            type: 'pie',
            data: {
                labels: data.statusProtocolos.map(item => item.status),
                datasets: [{ data: data.statusProtocolos.map(item => item.total), backgroundColor: ['#2196F3', '#FF9800', '#4CAF50', '#F44336', '#9C27B0', '#009688'] }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        if (evolucaoChartInstance) evolucaoChartInstance.destroy();
        const evolucaoCtx = document.getElementById('evolucaoChart').getContext('2d');
        evolucaoChartInstance = new Chart(evolucaoCtx, {
            type: 'line',
            data: {
                labels: data.evolucaoProtocolos.map(item => new Date(item.intervalo).toLocaleDateString('pt-BR', { timeZone: 'UTC' })),
                datasets: [{ label: 'Novos Protocolos', data: data.evolucaoProtocolos.map(item => item.total), fill: true, borderColor: '#4CAF50', backgroundColor: 'rgba(76, 175, 80, 0.2)', tension: 0.1 }]
            },
            options: { responsive: true, scales: { y: { beginAtZero: true } } }
        });
    }

    if(filterBtn) filterBtn.addEventListener('click', fetchDashboardData);
    fetchDashboardData(); // Initial load
}

// --- Modal Action Functions ---
window.confirmarEncaminhamento = async function() {
    const protocoloId = document.getElementById('encaminharProtocoloId').value;
    const novoResponsavel = document.getElementById('selectUsuarioEncaminhar').value;
    const novoStatus = document.getElementById('statusEncaminhamento').value;

    try {
        const response = await fetch(`/protocolos/atualizar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ protocoloId, novoStatus, novoResponsavel, observacao: `Encaminhado para ${novoResponsavel}` })
        });
        if (response.ok) {
            window.location.reload(); // Simple way to refresh data in an MPA
        } else {
            alert('Erro ao encaminhar protocolo.');
        }
    } catch (error) {
        console.error('Error forwarding protocol:', error);
        alert('Erro de conexão ao encaminhar protocolo.');
    }
}

window.confirmarAtualizacaoStatus = async function() {
    const protocoloId = document.getElementById('atualizarProtocoloId').value;
    const novoStatus = document.getElementById('statusSelect').value;
    const observacao = document.getElementById('observacaoAtualizacao').value;

    try {
        const response = await fetch(`/protocolos/atualizar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ protocoloId, novoStatus, observacao })
        });
        if (response.ok) {
            window.location.reload();
        } else {
            alert('Erro ao atualizar status.');
        }
    } catch (error) {
        console.error('Error updating status:', error);
        alert('Erro de conexão ao atualizar status.');
    }
}

// --- Protocol Form Functions ---
function initializeProtocolForm() {
    // Populate dropdowns on page load
    populateDropdown('/api/lotacoes', 'lotacao');
    populateDropdown('/api/tipos_requerimento', 'tipo_requerimento');

    // Add event listeners
    document.getElementById('matricula').addEventListener('blur', fetchServidorByMatricula);
    document.getElementById('cep').addEventListener('blur', fetchCep);
    document.getElementById('btnBuscarServidor').addEventListener('click', openServidorSearchModal);
    document.getElementById('buscaNomeInput').addEventListener('input', searchServidorByName);
}

async function populateDropdown(apiUrl, elementId) {
    const select = document.getElementById(elementId);
    if (!select) return;
    try {
        const response = await fetch(apiUrl);
        const data = await response.json();
        const currentValue = select.value; // Save current value if editing
        select.innerHTML = '<option value="">Selecione...</option>'; // Reset
        data.forEach(item => {
            const option = new Option(item, item);
            select.add(option);
        });
        if (currentValue) {
            select.value = currentValue; // Restore value
        }
    } catch (error) {
        console.error(`Failed to populate dropdown ${elementId}:`, error);
    }
}

async function fetchServidorByMatricula() {
    const matricula = this.value.trim();
    if (!matricula) return;
    try {
        const response = await fetch(`/api/servidor/${matricula}`);
        if (response.ok) {
            const servidor = await response.json();
            preencherCamposServidor(servidor);
        }
    } catch (error) {
        console.error('Erro ao buscar servidor por matrícula:', error);
    }
}

async function fetchCep() {
    const cep = this.value.replace(/\D/g, '');
    if (cep.length !== 8) return;
    try {
        const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const data = await response.json();
        if (!data.erro) {
            document.getElementById('endereco').value = data.logradouro || '';
            document.getElementById('municipio').value = data.localidade || '';
            document.getElementById('bairro').value = data.bairro || '';
        }
    } catch (error) {
        console.error('Erro ao buscar CEP:', error);
    }
}

function preencherCamposServidor(servidor) {
    document.getElementById('nome').value = servidor ? servidor.nome : '';
    document.getElementById('lotacao').value = servidor ? servidor.lotacao : '';
    document.getElementById('cargo').value = servidor ? servidor.cargo : '';
    document.getElementById('unidade_exercicio').value = servidor ? servidor.unidade_de_exercicio : '';
}

function openServidorSearchModal() {
    const modal = new bootstrap.Modal(document.getElementById('modalBuscaServidor'));
    document.getElementById('buscaNomeInput').value = '';
    document.getElementById('buscaNomeResultados').innerHTML = '';
    modal.show();
}

async function searchServidorByName() {
    const searchTerm = this.value.trim();
    const resultadosDiv = document.getElementById('buscaNomeResultados');
    if (searchTerm.length < 3) {
        resultadosDiv.innerHTML = '<p>Digite ao menos 3 caracteres.</p>';
        return;
    }
    try {
        const response = await fetch(`/api/servidores/search?nome=${encodeURIComponent(searchTerm)}`);
        const servidores = await response.json();
        resultadosDiv.innerHTML = '';
        if (servidores.length > 0) {
            servidores.forEach(servidor => {
                const div = document.createElement('div');
                div.className = 'list-group-item list-group-item-action';
                div.style.cursor = 'pointer';
                div.innerHTML = `<strong>${servidor.nome}</strong><br><small>Matrícula: ${servidor.matricula}</small>`;
                div.onclick = () => {
                    preencherCamposServidor(servidor);
                    const modal = bootstrap.Modal.getInstance(document.getElementById('modalBuscaServidor'));
                    modal.hide();
                };
                resultadosDiv.appendChild(div);
            });
        } else {
            resultadosDiv.innerHTML = '<p>Nenhum servidor encontrado.</p>';
        }
    } catch (error) {
        console.error('Erro ao buscar servidor por nome:', error);
    }
}
