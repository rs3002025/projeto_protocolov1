// This script will be rewritten to support the MPA pattern.
// It will only contain logic for enhancing the UI, not for rendering entire pages.

document.addEventListener('DOMContentLoaded', function () {

    // --- Dashboard Logic ---
    if (document.querySelector('.dashboard-screen')) {
        popularFiltrosDashboard();
        carregarDashboard();
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

    // --- Delegated Event Listeners ---
    // Use event delegation for buttons that might be on any page.
    // This is more robust than attaching listeners directly in some cases.
});

// --- NEW DASHBOARD FUNCTIONS ---
let tiposChartInstance = null;
let statusChartInstance = null;
let evolucaoChartInstance = null;

window.fecharModal = function(modalId) {
    const modalElement = document.getElementById(modalId);
    if (modalElement) {
        modalElement.style.display = 'none';
    }
}

window.popularFiltrosDashboard = function() {
    const statusOptions = '<option value="">Todos os Status</option><option value="PROTOCOLO GERADO">PROTOCOLO GERADO</option><option value="Em análise">Em análise</option><option value="Pendente de documento">Pendente de documento</option><option value="Finalizado">Finalizado</option><option value="Concluído">Concluído</option><option value="Encaminhado">Encaminhado</option>';
    const statusSelect = document.getElementById('dashStatus');
    if (statusSelect) {
        statusSelect.innerHTML = statusOptions;
    }

    // Use the existing populateDropdown function which fetches from the API
    populateDropdown('/api/tipos_requerimento', 'dashTipo');
    populateDropdown('/api/lotacoes', 'dashLotacao');
};

window.carregarDashboard = async function() {
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
        const res = await fetch(`/protocolos/dashboard-stats?${params.toString()}`);
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'Erro ao buscar dados do dashboard');
        }
        const stats = await res.json();

        // 1. Update Cards
        document.getElementById('stat-novos').textContent = stats.novosNoPeriodo || 0;
        document.getElementById('stat-pendentes').textContent = stats.pendentesAntigos || 0;
        document.getElementById('stat-finalizados').textContent = stats.totalFinalizados || 0;
        document.getElementById('stat-novos-label').textContent = (document.getElementById('dashDataInicio').value || document.getElementById('dashDataFim').value) ? 'Novos no Período' : 'Novos na Semana';

        // 2. Top 5 Types Chart (Bar Chart)
        if (tiposChartInstance) { tiposChartInstance.destroy(); }
        const tiposCtx = document.getElementById('tiposChart').getContext('2d');
        tiposChartInstance = new Chart(tiposCtx, {
            type: 'bar',
            data: {
                labels: stats.topTipos.map(item => item.tipo_requerimento),
                datasets: [{
                    label: 'Total',
                    data: stats.topTipos.map(item => item.total),
                    backgroundColor: ['#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B', '#FFC107'],
                    borderColor: '#fff',
                    borderWidth: 1
                }]
            },
            options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
        });

        // 3. Dynamic Pie Chart (Status or Type)
        if (statusChartInstance) { statusChartInstance.destroy(); }
        const statusCtx = document.getElementById('statusChart').getContext('2d');
        const pieChartDataType = document.getElementById('pieChartDataType').value;

        let pieChartLabels, pieChartData, pieChartTitle;

        if (pieChartDataType === 'status') {
            pieChartLabels = stats.statusProtocolos.map(item => item.status);
            pieChartData = stats.statusProtocolos.map(item => item.total);
            pieChartTitle = 'Protocolos por Status (no Período)';
        } else { // 'tipo'
            pieChartLabels = stats.todosTipos.map(item => item.tipo_requerimento);
            pieChartData = stats.todosTipos.map(item => item.total);
            pieChartTitle = 'Protocolos por Tipo (no Período)';
        }

        document.getElementById('pieChartTitle').textContent = pieChartTitle;

        statusChartInstance = new Chart(statusCtx, {
            type: 'pie',
            data: {
                labels: pieChartLabels,
                datasets: [{
                    label: 'Total',
                    data: pieChartData,
                    backgroundColor: ['#2196F3', '#FF9800', '#4CAF50', '#F44336', '#9C27B0', '#673AB7', '#009688', '#FF5722', '#795548', '#607D8B'],
                }]
            },
            options: { responsive: true, plugins: { legend: { position: 'right' } } }
        });

        // 4. Evolution Chart (Line Chart)
        if (evolucaoChartInstance) { evolucaoChartInstance.destroy(); }
        const evolucaoCtx = document.getElementById('evolucaoChart').getContext('2d');
        const evolucaoAgrupamento = document.getElementById('evolucaoAgrupamento').value;
        const evolucaoPeriodoSelect = document.getElementById('evolucaoPeriodo');
        const evolucaoPeriodoTexto = evolucaoPeriodoSelect.options[evolucaoPeriodoSelect.selectedIndex].text;

        document.getElementById('evolucaoChartTitle').textContent = `Evolução de Novos Protocolos (${evolucaoPeriodoTexto})`;

        evolucaoChartInstance = new Chart(evolucaoCtx, {
            type: 'line',
            data: {
                labels: stats.evolucaoProtocolos.map(item => {
                    const date = new Date(item.intervalo);
                    // Adjust for timezone issues by treating date as UTC
                    const userTimezoneOffset = date.getTimezoneOffset() * 60000;
                    return new Date(date.getTime() + userTimezoneOffset).toLocaleDateString('pt-BR', {
                        day: '2-digit',
                        month: evolucaoAgrupamento === 'month' ? 'long' : '2-digit',
                        year: 'numeric'
                    });
                }),
                datasets: [{
                    label: 'Novos Protocolos',
                    data: stats.evolucaoProtocolos.map(item => item.total),
                    fill: true,
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.2)',
                    tension: 0.2
                }]
            },
            options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });

    } catch (err) {
        console.error("Erro ao carregar dados do dashboard:", err);
        alert("Não foi possível carregar os dados do dashboard: " + err.message);
    }
};

window.imprimirDashboard = function() {
    window.print();
};

window.abrirModalImpressao = function() {
    document.getElementById('modalImpressaoDashboard').style.display = 'flex';
};

window.gerarImpressaoPersonalizada = async function() {
    const previewContent = document.getElementById('previewContent');
    previewContent.innerHTML = '<h4>Carregando pré-visualização...</h4>';
    fecharModal('modalImpressaoDashboard');
    document.getElementById('modalPreviewImpressao').style.display = 'flex';

    const checkboxes = document.querySelectorAll('#print-options-container input[name="print-item"]:checked');
    const selectors = Array.from(checkboxes).map(cb => cb.value);

    const chartSelectors = ['#tiposChart', '#statusChart', '#evolucaoChart'];
    const selectedCharts = chartSelectors.filter(sel => selectors.includes(sel));

    const imagePromises = selectedCharts.map(selector => {
        return new Promise((resolve) => {
            const canvas = document.querySelector(selector);
            // Wait for the next animation frame to ensure chart is rendered
            requestAnimationFrame(() => {
                const img = new Image();
                img.onload = () => resolve({ selector, image: img });
                img.onerror = () => resolve({ selector, image: null }); // Handle error
                img.src = canvas.toDataURL('image/png');
            });
        });
    });

    const loadedCharts = await Promise.all(imagePromises);
    const chartImageMap = loadedCharts.reduce((map, item) => {
        if (item.image) map[item.selector] = item.image;
        return map;
    }, {});

    // Build filters HTML
    let filtrosHtml = '';
    const dataInicio = document.getElementById('dashDataInicio').value;
    const dataFim = document.getElementById('dashDataFim').value;
    const status = document.getElementById('dashStatus').value;
    const tipo = document.getElementById('dashTipo').value;
    const lotacao = document.getElementById('dashLotacao').value;

    if (dataInicio) filtrosHtml += `<strong>Data de Início:</strong> ${new Date(dataInicio+'T00:00:00').toLocaleDateString('pt-BR')} | `;
    if (dataFim) filtrosHtml += `<strong>Data Final:</strong> ${new Date(dataFim+'T00:00:00').toLocaleDateString('pt-BR')} | `;
    if (status) filtrosHtml += `<strong>Status:</strong> ${status} | `;
    if (tipo) filtrosHtml += `<strong>Tipo:</strong> ${tipo} | `;
    if (lotacao) filtrosHtml += `<strong>Lotação:</strong> ${lotacao} | `;
    if (filtrosHtml) filtrosHtml = filtrosHtml.slice(0, -3); // Remove last " | "

    let html = `
        <div style="text-align: center; margin-bottom: 5px; padding-bottom: 5px; border-bottom: 1px solid #ccc;">
            <img src="/static/img/logo.png" alt="Logo" style="height: 45px; margin-bottom: 5px;">
            <h3 style="margin: 0; font-size: 1.1em;">Relatório de Desempenho - Dashboard</h3>
            <p style="font-size: 0.7em; color: #555; margin: 2px 0 0 0;">Gerado em: ${new Date().toLocaleString('pt-BR')}</p>
        </div>
        <div style="font-size: 0.7em; padding: 5px; margin-bottom: 10px; background-color: #f5f5f5; border-radius: 4px; text-align: center;">
            ${filtrosHtml ? filtrosHtml : 'Nenhum filtro principal aplicado.'}
        </div>
    `;

    html += '<table style="width: 100%; border-collapse: collapse; page-break-inside: auto;"><tbody>';

    // Cards Row
    if (selectors.includes('.dashboard-cards')) {
        const cardNovos = document.querySelector('#card-novos').innerHTML;
        const cardPendentes = document.querySelector('#card-pendentes').innerHTML;
        const cardFinalizados = document.querySelector('#card-finalizados').innerHTML;
        html += `
            <tr>
                <td>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="vertical-align: top; text-align: center;">
                            <td style="width: 33%; border: 1px solid #eee; padding: 5px; border-radius: 8px;">${cardNovos}</td>
                            <td style="width: 33%; border: 1px solid #eee; padding: 5px; border-radius: 8px;">${cardPendentes}</td>
                            <td style="width: 33%; border: 1px solid #eee; padding: 5px; border-radius: 8px;">${cardFinalizados}</td>
                        </tr>
                    </table>
                </td>
            </tr>
        `;
    }

    // Smaller Charts Row
    const tiposChartSelected = selectors.includes('#tiposChart') && chartImageMap['#tiposChart'];
    const statusChartSelected = selectors.includes('#statusChart') && chartImageMap['#statusChart'];
    if (tiposChartSelected || statusChartSelected) {
        html += `
            <tr><td style="height: 5px;"></td></tr>
            <tr>
                <td>
                    <table style="width: 100%; border-collapse: collapse;"><tr style="vertical-align: top; text-align: center;">
        `;
        if (tiposChartSelected) {
            html += `<td style="width: 50%; padding-right: 2.5px; box-sizing: border-box;">
                        <div style="border: 1px solid #eee; border-radius: 8px; padding: 10px;">
                            <h4 style="font-size: 0.9em; margin: 0 0 5px 0;">Top 5 Tipos de Requerimento</h4>
                            <img src="${chartImageMap['#tiposChart'].src}" style="width: 100%; height: auto;">
                        </div>
                     </td>`;
        }
        if (statusChartSelected) {
            html += `<td style="width: 50%; padding-left: 2.5px; box-sizing: border-box;">
                        <div style="border: 1px solid #eee; border-radius: 8px; padding: 10px;">
                            <h4 style="font-size: 0.9em; margin: 0 0 5px 0;">${document.getElementById('pieChartTitle').textContent}</h4>
                            <img src="${chartImageMap['#statusChart'].src}" style="width: 100%; height: auto;">
                        </div>
                     </td>`;
        }
        html += `</tr></table></td></tr>`;
    }

    // Evolution Chart Row
    if (selectors.includes('#evolucaoChart') && chartImageMap['#evolucaoChart']) {
        html += `
            <tr><td style="height: 5px;"></td></tr>
            <tr>
                <td>
                    <div style="border: 1px solid #eee; border-radius: 8px; padding: 10px; text-align: center;">
                        <h4 style="font-size: 0.9em; margin: 0 0 5px 0;">${document.getElementById('evolucaoChartTitle').textContent}</h4>
                        <img src="${chartImageMap['#evolucaoChart'].src}" style="width: 90%; height: auto; margin: 0 auto;">
                    </div>
                </td>
            </tr>`;
    }

    html += '</tbody></table>';
    previewContent.innerHTML = html;
};

window.salvarDashboardPersonalizadoPDF = async function() {
    const content = document.getElementById('previewContent');
    const button = document.querySelector('#modalPreviewImpressao button.btn-primary');

    button.textContent = 'Gerando...';
    button.disabled = true;

    const opt = {
        margin: 5,
        filename: 'Dashboard_Personalizado.pdf',
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };

    try {
        await html2pdf().set(opt).from(content).save();
    } catch (err) {
        console.error('Erro ao gerar PDF personalizado:', err);
        alert('Ocorreu um erro ao gerar o PDF.');
    } finally {
        button.textContent = 'Salvar PDF';
        button.disabled = false;
        fecharModal('modalPreviewImpressao');
    }
};

// --- Modal Action Functions ---
window.handleStatusChange = function(selectElement) {
    const customInputContainer = document.getElementById('statusCustomContainer');
    customInputContainer.style.display = selectElement.value === 'Outro' ? 'block' : 'none';
};

window.confirmarEncaminhamento = async function() {
    const protocoloId = document.getElementById('encaminharProtocoloId').value;
    const novoResponsavel = document.getElementById('selectUsuarioEncaminhar').value;
    const observacao = document.getElementById('observacaoEncaminhamento').value;

    if (!novoResponsavel) {
        alert('Por favor, selecione um usuário para encaminhar.');
        return;
    }

    const data = {
        protocoloId: protocoloId,
        novoStatus: 'Encaminhado', // O status é fixo para 'Encaminhado'
        novoResponsavel: novoResponsavel,
        observacao: `Encaminhado para ${novoResponsavel}. Observação: ${observacao}`
    };

    try {
        const response = await fetch('/protocolos/atualizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.sucesso) {
            alert('Protocolo encaminhado com sucesso!');
            // Fecha o modal e recarrega a página para ver a mudança
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalEncaminhar'));
            modal.hide();
            window.location.reload();
        } else {
            throw new Error(result.mensagem || 'Erro desconhecido');
        }
    } catch (error) {
        alert(`Erro ao encaminhar protocolo: ${error.message}`);
        console.error(error);
    }
};

window.confirmarAtualizacaoStatus = async function() {
    const protocoloId = document.getElementById('atualizarProtocoloId').value;
    const statusSelect = document.getElementById('statusSelect');
    let novoStatus = statusSelect.value;

    if (novoStatus === 'Outro') {
        novoStatus = document.getElementById('statusCustom').value.trim();
        if (!novoStatus) {
            alert('Por favor, digite o status personalizado.');
            return;
        }
    }

    const observacao = document.getElementById('observacaoAtualizacao').value;

    const data = {
        protocoloId: protocoloId,
        novoStatus: novoStatus,
        // Ao apenas atualizar o status, o responsável não muda, a menos que seja um encaminhamento.
        // O responsável pela ação é o 'current_user' no backend.
        observacao: observacao
    };

    try {
        const response = await fetch('/protocolos/atualizar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.sucesso) {
            alert('Status do protocolo atualizado com sucesso!');
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalAtualizarStatus'));
            modal.hide();
            window.location.reload();
        } else {
            throw new Error(result.mensagem || 'Erro desconhecido');
        }
    } catch (error) {
        alert(`Erro ao atualizar status: ${error.message}`);
        console.error(error);
    }
};

// --- Protocol Form Functions ---
function initializeProtocolForm() {
    // These values are injected by the template in 'edit' mode.
    const initialData = window.protocoloData || {};

    // Populate dropdowns and then set the initial value if it exists.
    populateDropdown('/api/lotacoes', 'lotacao', initialData.lotacao);
    populateDropdown('/api/tipos_requerimento', 'tipo', initialData.tipo_requerimento);
    populateDropdown('/api/bairros', 'bairro', initialData.bairro);

    // Add event listeners
    document.getElementById('matricula').addEventListener('blur', fetchServidorByMatricula);
    document.getElementById('cep').addEventListener('blur', fetchCep);

    // Attach listener for the server search button directly
    const btnBuscarNome = document.getElementById('btnBuscarNome');
    if (btnBuscarNome) {
        btnBuscarNome.addEventListener('click', openServidorSearchModal);
    }

    const buscaInput = document.getElementById('buscaNomeInput');
    if (buscaInput) {
        buscaInput.addEventListener('input', searchServidorByName);
    }

    const imprimirBtn = document.getElementById('imprimirBtn');
    if (imprimirBtn) {
        imprimirBtn.addEventListener('click', () => previsualizarPDF(null, true));
    }

    // Only generate a new protocol number if we are not in edit mode.
    if (!initialData.numero) {
        gerarNumeroProtocolo();
    }

    // Only set the current date if we are not in edit mode.
    const dataSolicitacaoInput = document.getElementById('dataSolicitacao');
    if (!dataSolicitacaoInput.value) {
        dataSolicitacaoInput.value = new Date().toISOString().split('T')[0];
    }
}

async function populateDropdown(apiUrl, elementId, selectedValue = null) {
    const select = document.getElementById(elementId);
    if (!select) {
        console.error(`Dropdown element with id '${elementId}' not found.`);
        return;
    }

    // Store the selected value from the template, if any.
    const initialValue = selectedValue || select.value;

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) throw new Error(`Network response was not ok for ${apiUrl}`);
        const data = await response.json();

        // Clear existing options except for the placeholder
        select.innerHTML = '<option value="">Selecione...</option>';

        data.forEach(item => {
            const option = new Option(item, item);
            select.add(option);
        });

        // Set the value if it was provided
        if (initialValue) {
            select.value = initialValue;
            if (select.value !== initialValue) {
                console.warn(`Value "${initialValue}" for dropdown ${elementId} not found in active options. Adding it to the list.`);
                const oldOption = new Option(initialValue, initialValue, true, true);
                select.add(oldOption);
            }
        }
    } catch (error) {
        console.error(`Failed to populate dropdown ${elementId}:`, error);
        select.innerHTML = '<option value="" disabled>Erro ao carregar</option>';
    }
}

async function fetchServidorByMatricula() {
    const matriculaInput = document.getElementById('matricula');
    const matricula = matriculaInput.value.trim();

    if (!matricula) {
        preencherCamposServidor(null); // Limpa os campos se a matrícula for removida
        return;
    }

    try {
        // Usa a rota correta da API definida em app.py
        const response = await fetch(`/api/servidor/${encodeURIComponent(matricula)}`);
        const servidor = await response.json();

        if (response.ok) {
            preencherCamposServidor(servidor);
        } else {
            console.warn(servidor.error || 'Servidor não encontrado');
            preencherCamposServidor(null); // Limpa os campos se não encontrar
        }
    } catch (error) {
        console.error('Erro ao buscar servidor por matrícula:', error);
        preencherCamposServidor(null); // Limpa os campos em caso de erro de rede
    }
}

async function fetchCep() {
    const cepInput = document.getElementById('cep');
    const cep = cepInput.value.replace(/\D/g, ''); // Remove non-digit characters

    if (cep.length !== 8) {
        // Don't alert if the field is empty, just if it's invalid
        if (cep.length > 0) {
            console.warn('CEP inválido.');
        }
        return;
    }

    try {
        const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        if (!response.ok) {
            throw new Error('Erro na resposta da API do ViaCEP');
        }
        const data = await response.json();

        if (data.erro) {
            console.warn('CEP não encontrado!');
            // Optionally clear fields or notify user
            return;
        }

        // Preenche os campos de endereço
        document.getElementById('endereco').value = data.logradouro || '';
        document.getElementById('municipio').value = data.localidade || '';

        const bairroSelect = document.getElementById('bairro');
        const bairroNome = data.bairro || '';

        if (bairroNome) {
            // Verifica se a opção já existe
            let optionExists = [...bairroSelect.options].some(option => option.value.toLowerCase() === bairroNome.toLowerCase());

            if (optionExists) {
                // Seleciona a opção existente
                bairroSelect.value = [...bairroSelect.options].find(option => option.value.toLowerCase() === bairroNome.toLowerCase()).value;
            } else {
                // Adiciona e seleciona a nova opção se não existir
                // Isso pode não ser o ideal se a lista de bairros for estritamente controlada pelo backend
                console.warn(`Bairro "${bairroNome}" não encontrado na lista, adicionando temporariamente.`);
                const newOption = new Option(bairroNome, bairroNome, true, true);
                bairroSelect.add(newOption);
            }
        }

    } catch (error) {
        console.error('Erro ao buscar CEP:', error);
        // Optionally notify user of the error
    }
}

function preencherCamposServidor(servidor) {
    const nomeInput = document.getElementById('nome');
    const lotacaoSelect = document.getElementById('lotacao');
    const cargoInput = document.getElementById('cargo');
    const unidadeInput = document.getElementById('unidade');

    if (servidor && servidor.nome) {
        nomeInput.value = servidor.nome;
        cargoInput.value = servidor.cargo || '';
        unidadeInput.value = servidor.unidade_de_exercicio || '';

        // Para o select de lotação, precisamos verificar se a opção existe
        const lotacaoValue = servidor.lotacao || '';
        let optionExists = [...lotacaoSelect.options].some(opt => opt.value === lotacaoValue);

        if (optionExists) {
            lotacaoSelect.value = lotacaoValue;
        } else if (lotacaoValue) {
            // Se a opção não existe, podemos adicioná-la dinamicamente
            console.warn(`Lotação "${lotacaoValue}" não encontrada. Adicionando à lista.`);
            const newOption = new Option(lotacaoValue, lotacaoValue, true, true);
            lotacaoSelect.add(newOption);
        } else {
             lotacaoSelect.value = '';
        }

    } else {
        // Limpa os campos se nenhum servidor for encontrado ou se os dados forem nulos
        nomeInput.value = '';
        lotacaoSelect.value = '';
        cargoInput.value = '';
        unidadeInput.value = '';
    }
}


function openServidorSearchModal() {
    const modalElement = document.getElementById('modalBuscaServidor');
    if (modalElement) {
        const modal = new bootstrap.Modal(modalElement);
        document.getElementById('buscaNomeInput').value = '';
        document.getElementById('buscaNomeResultados').innerHTML = '';
        modal.show();
    }
}

async function searchServidorByName() {
    const searchTerm = this.value.trim();
    const resultadosDiv = document.getElementById('buscaNomeResultados');
    if (searchTerm.length < 3) {
        resultadosDiv.innerHTML = '<p class="text-center text-muted">Digite ao menos 3 caracteres.</p>';
        return;
    }
    try {
        const response = await fetch(`/api/servidores/search?nome=${encodeURIComponent(searchTerm)}`);
        const servidores = await response.json();
        resultadosDiv.innerHTML = ''; // Clear previous results
        if (servidores.error) {
            resultadosDiv.innerHTML = `<p class="text-danger">${servidores.error}</p>`;
            return;
        }
        if (servidores.length > 0) {
            servidores.forEach(servidor => {
                const div = document.createElement('a'); // Use 'a' tag for list-group-item-action
                div.href = '#';
                div.className = 'list-group-item list-group-item-action';
                div.innerHTML = `<strong>${servidor.nome}</strong><br><small>Matrícula: ${servidor.matricula}</small>`;
                div.onclick = (e) => {
                    e.preventDefault();
                    preencherCamposServidor(servidor);
                    const modal = bootstrap.Modal.getInstance(document.getElementById('modalBuscaServidor'));
                    modal.hide();
                };
                resultadosDiv.appendChild(div);
            });
        } else {
            resultadosDiv.innerHTML = '<p class="text-center">Nenhum servidor encontrado.</p>';
        }
    } catch (error) {
        console.error('Erro ao buscar servidor por nome:', error);
        resultadosDiv.innerHTML = '<p class="text-danger text-center">Erro ao conectar com o servidor.</p>';
    }
}

// --- PDF Generation and Modal Functions (NEW) ---

let protocoloParaGerar = null;

window.fecharModal = function(modalId) {
    const modalElement = document.getElementById(modalId);
    if (modalElement) {
        const modalInstance = bootstrap.Modal.getInstance(modalElement);
        if (modalInstance) {
            modalInstance.hide();
        }
    }
}

window.previsualizarPDF = async function(id = null, isFromForm = false) {
  let protocolo;
  if (isFromForm) {
      protocolo = {
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
      try {
          const res = await fetch(`/api/protocolo/${id}`);
          if (!res.ok) { alert("Protocolo não encontrado"); return; }
          protocolo = await res.json();
      } catch (err) {
          console.error('Erro ao buscar protocolo:', err);
          alert('Erro ao buscar dados do protocolo.');
          return;
      }
  }

  protocoloParaGerar = protocolo;
  const pdfContentDiv = document.getElementById('pdfContent');
  const modeloDiv = document.getElementById('modeloProtocolo');
  if (!pdfContentDiv || !modeloDiv) { console.error("Elementos do modal ou template não encontrados."); return; }

  const clone = modeloDiv.cloneNode(true);
  clone.style.display = 'block';

  const qrcodeContainer = clone.querySelector('#qrcode-container');
  if (qrcodeContainer && protocolo.numero && protocolo.numero.includes('/')) {
      qrcodeContainer.innerHTML = '';
      const numeroParts = protocolo.numero.split('/');
      if (numeroParts.length === 2) {
          const urlConsulta = `${window.location.origin}/consulta/${numeroParts[1]}/${numeroParts[0]}`;
          new QRCode(qrcodeContainer, { text: urlConsulta, width: 90, height: 90, correctLevel: QRCode.CorrectLevel.H });
      }
  }

  clone.querySelector('#doc_numero').textContent = protocolo.numero || 'A ser gerado';
  let dataTexto = protocolo.data_solicitacao ? new Date(protocolo.data_solicitacao + 'T00:00:00').toLocaleDateString('pt-BR') : new Date().toLocaleDateString('pt-BR');
  clone.querySelector('#doc_dataSolicitacao').textContent = dataTexto;
  clone.querySelector('#doc_nome').textContent = protocolo.nome || '';
  clone.querySelector('#doc_matricula').textContent = protocolo.matricula || '';
  clone.querySelector('#doc_cpf').textContent = protocolo.cpf || '';
  clone.querySelector('#doc_rg').textContent = protocolo.rg || '';
  clone.querySelector('#doc_endereco').textContent = protocolo.endereco || '';
  clone.querySelector('#doc_bairro').textContent = protocolo.bairro || '';
  clone.querySelector('#doc_municipio').textContent = protocolo.municipio || '';
  clone.querySelector('#doc_cep').textContent = protocolo.cep || '';
  clone.querySelector('#doc_telefone').textContent = protocolo.telefone || '';
  clone.querySelector('#doc_cargo').textContent = protocolo.cargo || '';
  clone.querySelector('#doc_lotacao').textContent = protocolo.lotacao || '';
  clone.querySelector('#doc_unidade').textContent = protocolo.unidade_exercicio || '';
  clone.querySelector('#doc_tipo').textContent = protocolo.tipo_requerimento || '';
  clone.querySelector('#doc_requerAo').textContent = protocolo.requer_ao || '';
  clone.querySelector('#doc_complemento').innerHTML = protocolo.observacoes ? protocolo.observacoes.replace(/\n/g, '<br>') : 'Nenhuma informação adicional.';

  pdfContentDiv.innerHTML = '';
  pdfContentDiv.appendChild(clone.querySelector('.pdf-body'));

  const pdfModal = new bootstrap.Modal(document.getElementById('pdfModal'));
  pdfModal.show();
}

window.gerarPDF = async function() {
  if (!protocoloParaGerar) { alert("Nenhum protocolo para gerar."); return; }
  const element = document.getElementById('pdfContent').querySelector('.doc-container');
  const opt = {
    margin: [0, 0, 0, 0],
    filename: `Protocolo_${(protocoloParaGerar.numero || 'Novo').replace(/[\/\\]/g, '-')}.pdf`,
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, scrollY: 0, useCORS: true },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
  };
  try {
    await html2pdf().set(opt).from(element).save();
    fecharModal('pdfModal');
  } catch (error) {
    console.error("Erro ao gerar PDF:", error);
    alert("Ocorreu um erro ao gerar o PDF.");
  }
}

async function gerarNumeroProtocolo() {
    const anoAtual = new Date().getFullYear();
    try {
        const res = await fetch(`/protocolos/ultimoNumero/${anoAtual}`);
        if (!res.ok) throw new Error('Failed to fetch last protocol number');
        const data = await res.json();
        document.getElementById('numeroProtocolo').value = `${String((data.ultimo || 0) + 1).padStart(4, '0')}/${anoAtual}`;
    } catch (error) {
        console.error("Erro ao gerar número:", error);
        document.getElementById('numeroProtocolo').value = `0001/${anoAtual}`;
    }
}
