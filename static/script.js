document.addEventListener('DOMContentLoaded', function () {
    // --- Dashboard Logic ---
    const dashboardHeader = document.getElementById('dashboard-header');
    if (dashboardHeader) {
        initializeDashboard();
    }

    // This logic is for modals that can appear on multiple pages, so it's safe to keep it global.
    // However, it's better to ensure the elements exist before adding listeners.

    // --- Modal Logic for /protocolos page ---
    const updateStatusModal = document.getElementById('modalAtualizarStatus');
    if (updateStatusModal) {
        updateStatusModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const protocoloId = button.getAttribute('data-protocolo-id');
            const modalProtocoloIdInput = updateStatusModal.querySelector('#atualizarProtocoloId');
            if(modalProtocoloIdInput) modalProtocoloIdInput.value = protocoloId;
        });
    }

    const forwardModal = document.getElementById('modalEncaminhar');
    if(forwardModal) {
        forwardModal.addEventListener('show.bs.modal', async function(event) {
            const button = event.relatedTarget;
            const protocoloId = button.getAttribute('data-protocolo-id');
            const modalProtocoloIdInput = forwardModal.querySelector('#encaminharProtocoloId');
            if(modalProtocoloIdInput) modalProtocoloIdInput.value = protocoloId;

            const userSelect = forwardModal.querySelector('#selectUsuarioEncaminhar');
            if (!userSelect) return;
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
// NOTE: This function and its helpers would ideally be in their own file too,
// but for now, keeping it here as it's part of the original global script.
function initializeDashboard() {
    let tiposChartInstance = null;
    let statusChartInstance = null;
    let evolucaoChartInstance = null;
    const filterBtn = document.getElementById('filter-btn');

    async function fetchDashboardData() {
        const dataInicio = document.getElementById('dashDataInicio')?.value;
        const dataFim = document.getElementById('dashDataFim')?.value;
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
        const statNovos = document.getElementById('stat-novos');
        const statPendentes = document.getElementById('stat-pendentes');
        const statFinalizados = document.getElementById('stat-finalizados');

        if(statNovos) statNovos.textContent = data.novosNoPeriodo;
        if(statPendentes) statPendentes.textContent = data.pendentesAntigos;
        if(statFinalizados) statFinalizados.textContent = data.totalFinalizados;

        const tiposCtx = document.getElementById('tiposChart')?.getContext('2d');
        if(tiposCtx) {
            if (tiposChartInstance) tiposChartInstance.destroy();
            tiposChartInstance = new Chart(tiposCtx, {
                type: 'bar',
                data: {
                    labels: data.topTipos.map(item => item.tipo_requerimento),
                    datasets: [{ label: 'Total', data: data.topTipos.map(item => item.total), backgroundColor: '#4CAF50' }]
                },
                options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
            });
        }

        const statusCtx = document.getElementById('statusChart')?.getContext('2d');
        if(statusCtx) {
            if (statusChartInstance) statusChartInstance.destroy();
            statusChartInstance = new Chart(statusCtx, {
                type: 'pie',
                data: {
                    labels: data.statusProtocolos.map(item => item.status),
                    datasets: [{ data: data.statusProtocolos.map(item => item.total), backgroundColor: ['#2196F3', '#FF9800', '#4CAF50', '#F44336', '#9C27B0', '#009688'] }]
                },
                options: { responsive: true, plugins: { legend: { position: 'right' } } }
            });
        }

        const evolucaoCtx = document.getElementById('evolucaoChart')?.getContext('2d');
        if(evolucaoCtx) {
            if (evolucaoChartInstance) evolucaoChartInstance.destroy();
            evolucaoChartInstance = new Chart(evolucaoCtx, {
                type: 'line',
                data: {
                    labels: data.evolucaoProtocolos.map(item => new Date(item.intervalo).toLocaleDateString('pt-BR', { timeZone: 'UTC' })),
                    datasets: [{ label: 'Novos Protocolos', data: data.evolucaoProtocolos.map(item => item.total), fill: true, borderColor: '#4CAF50', backgroundColor: 'rgba(76, 175, 80, 0.2)', tension: 0.1 }]
                },
                options: { responsive: true, scales: { y: { beginAtZero: true } } }
            });
        }
    }

    if(filterBtn) filterBtn.addEventListener('click', fetchDashboardData);
    if(document.getElementById('dashboard-header')) fetchDashboardData(); // Initial load
}

// --- Modal Action Functions ---
window.confirmarEncaminhamento = async function() {
    const protocoloId = document.getElementById('encaminharProtocoloId')?.value;
    const novoResponsavel = document.getElementById('selectUsuarioEncaminhar')?.value;
    const novoStatus = document.getElementById('statusEncaminhamento')?.value;

    try {
        const response = await fetch(`/protocolos/atualizar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ protocoloId, novoStatus, novoResponsavel, observacao: `Encaminhado para ${novoResponsavel}` })
        });
        if (response.ok) {
            window.location.reload();
        } else {
            alert('Erro ao encaminhar protocolo.');
        }
    } catch (error) {
        console.error('Error forwarding protocol:', error);
        alert('Erro de conexão ao encaminhar protocolo.');
    }
}

window.confirmarAtualizacaoStatus = async function() {
    const protocoloId = document.getElementById('atualizarProtocoloId')?.value;
    const novoStatus = document.getElementById('statusSelect')?.value;
    const observacao = document.getElementById('observacaoAtualizacao')?.value;

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
