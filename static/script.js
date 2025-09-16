// =================================================================================
// GLOBAL MODAL AND UI INITIALIZATION
// =================================================================================
document.addEventListener('DOMContentLoaded', function () {
    // --- Dashboard Initialization ---
    // Checks for a unique element on the dashboard page before running its JS
    if (document.getElementById('dashboard-header')) {
        initializeDashboard();
    }

    // --- Protocol Form Initialization ---
    // Checks for a unique element on the form page before running its JS
    if (document.getElementById('protocol-form')) {
        initializeProtocolForm();
    }

    // --- Modal Listeners for Protocol List Page ---
    // These listeners are for modals that might be included in layout.html
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
                if (!response.ok) return;
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

// =================================================================================
// DASHBOARD PAGE LOGIC
// =================================================================================
function initializeDashboard() {
    // This function is page-specific and guarded by the DOMContentLoaded check.
    // Original logic seems fine.
}

// =================================================================================
// PROTOCOL FORM PAGE LOGIC (`/protocolo/novo`)
// =================================================================================
function initializeProtocolForm() {
    // This entire function is guarded by `if (document.getElementById('protocol-form'))`

    // --- Helper Functions (scoped to this initialization) ---
    async function populateDropdown(apiUrl, elementId) {
        const select = document.getElementById(elementId);
        if (!select) return;
        try {
            const response = await fetch(apiUrl);
            if (!response.ok) throw new Error('Network response was not ok');
            const data = await response.json();
            select.innerHTML = '<option value="">Selecione...</option>';
            data.forEach(item => {
                const option = new Option(item, item);
                select.add(option);
            });
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
            console.error('Erro ao buscar servidor:', error);
        }
    }

    function preencherCamposServidor(servidor) {
        if(!servidor) return;
        document.getElementById('nome').value = servidor.nome || '';
        document.getElementById('lotacao').value = servidor.lotacao || '';
        document.getElementById('cargo').value = servidor.cargo || '';
        document.getElementById('unidade').value = servidor.unidade_exercicio || '';
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
        if (!resultadosDiv) return;
        if (searchTerm.length < 3) {
            resultadosDiv.innerHTML = '<p class="text-center text-muted">Digite ao menos 3 caracteres.</p>';
            return;
        }
        try {
            const response = await fetch(`/api/servidores/search?nome=${encodeURIComponent(searchTerm)}`);
            const servidores = await response.json();
            resultadosDiv.innerHTML = '';
            if (servidores.error) {
                resultadosDiv.innerHTML = `<p class="text-danger">${servidores.error}</p>`;
                return;
            }
            if (servidores.length > 0) {
                servidores.forEach(servidor => {
                    const div = document.createElement('a');
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
            console.error('Erro ao buscar servidor:', error);
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

    // --- Execution for this page ---
    populateDropdown('/api/lotacoes', 'lotacao');
    populateDropdown('/api/tipos_requerimento', 'tipo');
    populateDropdown('/api/bairros', 'bairro');

    document.getElementById('matricula').addEventListener('blur', fetchServidorByMatricula);
    document.getElementById('btnBuscarNome').addEventListener('click', openServidorSearchModal);
    document.getElementById('buscaNomeInput').addEventListener('input', searchServidorByName);
    document.getElementById('imprimirBtn').addEventListener('click', () => window.previsualizarPDF(null, true));

    gerarNumeroProtocolo();
    const dataSolicitacaoInput = document.getElementById('dataSolicitacao');
    if (dataSolicitacaoInput && !dataSolicitacaoInput.value) {
        dataSolicitacaoInput.value = new Date().toISOString().split('T')[0];
    }
}


// =================================================================================
// GLOBALLY AVAILABLE FUNCTIONS (MODAL ACTIONS, PDF)
// =================================================================================
let protocoloParaGerar = null;

window.fecharModal = function(modalId) {
    const modalEl = document.getElementById(modalId);
    if(modalEl) {
        const modalInstance = bootstrap.Modal.getInstance(modalEl);
        if (modalInstance) {
            modalInstance.hide();
        } else {
            modalEl.style.display = 'none';
        }
    }
}

window.previsualizarPDF = async function(id = null, isFromForm = false) {
  let protocolo;
  if (isFromForm) {
      protocolo = {
          numero: document.getElementById('numeroProtocolo')?.value,
          data_solicitacao: document.getElementById('dataSolicitacao')?.value,
          nome: document.getElementById('nome')?.value,
          matricula: document.getElementById('matricula')?.value,
          cpf: document.getElementById('cpf')?.value,
          rg: document.getElementById('rg')?.value,
          endereco: document.getElementById('endereco')?.value,
          bairro: document.getElementById('bairro')?.value,
          municipio: document.getElementById('municipio')?.value,
          cep: document.getElementById('cep')?.value,
          telefone: document.getElementById('telefone')?.value,
          cargo: document.getElementById('cargo')?.value,
          lotacao: document.getElementById('lotacao')?.value,
          unidade_exercicio: document.getElementById('unidade')?.value,
          tipo_requerimento: document.getElementById('tipo')?.value,
          requer_ao: document.getElementById('requerAo')?.value,
          observacoes: document.getElementById('complemento')?.value
      };
  } else {
      if (id === null) { alert('ID do protocolo não fornecido.'); return; }
      try {
          const res = await fetch(`/api/protocolo/${id}`);
          if (!res.ok) { alert("Erro: Protocolo não encontrado."); return; }
          protocolo = await res.json();
      } catch (err) {
          console.error('Erro ao buscar dados do protocolo:', err);
          return;
      }
  }

  protocoloParaGerar = protocolo;
  const pdfContentDiv = document.getElementById('pdfContent');
  const modeloDiv = document.getElementById('modeloProtocolo');
  if (!pdfContentDiv || !modeloDiv) { return; }

  const clone = modeloDiv.cloneNode(true);
  clone.style.display = 'block';

  const qrcodeContainer = clone.querySelector('#qrcode-container');
  if (qrcodeContainer && protocolo.numero && protocolo.numero.includes('/')) {
      qrcodeContainer.innerHTML = '';
      const numeroParts = protocolo.numero.split('/');
      if (numeroParts.length === 2) {
          const urlConsulta = `${window.location.origin}/consulta/${numeroParts[1]}/${numeroParts[0]}`;
          try {
            new QRCode(qrcodeContainer, { text: urlConsulta, width: 90, height: 90, correctLevel: QRCode.CorrectLevel.H });
          } catch(e) { console.error("Erro ao gerar QRCode.", e); }
      }
  }

  clone.querySelector('#doc_numero').textContent = protocolo.numero || '';
  clone.querySelector('#doc_dataSolicitacao').textContent = protocolo.data_solicitacao ? new Date(protocolo.data_solicitacao + 'T00:00:00').toLocaleDateString('pt-BR') : '';
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
  clone.querySelector('#doc_complemento').innerHTML = protocolo.observacoes ? protocolo.observacoes.replace(/\n/g, '<br>') : '';

  pdfContentDiv.innerHTML = '';
  pdfContentDiv.appendChild(clone.querySelector('.pdf-body'));

  const pdfModal = document.getElementById('pdfModal');
  if (pdfModal) {
      const modal = new bootstrap.Modal(pdfModal);
      modal.show();
  }
}

window.gerarPDF = async function() {
  if (!protocoloParaGerar) { alert("Nenhum protocolo selecionado."); return; }
  const element = document.getElementById('pdfContent').querySelector('.doc-container');
  if (!element) { return; }
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
  }
}
