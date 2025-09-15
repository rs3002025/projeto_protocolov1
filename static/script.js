// This script will be rewritten to support the MPA pattern.
// It will only contain logic for enhancing the UI, not for rendering entire pages.

document.addEventListener('DOMContentLoaded', function () {

    // --- Dashboard Logic ---
    // Check if we are on the home page (where the dashboard elements exist)
    if (document.getElementById('dashboard-header')) {
        initializeDashboard();
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
async function confirmarEncaminhamento() {
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

async function confirmarAtualizacaoStatus() {
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
