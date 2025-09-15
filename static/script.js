document.addEventListener('DOMContentLoaded', function () {

    // --- Dashboard Logic ---
    if (document.getElementById('filter-btn')) { // A good check for the dashboard page
        initializeDashboard();
    }

    // --- Protocol Form Logic ---
    if (document.getElementById('protocol-form')) {
        initializeProtocolForm();
    }

    // --- Modal Logic ---
    const updateStatusModal = document.getElementById('modalAtualizarStatus');
    if (updateStatusModal) {
        updateStatusModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const protocoloId = button.getAttribute('data-protocolo-id');
            updateStatusModal.querySelector('#atualizarProtocoloId').value = protocoloId;
        });
    }

    const forwardModal = document.getElementById('modalEncaminhar');
    if(forwardModal) {
        forwardModal.addEventListener('show.bs.modal', async function(event) {
            const button = event.relatedTarget;
            const protocoloId = button.getAttribute('data-protocolo-id');
            forwardModal.querySelector('#encaminharProtocoloId').value = protocoloId;

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
    // Populate filter dropdowns first
    populateDropdown('/api/lotacoes', 'dashLotacao');
    populateDropdown('/api/tipos_requerimento', 'dashTipo');
    const statusOptions = '<option value="">Todos os Status</option><option value="Aberto">Aberto</option><option value="Em análise">Em análise</option><option value="Pendente de documento">Pendente de documento</option><option value="Finalizado">Finalizado</option><option value="Concluído">Concluído</option><option value="Encaminhado">Encaminhado</option>';
    document.getElementById('dashStatus').innerHTML = statusOptions;

    let tiposChartInstance = null;
    let statusChartInstance = null;
    let evolucaoChartInstance = null;

    const allFilters = document.querySelectorAll('.filtros select, .filtros input, .chart-filters select');
    allFilters.forEach(f => f.addEventListener('change', fetchDashboardData));
    document.getElementById('filter-btn').addEventListener('click', fetchDashboardData);


    async function fetchDashboardData() {
        const params = new URLSearchParams({
            dataInicio: document.getElementById('dashDataInicio').value,
            dataFim: document.getElementById('dashDataFim').value,
            status: document.getElementById('dashStatus').value,
            tipo: document.getElementById('dashTipo').value,
            lotacao: document.getElementById('dashLotacao').value,
            evolucaoPeriodo: document.getElementById('evolucaoPeriodo').value,
            evolucaoAgrupamento: document.getElementById('evolucaoAgrupamento').value
        });

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
        const pieChartDataType = document.getElementById('pieChartDataType').value;
        const pieChartData = (pieChartDataType === 'status') ? data.statusProtocolos : data.todosTipos;
        const pieChartLabels = pieChartData.map(item => item.status || item.tipo_requerimento);
        const pieChartValues = pieChartData.map(item => item.total);
        document.getElementById('pieChartTitle').textContent = (pieChartDataType === 'status') ? 'Protocolos por Status' : 'Protocolos por Tipo';

        statusChartInstance = new Chart(statusCtx, {
            type: 'pie',
            data: {
                labels: pieChartLabels,
                datasets: [{ data: pieChartValues, backgroundColor: ['#2196F3', '#FF9800', '#4CAF50', '#F44336', '#9C27B0', '#009688', '#FF5722', '#795548', '#607D8B'] }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        if (evolucaoChartInstance) evolucaoChartInstance.destroy();
        const evolucaoCtx = document.getElementById('evolucaoChart').getContext('2d');
        const evolucaoAgrupamento = document.getElementById('evolucaoAgrupamento').value;
        evolucaoChartInstance = new Chart(evolucaoCtx, {
            type: 'line',
            data: {
                labels: data.evolucaoProtocolos.map(item => new Date(item.intervalo).toLocaleDateString('pt-BR', { timeZone: 'UTC', month: evolucaoAgrupamento === 'month' ? 'long' : '2-digit', day: evolucaoAgrupamento === 'day' ? '2-digit' : undefined })),
                datasets: [{ label: 'Novos Protocolos', data: data.evolucaoProtocolos.map(item => item.total), fill: true, borderColor: '#4CAF50', backgroundColor: 'rgba(76, 175, 80, 0.2)', tension: 0.1 }]
            },
            options: { responsive: true, scales: { y: { beginAtZero: true } } }
        });
    }

    const dataInicioInput = document.getElementById('dashDataInicio');
    if (!dataInicioInput.value) {
        const hoje = new Date();
        const trintaDiasAtras = new Date(new Date().setDate(hoje.getDate() - 30));
        dataInicioInput.value = trintaDiasAtras.toISOString().split('T')[0];
    }
    fetchDashboardData();
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
    populateDropdown('/api/lotacoes', 'lotacao');
    populateDropdown('/api/tipos_requerimento', 'tipo_requerimento');
    gerarNumeroProtocolo();

    document.getElementById('matricula').addEventListener('blur', fetchServidorByMatricula);
    document.getElementById('cep').addEventListener('blur', fetchCep);
    document.getElementById('btnBuscarServidor').addEventListener('click', openServidorSearchModal);
    document.getElementById('buscaNomeInput').addEventListener('input', searchServidorByName);
}

async function gerarNumeroProtocolo() {
    const anoAtual = new Date().getFullYear();
    const numeroInput = document.getElementById('numero');
    if (!numeroInput) return;

    try {
        const response = await fetch(`/api/protocolos/ultimoNumero/${anoAtual}`);
        const data = await response.json();
        const proximoNumero = (data.ultimo || 0) + 1;
        numeroInput.value = `${String(proximoNumero).padStart(4, '0')}/${anoAtual}`;
    } catch (error) {
        console.error("Erro ao gerar número do protocolo:", error);
        numeroInput.value = `0001/${anoAtual}`;
    }
}

async function populateDropdown(apiUrl, elementId) {
    const select = document.getElementById(elementId);
    if (!select) return;
    try {
        const response = await fetch(apiUrl);
        const data = await response.json();
        const currentValue = select.value;
        select.innerHTML = '<option value="">Selecione...</option>';
        data.forEach(item => {
            const option = new Option(item, item);
            select.add(option);
        });
        if (currentValue) {
            select.value = currentValue;
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
    if (servidor) {
        document.getElementById('matricula').value = servidor.matricula;
    }
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

// --- Admin Page Logic ---
window.openEditUserModal = function(user) {
    const modal = new bootstrap.Modal(document.getElementById('modalEditarUsuario'));
    document.getElementById('formEditarUsuario').action = `/admin/usuarios/${user.id}/editar`;
    document.getElementById('editUserId').value = user.id;
    document.getElementById('editNomeCompleto').value = user.nome_completo;
    document.getElementById('editLogin').value = user.login;
    document.getElementById('editEmail').value = user.email;
    document.getElementById('editTipo').value = user.tipo;
    modal.show();
}

window.openResetPasswordModal = function(userId) {
    const modal = new bootstrap.Modal(document.getElementById('modalResetarSenha'));
    document.getElementById('formResetarSenha').action = `/admin/usuarios/${userId}/resetar_senha`;
    modal.show();
}

// --- PDF Generation (Client-Side) ---
let protocoloParaGerarPDF = null;

function preencherTemplatePDF(protocolo) {
    const modeloNode = document.getElementById('modeloProtocolo').cloneNode(true);
    modeloNode.style.display = 'block';

    const Mapeamento = {
        '#doc_numero': protocolo.numero,
        '#doc_dataSolicitacao': new Date(protocolo.data_solicitacao).toLocaleDateString('pt-BR', {timeZone: 'UTC'}),
        '#doc_nome': protocolo.nome,
        '#doc_matricula': protocolo.matricula,
        '#doc_cpf': protocolo.cpf,
        '#doc_rg': protocolo.rg,
        '#doc_endereco': protocolo.endereco,
        '#doc_bairro': protocolo.bairro,
        '#doc_municipio': protocolo.municipio,
        '#doc_cep': protocolo.cep,
        '#doc_telefone': protocolo.telefone,
        '#doc_cargo': protocolo.cargo,
        '#doc_lotacao': protocolo.lotacao,
        '#doc_unidade': protocolo.unidade_exercicio,
        '#doc_tipo': protocolo.tipo_requerimento,
        '#doc_requerAo': protocolo.requer_ao,
        '#doc_complemento': protocolo.observacoes ? protocolo.observacoes.replace(/\n/g, '<br>') : 'Nenhuma.'
    };

    for(const selector in Mapeamento) {
        const el = modeloNode.querySelector(selector);
        if(el) el.innerHTML = Mapeamento[selector] || 'N/A';
    }

    const qrcodeContainer = modeloNode.querySelector('#qrcode-container');
    qrcodeContainer.innerHTML = '';
    if (protocolo.numero && protocolo.numero.includes('/')) {
        const [num, ano] = protocolo.numero.split('/');
        const urlConsulta = `${window.location.origin}/consulta/${ano}/${num}`;
        new QRCode(qrcodeContainer, { text: urlConsulta, width: 90, height: 90, correctLevel: QRCode.CorrectLevel.H });
    }

    return modeloNode;
}


window.previsualizarPDF = async function(protocoloId) {
    try {
        const response = await fetch(`/api/protocolo/${protocoloId}`);
        if (!response.ok) throw new Error('Falha ao buscar dados do protocolo');
        const protocolo = await response.json();
        protocoloParaGerarPDF = protocolo;

        const pdfContentDiv = document.getElementById('pdfContent');
        pdfContentDiv.innerHTML = '';
        pdfContentDiv.appendChild(preencherTemplatePDF(protocolo));

        const modal = new bootstrap.Modal(document.getElementById('pdfModal'));
        modal.show();
    } catch(err) {
        console.error("Erro ao pré-visualizar PDF:", err);
        alert("Erro ao carregar dados do documento.");
    }
};

window.gerarPDF = function() {
    if (!protocoloParaGerarPDF) {
        alert("Nenhum protocolo para gerar PDF.");
        return;
    }
    const element = preencherTemplatePDF(protocoloParaGerarPDF);
    const opt = {
        margin: [5, 5, 5, 5],
        filename: `Protocolo_${protocoloParaGerarPDF.numero.replace('/', '-')}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save();
};

// --- PDF Generation (Client-Side) ---
let protocoloParaGerarPDF = null;

window.openPdfModal = async function(protocoloId) {
    try {
        const response = await fetch(`/api/protocolo/${protocoloId}`);
        if (!response.ok) throw new Error('Failed to fetch protocol data');

        const protocolo = await response.json();
        protocoloParaGerarPDF = protocolo;

        const pdfContentDiv = document.getElementById('pdfContent');
        const modeloNode = document.getElementById('modeloProtocolo').cloneNode(true);

        // This is a simplified version of the original's logic to populate the template
        let contentHtml = `
            <p><strong>Número:</strong> ${protocolo.numero}</p>
            <p><strong>Data:</strong> ${new Date(protocolo.data_solicitacao).toLocaleDateString('pt-BR')}</p>
            <p><strong>Nome:</strong> ${protocolo.nome}</p>
            <p><strong>Matrícula:</strong> ${protocolo.matricula}</p>
            <p><strong>Tipo:</strong> ${protocolo.tipo_requerimento}</p>
            <p><strong>Observações:</strong> ${protocolo.observacoes}</p>
        `;

        modeloNode.querySelector('#doc-content').innerHTML = contentHtml;

        const qrcodeContainer = modeloNode.querySelector('#qrcode-container');
        qrcodeContainer.innerHTML = '';
        if (protocolo.numero && protocolo.numero.includes('/')) {
            const [num, ano] = protocolo.numero.split('/');
            const urlConsulta = `${window.location.origin}/consulta/${ano}/${num}`;
            new QRCode(qrcodeContainer, { text: urlConsulta, width: 90, height: 90 });
        }

        pdfContentDiv.innerHTML = '';
        pdfContentDiv.appendChild(modeloNode.firstElementChild);

        const modal = new bootstrap.Modal(document.getElementById('pdfModal'));
        modal.show();

    } catch (error) {
        console.error('Error preparing PDF preview:', error);
        alert('Erro ao carregar dados para o documento.');
    }
};

window.gerarPDF = function() {
    if (!protocoloParaGerarPDF) {
        alert("Nenhum protocolo para gerar PDF.");
        return;
    }
    const element = document.getElementById('pdfContent');
    const opt = {
        margin: 5,
        filename: `Protocolo_${protocoloParaGerarPDF.numero.replace('/', '-')}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save();
};
