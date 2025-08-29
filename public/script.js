async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('protocolo-token');
    const headers = { 'Content-Type': 'application/json', ...options.headers };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const finalOptions = { ...options, headers };
    const response = await fetch(url, finalOptions);
    if (response.status === 401 || response.status === 403) {
        console.error("Token inválido ou expirado. Fazendo logout.");
        sair();
        throw new Error("Token inválido ou expirado.");
    }
    return response;
}

// Variáveis Globais
const itensPorPagina = 10;
let paginaAtualTodos = 1;
let paginaAtualMeus = 1;
let tiposChartInstance = null;
let protocoloParaGerar = null; // Adicionado para a função de PDF
window.opcoesTipos = [];
window.opcoesLotacoes = [];

// Funções de Inicialização (executadas quando o DOM estiver pronto)
document.addEventListener('DOMContentLoaded', () => {
    window.usuarioLogado = localStorage.getItem('usuarioLogado') || "";
    window.nivelUsuario = localStorage.getItem('nivelUsuario') || "";
    window.usuarioLogin = localStorage.getItem('usuarioLogin') || "";

    document.body.classList.remove('loading');

    if (window.usuarioLogado) {
        document.getElementById('btnDashboard').style.display = (window.nivelUsuario === 'admin' || window.nivelUsuario === 'padrao') ? 'flex' : 'none';
        document.getElementById('btnConfig').style.display = window.nivelUsuario === "admin" ? "flex" : "none";
        document.getElementById('btnNovo').style.display = (window.nivelUsuario === "admin" || window.nivelUsuario === "padrao" || window.nivelUsuario === "usuario") ? "flex" : "none";
        document.getElementById('btnRelatorios').style.display = (window.nivelUsuario === "admin" || window.nivelUsuario === "padrao") ? "flex" : "none";
        document.getElementById('btnTodosProtocolos').style.display = (window.nivelUsuario === 'admin' || window.nivelUsuario === 'padrao') ? 'flex' : 'none';

        carregarOpcoesDropdowns().then(() => {
            mostrarTela('menu'); // Sempre vai para o menu após o login
            verificarNotificacoes();
        });

    } else {
        mostrarTela('login');
    }

    document.getElementById('matricula').addEventListener('blur', async function() {
        const matricula = this.value.trim();
        if (!matricula) { preencherCamposServidor(null); return; }
        try {
            const response = await fetchWithAuth(`/protocolos/servidor/${encodeURIComponent(matricula)}`);
            if (!response.ok) { return; }
            const servidor = await response.json();
            preencherCamposServidor(servidor);
        } catch (error) { console.error('Erro ao buscar servidor:', error); }
    });

    document.getElementById('cep').addEventListener('blur', async function () {
        const cep = this.value.replace(/\D/g, '');
        if (cep.length !== 8) {
            if(cep.length > 0) alert('CEP inválido. Digite os 8 dígitos.');
            return;
        }
        try {
            const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
            const data = await response.json();
            if (data.erro) { alert('CEP não encontrado!'); return; }
            document.getElementById('endereco').value = data.logradouro || '';
            document.getElementById('bairro').value = data.bairro || '';
            document.getElementById('municipio').value = data.localidade || '';
        } catch (error) { console.error('Erro ao buscar CEP:', error); alert('Erro ao buscar o CEP.'); }
    });
});

// Funções Globais (acessíveis via onclick)
window.logar = async function() {
    const user = document.getElementById('usuario').value;
    const senha = document.getElementById('senha').value;
    const msg = document.getElementById('loginMsg');
    try {
        const res = await fetch('/login', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ login: user, senha: senha })
        });
        const data = await res.json();
        if (data.sucesso && data.usuario && data.token) {
            localStorage.setItem('protocolo-token', data.token);
            localStorage.setItem('usuarioLogado', data.usuario.nome);
            localStorage.setItem('usuarioLogin', data.usuario.login);
            localStorage.setItem('nivelUsuario', data.usuario.tipo);
            window.location.reload();
        } else {
            msg.textContent = "Usuário ou senha incorretos.";
        }
    } catch(err) { console.error("Erro no login:", err); msg.textContent = "Erro ao conectar ao servidor."; }
};
window.sair = function() {
    localStorage.clear();
    window.location.reload();
};
window.mostrarTela = async function(tela) {
    ['login','menu','dashboard','form','config','protocolos','meusProtocolos','relatorios'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('active');
    });
    document.getElementById(tela).classList.add('active');

    if (tela === 'meusProtocolos') {
        const usuarioLogin = localStorage.getItem('usuarioLogin');
        if (usuarioLogin) {
            try {
                await fetchWithAuth('/protocolos/notificacoes/ler', {
                    method: 'POST', body: JSON.stringify({ usuarioLogin })
                });
                await verificarNotificacoes();
            } catch (err) { console.error('Erro ao marcar notificações como lidas:', err); }
        }
    }

    if (tela === 'protocolos') listarProtocolos();
    if (tela === 'meusProtocolos') listarMeusProtocolos();
    if (tela === 'form') { popularDropdownsFormulario(); gerarNumeroProtocolo(); }
    if (tela === 'config') { atualizarListaUsuarios(); carregarTabelaGestao('tipos'); carregarTabelaGestao('lotacoes'); }
    if (tela === 'relatorios') { popularFiltrosRelatorio(); pesquisarProtocolos(); }
    if (tela === 'dashboard') { popularFiltrosDashboard(); carregarDashboard(); }
};
window.gerarNumeroProtocolo = async function() {
  const anoAtual = new Date().getFullYear();
  try {
    const res = await fetchWithAuth(`/protocolos/ultimoNumero/${anoAtual}`);
    const data = await res.json();
    document.getElementById('numeroProtocolo').value = `${String((data.ultimo || 0) + 1).padStart(4, '0')}/${anoAtual}`;
  } catch (error) { console.error("Erro ao gerar número:", error); document.getElementById('numeroProtocolo').value = `0001/${anoAtual}`; }
};
window.enviarRequerimento = async function() {
  let numeroProtocolo = document.getElementById('numeroProtocolo').value;
  if (!numeroProtocolo) { alert("❗Número de protocolo não gerado."); return; }

  const protocolo = {
    numero: numeroProtocolo, matricula: document.getElementById('matricula').value, nome: document.getElementById('nome').value,
    endereco: document.getElementById('endereco').value, municipio: document.getElementById('municipio').value, bairro: document.getElementById('bairro').value,
    cep: document.getElementById('cep').value, telefone: document.getElementById('telefone').value, cpf: document.getElementById('cpf').value,
    rg: document.getElementById('rg').value, dataExpedicao: document.getElementById('dataExpedicao').value, cargo: document.getElementById('cargo').value,
    lotacao: document.getElementById('lotacao').value, unidade: document.getElementById('unidade').value, tipo: document.getElementById('tipo').value,
    requerAo: document.getElementById('requerAo').value, dataSolicitacao: document.getElementById('dataSolicitacao').value, complemento: document.getElementById('complemento').value,
    status: "Enviado", responsavel: window.usuarioLogin,
  };

  try {
      const res = await fetchWithAuth('/protocolos', { method: 'POST', body: JSON.stringify(protocolo) });
      const data = await res.json();
      if (res.ok && data.sucesso) {
          alert('✅ Protocolo enviado e salvo com sucesso!');
          document.querySelector('#form .formulario').reset();
          await gerarNumeroProtocolo();
      } else if (res.status === 400) {
          if (confirm("O número deste protocolo já foi usado. Deseja tentar salvar novamente com um novo número sem perder os dados?")) {
              await gerarNumeroProtocolo();
              protocolo.numero = document.getElementById('numeroProtocolo').value;
              await enviarRequerimento();
          }
      } else {
          alert('❌ Erro ao enviar protocolo: ' + (data.mensagem || 'Erro desconhecido'));
      }
  } catch(err) { alert('❌ Erro na conexão: ' + err.message); }
};

window.listarProtocolos = async function(pagina = 1) {
  const tbody = document.getElementById('tabelaProtocolos');
  tbody.innerHTML = "<tr><td colspan='7'>Carregando...</td></tr>";
  paginaAtualTodos = pagina;
  try {
    const res = await fetchWithAuth('/protocolos');
    const data = await res.json();
    tbody.innerHTML = "";
    const inicio = (pagina - 1) * itensPorPagina;
    const fim = inicio + itensPorPagina;
    const paginaDados = data.protocolos.slice(inicio, fim);
    if (paginaDados.length === 0) tbody.innerHTML = "<tr><td colspan='7'>Nenhum protocolo encontrado.</td></tr>";
    paginaDados.forEach(p => {
      const tr = document.createElement('tr');
      const isAdmin = window.nivelUsuario === 'admin' || window.nivelUsuario === 'padrao';
      const adminButtons = isAdmin ? `<button onclick="abrirModalEditarProtocolo(${p.id})">Editar</button><button onclick="abrirModalAnexos(${p.id})">Anexos</button><button onclick="excluirProtocolo(${p.id})" style="background-color:#c82333;">Excluir</button>` : '';
      tr.innerHTML = `<td class="col-numero">${p.numero}</td><td class="col-matricula">${p.matricula}</td><td class="col-nome">${p.nome}</td><td class="col-tipo">${p.tipo_requerimento}</td><td class="col-status">${p.status}</td><td class="col-responsavel">${p.responsavel}</td><td class="col-acao"><div class="action-buttons"><button onclick="abrirAtualizar(${p.id})">Atualizar</button><button onclick="abrirModalEncaminhar(${p.id})">Encaminhar</button><button onclick="previsualizarPDF(${p.id})">Documento</button>${adminButtons}</div><details id="hist_${p.id}" ontoggle="carregarHistorico(this, ${p.id})"><summary>Histórico</summary></details></td>`;
      tbody.appendChild(tr);
    });
    renderizarPaginacao(data.protocolos.length, pagina, 'paginacaoProtocolos', listarProtocolos);
  } catch (error) { console.error("Erro ao listar protocolos:", error); tbody.innerHTML = "<tr><td colspan='7'>Erro ao carregar protocolos.</td></tr>"; }
};

window.listarMeusProtocolos = async function(pagina = 1) {
    const tbody = document.getElementById('meusProtocolosTabela');
    tbody.innerHTML = "<tr><td colspan='4'>Carregando...</td></tr>";
    paginaAtualMeus = pagina;
    const filtroNumero = document.getElementById('filtroMeusProtocolosNumero').value.trim().toLowerCase();
    const filtroNome = document.getElementById('filtroMeusProtocolosNome').value.trim().toLowerCase();
    try {
        const usuarioLogin = localStorage.getItem('usuarioLogin');
        if (!usuarioLogin) { tbody.innerHTML = "<tr><td colspan='4'>Usuário não identificado.</td></tr>"; return; }
        const res = await fetchWithAuth(`/protocolos/meus/${usuarioLogin}`);
        let data = await res.json();
        tbody.innerHTML = "";
        if (filtroNumero || filtroNome) {
            data.protocolos = data.protocolos.filter(p => {
                const numeroMatch = !filtroNumero || (p.numero || "").toLowerCase().includes(filtroNumero);
                const nomeMatch = !filtroNome || (p.nome || "").toLowerCase().includes(filtroNome);
                return numeroMatch && nomeMatch;
            });
        }
        const inicio = (pagina - 1) * itensPorPagina;
        const fim = inicio + itensPorPagina;
        const paginaDados = data.protocolos.slice(inicio, fim);
        if (paginaDados.length === 0) tbody.innerHTML = "<tr><td colspan='4'>Nenhum protocolo encontrado.</td></tr>";
        paginaDados.forEach(p => {
            const tr = document.createElement('tr');
            const isAdmin = window.nivelUsuario === 'admin' || window.nivelUsuario === 'padrao';
            const adminButtons = isAdmin ? `<button onclick="abrirModalEditarProtocolo(${p.id})">Editar</button><button onclick="abrirModalAnexos(${p.id})">Anexos</button><button onclick="excluirProtocolo(${p.id})" style="background-color:#c82333;">Excluir</button>` : '';
            tr.innerHTML = `<td class="col-numero">${p.numero}</td><td class="col-nome">${p.nome}</td><td class="col-status">${p.status}</td><td class="col-acao"><div class="action-buttons"><button onclick="abrirAtualizar(${p.id})">Atualizar</button><button onclick="abrirModalEncaminhar(${p.id})">Encaminhar</button><button onclick="previsualizarPDF(${p.id})">Documento</button>${adminButtons}</div><details id="hist_${p.id}" ontoggle="carregarHistorico(this, ${p.id})"><summary>Histórico</summary></details></td>`;
            tbody.appendChild(tr);
        });
        renderizarPaginacao(data.protocolos.length, pagina, 'paginacaoMeusProtocolos', listarMeusProtocolos);
    } catch (error) { console.error("Erro ao listar meus protocolos:", error); tbody.innerHTML = "<tr><td colspan='4'>Erro ao carregar protocolos.</td></tr>"; }
};

window.abrirModalAnexos = function(id) {
    alert("Função para abrir anexos do protocolo ID: " + id);
};

window.limparFiltrosMeusProtocolos = function() {
    document.getElementById('filtroMeusProtocolosNumero').value = '';
    document.getElementById('filtroMeusProtocolosNome').value = '';
    listarMeusProtocolos();
};
window.fecharModal = function(modalId) { document.getElementById(modalId).style.display = 'none'; };
window.abrirModalEncaminhar = async function(idProtocolo) {
  try {
    const res = await fetchWithAuth('/usuarios');
    const data = await res.json();
    const select = document.getElementById('selectUsuarioEncaminhar');
    select.innerHTML = '';
    data.usuarios.forEach(usuario => {
      if(usuario.status !== 'ativo') return;
      const option = document.createElement('option');
      option.value = usuario.login;
      option.textContent = `${usuario.nome} (${usuario.tipo})`;
      select.appendChild(option);
    });
    document.getElementById('statusEncaminhamento').value = 'Encaminhado';
    const modal = document.getElementById('modalEncaminhar');
    modal.dataset.protocoloId = idProtocolo;
    modal.style.display = 'flex';
  } catch (error) { alert('Erro ao carregar usuários'); console.error(error); }
};
window.confirmarEncaminhamento = async function() {
  const modal = document.getElementById('modalEncaminhar');
  const idProtocolo = modal.dataset.protocoloId;
  const destino = document.getElementById('selectUsuarioEncaminhar').value;
  const novoStatus = document.getElementById('statusEncaminhamento').value.trim();
  if (!novoStatus) { alert('O campo de status não pode ficar vazio.'); return; }
  try {
    const response = await fetchWithAuth('/protocolos/atualizar', {
      method: 'POST',
      body: JSON.stringify({ protocoloId: idProtocolo, novoStatus: novoStatus, novoResponsavel: destino, observacao: `Encaminhado por ${window.usuarioLogado} para ${destino}`, usuarioLogado: window.usuarioLogado })
    });
    const data = await response.json();
    if (data.sucesso) {
      alert('✅ Protocolo encaminhado com sucesso!');
      fecharModal('modalEncaminhar');
      if (document.getElementById('protocolos').classList.contains('active')) await listarProtocolos();
      if (document.getElementById('meusProtocolos').classList.contains('active')) await listarMeusProtocolos();
      await verificarNotificacoes();
    } else {
      alert('❌ Erro ao encaminhar protocolo: ' + (data.mensagem || ''));
    }
  } catch (err) { console.error(err); alert('❌ Erro ao encaminhar protocolo'); }
};
window.abrirAtualizar = async function(id) {
  const modal = document.getElementById('modalAtualizarStatus');
  document.getElementById('statusSelect').value = 'Em análise';
  document.getElementById('statusCustom').style.display = 'none';
  document.getElementById('statusCustom').value = '';
  document.getElementById('observacaoAtualizacao').value = '';
  modal.dataset.protocoloId = id;
  modal.style.display = 'flex';
};
window.handleStatusChange = function(selectElement) {
  const customInput = document.getElementById('statusCustom');
  customInput.style.display = selectElement.value === 'Outro' ? 'block' : 'none';
};
window.confirmarAtualizacaoStatus = async function() {
  const modal = document.getElementById('modalAtualizarStatus');
  const protocoloId = modal.dataset.protocoloId;
  const statusSelect = document.getElementById('statusSelect');
  let novoStatus = statusSelect.value;
  if (novoStatus === 'Outro') {
    novoStatus = document.getElementById('statusCustom').value.trim();
    if (!novoStatus) { alert('Por favor, digite o status personalizado.'); return; }
  }
  const observacaoInput = document.getElementById('observacaoAtualizacao').value.trim();
  const observacaoFinal = `Status atualizado para "${novoStatus}". ${observacaoInput}`.trim();
  try {
    const response = await fetchWithAuth(`/protocolos/atualizar`, {
      method: 'POST',
      body: JSON.stringify({ protocoloId: protocoloId, novoStatus: novoStatus, novoResponsavel: window.usuarioLogin, observacao: observacaoFinal, usuarioLogado: window.usuarioLogado })
    });
    const data = await response.json();
    if (data.sucesso) {
      alert("✅ Status atualizado!");
      fecharModal('modalAtualizarStatus');
      if (document.getElementById('protocolos').classList.contains('active')) await listarProtocolos();
      if (document.getElementById('meusProtocolos').classList.contains('active')) await listarMeusProtocolos();
    } else {
      alert("Erro ao atualizar.");
    }
  } catch (error) { console.error("Erro na atualização:", error); }
};
window.carregarHistorico = async function(detailsElement, protocoloId) {
    if (!detailsElement.open || detailsElement.dataset.loaded === 'true') return;
    const summary = detailsElement.querySelector('summary');
    detailsElement.innerHTML = '';
    detailsElement.appendChild(summary);
    const loadingDiv = document.createElement('div');
    loadingDiv.textContent = 'Carregando histórico...';
    detailsElement.appendChild(loadingDiv);
    try {
        const res = await fetchWithAuth(`/protocolos/historico/${protocoloId}`);
        const data = await res.json();
        loadingDiv.remove();
        if (data.historico && data.historico.length > 0) {
            data.historico.forEach(h => {
                const div = document.createElement('div');
                div.textContent = `📌 ${h.status} - 👤 ${h.responsavel} - 🕒 ${new Date(h.data_movimentacao).toLocaleString('pt-BR')}${h.observacao ? ` - 📝 ${h.observacao}` : ''}`;
                detailsElement.appendChild(div);
            });
        } else {
            const noHistoryDiv = document.createElement('div');
            noHistoryDiv.textContent = 'Nenhum histórico de movimentação encontrado.';
            detailsElement.appendChild(noHistoryDiv);
        }
        detailsElement.dataset.loaded = 'true';
    } catch (error) {
        loadingDiv.textContent = 'Erro ao carregar histórico.';
        console.error("Erro ao carregar histórico:", error);
    }
};
window.abrirModalEditarProtocolo = async function(protocoloId) {
    try {
        const res = await fetchWithAuth(`/protocolos/${protocoloId}`);
        const data = await res.json();
        if (!data.protocolo) {
            alert(data.mensagem || "Protocolo não encontrado.");
            return;
        }
        const p = data.protocolo;
        popularDropdown('p_edit_lotacao', window.opcoesLotacoes);
        popularDropdown('p_edit_tipo', window.opcoesTipos);
        document.getElementById('p_edit_id').value = p.id;
        document.getElementById('p_edit_numero').value = p.numero || '';
        document.getElementById('p_edit_matricula').value = p.matricula || '';
        document.getElementById('p_edit_nome').value = p.nome || '';
        document.getElementById('p_edit_endereco').value = p.endereco || '';
        document.getElementById('p_edit_municipio').value = p.municipio || '';
        document.getElementById('p_edit_bairro').value = p.bairro || '';
        document.getElementById('p_edit_cep').value = p.cep || '';
        document.getElementById('p_edit_telefone').value = p.telefone || '';
        document.getElementById('p_edit_cpf').value = p.cpf || '';
        document.getElementById('p_edit_rg').value = p.rg || '';
        document.getElementById('p_edit_dataExpedicao').value = p.data_expedicao ? new Date(p.data_expedicao).toISOString().split('T')[0] : '';
        document.getElementById('p_edit_cargo').value = p.cargo || '';
        document.getElementById('p_edit_lotacao').value = p.lotacao || '';
        document.getElementById('p_edit_unidade').value = p.unidade_exercicio || '';
        document.getElementById('p_edit_tipo').value = p.tipo_requerimento || '';
        document.getElementById('p_edit_requerAo').value = p.requer_ao || '';
        document.getElementById('p_edit_dataSolicitacao').value = p.data_solicitacao ? new Date(p.data_solicitacao).toISOString().split('T')[0] : '';
        document.getElementById('p_edit_complemento').value = p.observacoes || '';
        document.getElementById('modalEditarProtocolo').style.display = 'flex';
    } catch (err) {
        alert("Erro ao carregar dados do protocolo para edição.");
        console.error(err);
    }
};
window.confirmarEdicaoProtocolo = async function() {
    const protocoloId = document.getElementById('p_edit_id').value;
    const protocolo = {
        numero: document.getElementById('p_edit_numero').value, matricula: document.getElementById('p_edit_matricula').value,
        nome: document.getElementById('p_edit_nome').value, endereco: document.getElementById('p_edit_endereco').value,
        municipio: document.getElementById('p_edit_municipio').value, bairro: document.getElementById('p_edit_bairro').value,
        cep: document.getElementById('p_edit_cep').value, telefone: document.getElementById('p_edit_telefone').value,
        cpf: document.getElementById('p_edit_cpf').value, rg: document.getElementById('p_edit_rg').value,
        dataExpedicao: document.getElementById('p_edit_dataExpedicao').value, cargo: document.getElementById('p_edit_cargo').value,
        lotacao: document.getElementById('p_edit_lotacao').value, unidade: document.getElementById('p_edit_unidade').value,
        tipo: document.getElementById('p_edit_tipo').value, requerAo: document.getElementById('p_edit_requerAo').value,
        dataSolicitacao: document.getElementById('p_edit_dataSolicitacao').value, complemento: document.getElementById('p_edit_complemento').value,
    };
    try {
        const res = await fetchWithAuth(`/protocolos/${protocoloId}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(protocolo)
        });
        const data = await res.json();
        alert(data.mensagem);
        if (data.sucesso) {
            fecharModal('modalEditarProtocolo');
            if (document.getElementById('protocolos').classList.contains('active')) listarProtocolos();
            if (document.getElementById('meusProtocolos').classList.contains('active')) listarMeusProtocolos();
        }
    } catch(err) { alert('Erro ao salvar as alterações.'); console.error(err); }
};
window.excluirProtocolo = async function(protocoloId) {
    if (confirm("ATENÇÃO!\n\nTem certeza que deseja excluir este protocolo?\nEsta ação é irreversível e removerá também todo o seu histórico.")) {
        try {
            const res = await fetchWithAuth(`/protocolos/${protocoloId}`, { method: 'DELETE' });
            const data = await res.json();
            alert(data.mensagem);
            if (data.sucesso) {
                if (document.getElementById('protocolos').classList.contains('active')) listarProtocolos();
                if (document.getElementById('meusProtocolos').classList.contains('active')) listarMeusProtocolos();
            }
        } catch(err) { alert('Erro ao tentar excluir o protocolo.'); console.error(err); }
    }
};
window.previsualizarPDF = async function(id, isPrint = false) {
  let protocolo;
  if(id === null && isPrint === true) {
      protocolo = {
          numero: document.getElementById('numeroProtocolo').value, data_solicitacao: document.getElementById('dataSolicitacao').value,
          nome: document.getElementById('nome').value, matricula: document.getElementById('matricula').value, cpf: document.getElementById('cpf').value,
          rg: document.getElementById('rg').value, endereco: document.getElementById('endereco').value, bairro: document.getElementById('bairro').value,
          municipio: document.getElementById('municipio').value, cep: document.getElementById('cep').value, telefone: document.getElementById('telefone').value,
          cargo: document.getElementById('cargo').value, lotacao: document.getElementById('lotacao').value, unidade_exercicio: document.getElementById('unidade').value,
          tipo_requerimento: document.getElementById('tipo').value, requer_ao: document.getElementById('requerAo').value, observacoes: document.getElementById('complemento').value,
      };
  } else {
      try {
          const res = await fetchWithAuth(`/protocolos/${id}`);
          const data = await res.json();
          if(!data.protocolo) { alert("Protocolo não encontrado"); return; }
          protocolo = data.protocolo;
      } catch (err) { console.error('Erro ao buscar protocolo:', err); alert('Erro ao buscar dados do protocolo.'); return; }
  }
  protocoloParaGerar = protocolo;
  const modeloOriginal = document.getElementById('modeloProtocolo');
  const pdfContentDiv = document.getElementById('pdfContent');
  pdfContentDiv.innerHTML = modeloOriginal.innerHTML;
  const qrcodeContainer = pdfContentDiv.querySelector('#qrcode-container');
  if(qrcodeContainer && protocolo.numero && protocolo.numero.includes('/')) {
      qrcodeContainer.innerHTML = '';
      const numeroParts = protocolo.numero.split('/');
      if (numeroParts.length === 2) {
          const urlConsulta = `${window.location.origin}/consulta/${numeroParts[1]}/${numeroParts[0]}`;
          new QRCode(qrcodeContainer, { text: urlConsulta, width: 90, height: 90, correctLevel : QRCode.CorrectLevel.H });
      }
  }
  pdfContentDiv.querySelector('#doc_numero').textContent = protocolo.numero ?? 'A ser gerado';
  pdfContentDiv.querySelector('#doc_dataSolicitacao').textContent = protocolo.data_solicitacao ? new Date(protocolo.data_solicitacao).toLocaleDateString('pt-BR', {timeZone: 'UTC'}) : new Date().toLocaleDateString('pt-BR');
  pdfContentDiv.querySelector('#doc_nome').textContent = protocolo.nome ?? '';
  pdfContentDiv.querySelector('#doc_matricula').textContent = protocolo.matricula ?? '';
  pdfContentDiv.querySelector('#doc_cpf').textContent = protocolo.cpf ?? '';
  pdfContentDiv.querySelector('#doc_rg').textContent = protocolo.rg ?? '';
  pdfContentDiv.querySelector('#doc_endereco').textContent = protocolo.endereco ?? '';
  pdfContentDiv.querySelector('#doc_bairro').textContent = protocolo.bairro ?? '';
  pdfContentDiv.querySelector('#doc_municipio').textContent = protocolo.municipio ?? '';
  pdfContentDiv.querySelector('#doc_cep').textContent = protocolo.cep ?? '';
  pdfContentDiv.querySelector('#doc_telefone').textContent = protocolo.telefone ?? '';
  pdfContentDiv.querySelector('#doc_cargo').textContent = protocolo.cargo ?? '';
  pdfContentDiv.querySelector('#doc_lotacao').textContent = protocolo.lotacao ?? '';
  pdfContentDiv.querySelector('#doc_unidade').textContent = protocolo.unidade_exercicio ?? '';
  pdfContentDiv.querySelector('#doc_tipo').textContent = protocolo.tipo_requerimento ?? '';
  pdfContentDiv.querySelector('#doc_requerAo').textContent = protocolo.requer_ao ?? '';
  pdfContentDiv.querySelector('#doc_complemento').innerHTML = protocolo.observacoes ? protocolo.observacoes.replace(/\n/g, '<br>') : 'Nenhuma informação adicional.';
  document.getElementById('pdfModal').style.display = 'block';
};
window.gerarPDF = async function() {
  if (!protocoloParaGerar) { alert("Nenhum protocolo para gerar."); return; }
  const element = document.getElementById('pdfContent');
  const opt = { margin: [0, 0, 0, 0], filename: `Protocolo_${protocoloParaGerar.numero.replace('/', '-')}.pdf`, image: { type: 'jpeg', quality: 0.98 }, html2canvas: { scale: 2, scrollY: 0, useCORS: true }, jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' } };
  try {
    await html2pdf().set(opt).from(element).save();
    fecharModal('pdfModal');
  } catch (error) { console.error("Erro ao gerar PDF:", error); alert("Ocorreu um erro ao gerar o PDF."); }
};
window.popularFiltrosRelatorio = function() {
    popularDropdown('filtroTipo', window.opcoesTipos);
    document.getElementById('filtroTipo').firstChild.textContent = "Todo tipo de Requerimento";
    popularDropdown('filtroLotacao', window.opcoesLotacoes);
    document.getElementById('filtroLotacao').firstChild.textContent = "Todas as Lotações";
};
window.pesquisarProtocolos = async function() {
  const params = new URLSearchParams({ numero: document.getElementById('filtroNumero').value, nome: document.getElementById('filtroNome').value, status: document.getElementById('filtroStatus').value, dataInicio: document.getElementById('filtroDataInicio').value, dataFim: document.getElementById('filtroDataFim').value, tipo: document.getElementById('filtroTipo').value, lotacao: document.getElementById('filtroLotacao').value });
  const tbody = document.getElementById('resultadosPesquisa');
  tbody.innerHTML = '<tr><td colspan="7">Pesquisando...</td></tr>';
  try {
    const res = await fetchWithAuth(`/protocolos/pesquisa?${params.toString()}`);
    const data = await res.json();
    tbody.innerHTML = '';
    if (data.protocolos && data.protocolos.length > 0) {
      data.protocolos.forEach(p => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${p.numero || ''}</td> <td>${p.nome || ''}</td> <td>${p.matricula || ''}</td>
          <td>${p.tipo_requerimento || ''}</td> <td>${p.data_solicitacao ? new Date(p.data_solicitacao).toLocaleDateString('pt-BR', {timeZone: 'UTC'}) : ''}</td>
          <td>${p.status || ''}</td> <td>${p.responsavel || ''}</td>
        `;
        tbody.appendChild(tr);
      });
    } else {
      tbody.innerHTML = '<tr><td colspan="7">Nenhum protocolo encontrado com os filtros informados.</td></tr>';
    }
  } catch (error) { console.error("Erro ao pesquisar protocolos:", error); }
};
window.previsualizarRelatorioPDF = async function() {
    const params = new URLSearchParams({ numero: document.getElementById('filtroNumero').value, nome: document.getElementById('filtroNome').value, status: document.getElementById('filtroStatus').value, dataInicio: document.getElementById('filtroDataInicio').value, dataFim: document.getElementById('filtroDataFim').value, tipo: document.getElementById('filtroTipo').value, lotacao: document.getElementById('filtroLotacao').value });
    try {
        const res = await fetchWithAuth(`/protocolos/pesquisa?${params.toString()}`);
        const data = await res.json();
        if (!data.protocolos || data.protocolos.length === 0) { alert("Nenhum resultado encontrado para gerar o PDF."); return; }
        const templatePDF = document.getElementById('modeloProtocolo');
        let htmlContent = '';
        data.protocolos.forEach(p => {
            const tempNode = templatePDF.cloneNode(true);
            tempNode.style.display = 'block';
            tempNode.querySelector('#doc_numero').textContent = p.numero || '';
            tempNode.querySelector('#doc_dataSolicitacao').textContent = p.data_solicitacao ? new Date(p.data_solicitacao).toLocaleDateString('pt-BR', {timeZone: 'UTC'}) : '';
            tempNode.querySelector('#doc_nome').textContent = p.nome || '';
            tempNode.querySelector('#doc_matricula').textContent = p.matricula || '';
            tempNode.querySelector('#doc_tipo').textContent = p.tipo_requerimento || '';
            htmlContent += `<div style="page-break-after: always;">${tempNode.innerHTML}</div>`;
        });
        document.getElementById('relatorioContent').innerHTML = htmlContent;
        document.getElementById('relatorioModal').style.display = 'block';
    } catch(err) { console.error('Erro ao gerar relatório:', err); alert('Erro ao gerar relatório.'); }
};
window.salvarRelatorioPDF = async function() {
    const element = document.getElementById('relatorioContent');
    const opt = { margin: [0, 0, 0, 0], filename: `Relatorio_Protocolos.pdf`, image: { type: 'jpeg', quality: 0.98 }, html2canvas: { scale: 2 }, jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' } };
    try {
        await html2pdf().set(opt).from(element).save();
        fecharModal('relatorioModal');
    } catch(err) { console.error('Erro ao salvar PDF do relatório:', err); alert('Erro ao salvar PDF do relatório.'); }
};
window.exportarRelatorioExcel = function() {
  const params = new URLSearchParams({ numero: document.getElementById('filtroNumero').value, nome: document.getElementById('filtroNome').value, status: document.getElementById('filtroStatus').value, dataInicio: document.getElementById('filtroDataInicio').value, dataFim: document.getElementById('filtroDataFim').value, tipo: document.getElementById('filtroTipo').value, lotacao: document.getElementById('filtroLotacao').value });
  window.location.href = `/protocolos/backup?${params.toString()}`;
};
window.limparFiltrosRelatorio = function() {
    const form = document.querySelector('#relatorios .filtros');
    if(form) form.reset();
    pesquisarProtocolos();
};
window.verificarNotificacoes = async function() {
  const usuarioLogin = localStorage.getItem('usuarioLogin');
  if (!usuarioLogin) return;
  try {
    const res = await fetchWithAuth(`/protocolos/notificacoes/${usuarioLogin}`);
    const data = await res.json();
    const bell = document.getElementById('notification-bell');
    const countSpan = document.getElementById('notification-count');
    if (data.count > 0) {
      countSpan.textContent = data.count;
      bell.style.display = 'block';
    } else {
      bell.style.display = 'none';
    }
  } catch (err) { console.error('Erro ao verificar notificações:', err); }
};
window.popularFiltrosDashboard = function() {
    const statusOptions = '<option value="">Todos os Status</option><option value="Em análise">Em análise</option><option value="Pendente de documento">Pendente de documento</option><option value="Finalizado">Finalizado</option><option value="Concluído">Concluído</option><option value="Encaminhado">Encaminhado</option>';
    document.getElementById('dashStatus').innerHTML = statusOptions;
    popularDropdown('dashTipo', window.opcoesTipos);
    document.getElementById('dashTipo').firstChild.textContent = "Todo tipo de Requerimento";
    popularDropdown('dashLotacao', window.opcoesLotacoes);
    document.getElementById('dashLotacao').firstChild.textContent = "Todas as Lotações";
};
window.carregarDashboard = async function() {
    const params = new URLSearchParams({
        dataInicio: document.getElementById('dashDataInicio').value, dataFim: document.getElementById('dashDataFim').value,
        status: document.getElementById('dashStatus').value, tipo: document.getElementById('dashTipo').value, lotacao: document.getElementById('dashLotacao').value
    });
    try {
        const res = await fetchWithAuth(`/protocolos/dashboard-stats?${params.toString()}`);
        const stats = await res.json();
        document.getElementById('stat-novos').textContent = stats.novosNoPeriodo;
        document.getElementById('stat-pendentes').textContent = stats.pendentesAntigos;
        document.getElementById('stat-novos-label').textContent = (document.getElementById('dashDataInicio').value || document.getElementById('dashDataFim').value) ? 'Novos no Período' : 'Novos na Semana';
        const labels = stats.topTipos.map(item => item.tipo_requerimento);
        const data = stats.topTipos.map(item => item.total);
        const ctx = document.getElementById('tiposChart').getContext('2d');
        if (tiposChartInstance) { tiposChartInstance.destroy(); }
        tiposChartInstance = new Chart(ctx, {
            type: 'bar', data: { labels: labels, datasets: [{
                    label: 'Total de Protocolos', data: data,
                    backgroundColor: ['rgba(46, 125, 50, 0.7)', 'rgba(76, 175, 80, 0.7)', 'rgba(139, 195, 74, 0.7)', 'rgba(205, 220, 57, 0.7)', 'rgba(255, 235, 59, 0.7)'],
                    borderWidth: 1 }]
            },
            options: { scales: { y: { beginAtZero: true } }, indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
        });
    } catch (err) { console.error("Erro ao carregar dados do dashboard:", err); alert("Não foi possível carregar os dados do dashboard."); }
};
window.salvarEmailSistema = function() {
  localStorage.setItem('emailSistema', document.getElementById('emailSistemaConfig').value);
  alert("Email salvo com sucesso!");
};
window.cadastrarUsuario = async function() {
  const nomeCompleto = document.getElementById('nomeCompleto').value.trim();
  const login = document.getElementById('novoUsuario').value.trim();
  const cpf = document.getElementById('cpfUsuario').value.trim();
  const senha = document.getElementById('novaSenha').value.trim();
  const email = document.getElementById('novoEmail').value.trim();
  const tipo = document.getElementById('nivelUsuario').value;
  if (!nomeCompleto || !login || !cpf || !senha || !email || !tipo) { alert('Por favor, preencha todos os campos.'); return; }
  try {
    const res = await fetchWithAuth('/usuarios', { method: 'POST', body: JSON.stringify({ nome: nomeCompleto, login, cpf, senha, email, tipo }) });
    const data = await res.json();
    alert(data.mensagem || 'Usuário cadastrado!');
    if (data.sucesso) {
        document.getElementById('nomeCompleto').value = ''; document.getElementById('novoUsuario').value = ''; document.getElementById('cpfUsuario').value = ''; document.getElementById('novaSenha').value = ''; document.getElementById('novoEmail').value = '';
        atualizarListaUsuarios();
    }
  } catch (error) { console.error('Erro ao cadastrar usuário:', error); alert('Erro ao cadastrar usuário.'); }
};
window.atualizarListaUsuarios = async function() {
  try {
    const response = await fetchWithAuth('/usuarios');
    const data = await response.json();
    const tbody = document.getElementById('tabelaUsuarios');
    tbody.innerHTML = "";
    data.usuarios.forEach(u => {
      const tr = document.createElement('tr');
      const statusClasse = u.status === 'ativo' ? 'color:green;' : 'color:red;';
      tr.innerHTML = `
        <td>${u.nome}</td> <td>${u.login}</td> <td>${u.email}</td> <td>${u.tipo}</td> <td style="font-weight:bold; ${statusClasse}">${u.status}</td>
        <td>
          <button onclick='abrirModalEditar(${JSON.stringify(u)})'>Editar</button>
          <button onclick='abrirModalResetarSenha(${u.id})'>Resetar Senha</button>
          ${u.status === 'ativo' ? `<button onclick="alterarStatusUsuario(${u.id}, 'inativo')" style="background-color:#c82333;">Desativar</button>` : `<button onclick="alterarStatusUsuario(${u.id}, 'ativo')" style="background-color:#218838;">Reativar</button>`}
        </td>`;
      tbody.appendChild(tr);
    });
  } catch (error) { alert('Erro ao carregar usuários: ' + error.message); }
};
window.abrirModalEditar = function(usuario) {
  document.getElementById('editUserId').value = usuario.id;
  document.getElementById('editNomeCompleto').value = usuario.nome;
  document.getElementById('editLogin').value = usuario.login;
  document.getElementById('editEmail').value = usuario.email;
  document.getElementById('editCpf').value = usuario.cpf;
  document.getElementById('editTipo').value = usuario.tipo;
  document.getElementById('modalEditarUsuario').style.display = 'flex';
};
window.confirmarEdicaoUsuario = async function() {
  const id = document.getElementById('editUserId').value;
  const usuario = { nome: document.getElementById('editNomeCompleto').value, login: document.getElementById('editLogin').value, email: document.getElementById('editEmail').value, cpf: document.getElementById('editCpf').value, tipo: document.getElementById('editTipo').value };
  try {
    const res = await fetchWithAuth(`/usuarios/${id}`, { method: 'PUT', body: JSON.stringify(usuario) });
    const data = await res.json();
    alert(data.mensagem);
    if (data.sucesso) { fecharModal('modalEditarUsuario'); atualizarListaUsuarios(); }
  } catch(err) { alert('Erro ao salvar alterações.'); }
};
window.abrirModalResetarSenha = function(id) {
  document.getElementById('resetUserId').value = id;
  document.getElementById('resetNovaSenha').value = '';
  document.getElementById('modalResetarSenha').style.display = 'flex';
};
window.confirmarResetSenha = async function() {
  const id = document.getElementById('resetUserId').value;
  const novaSenha = document.getElementById('resetNovaSenha').value;
  if (novaSenha.length < 4) { alert('A nova senha deve ter pelo menos 4 caracteres.'); return; }
  try {
    const res = await fetchWithAuth(`/usuarios/${id}/senha`, { method: 'PUT', body: JSON.stringify({ novaSenha }) });
    const data = await res.json();
    alert(data.mensagem);
    if (data.sucesso) { fecharModal('modalResetarSenha'); }
  } catch(err) { alert('Erro ao resetar senha.'); }
};
window.alterarStatusUsuario = async function(id, novoStatus) {
  const acao = novoStatus === 'inativo' ? 'desativar' : 'reativar';
  if (confirm(`Tem certeza que deseja ${acao} este usuário?`)) {
    try {
      const res = await fetchWithAuth(`/usuarios/${id}/status`, { method: 'PUT', body: JSON.stringify({ status: novoStatus }) });
      const data = await res.json();
      alert(data.mensagem);
      if (data.sucesso) { atualizarListaUsuarios(); }
    } catch(err) { alert(`Erro ao ${acao} usuário.`); }
  }
};
window.carregarOpcoesDropdowns = async function() {
    try {
        const [tiposRes, lotacoesRes] = await Promise.all([ fetchWithAuth('/admin/tipos'), fetchWithAuth('/admin/lotacoes') ]);
        window.opcoesTipos = await tiposRes.json();
        window.opcoesLotacoes = await lotacoesRes.json();
    } catch (err) { console.error("Erro ao carregar opções de dropdowns:", err); }
};
window.popularDropdown = function(selectId, opcoes) {
    const select = document.getElementById(selectId);
    const primeiraOpcao = select.options[0];
    select.innerHTML = '';
    if(primeiraOpcao) select.appendChild(primeiraOpcao);
    opcoes.forEach(opcao => {
        const opt = document.createElement('option');
        opt.value = opcao;
        opt.textContent = opcao;
        select.appendChild(opt);
    });
};
window.popularDropdownsFormulario = function() { popularDropdown('tipo', window.opcoesTipos); popularDropdown('lotacao', window.opcoesLotacoes); };
window.carregarTabelaGestao = async function(tipo) {
    const tbody = document.getElementById(tipo === 'tipos' ? 'tabelaTipos' : 'tabelaLotacoes');
    tbody.innerHTML = '';
    try {
        const res = await fetchWithAuth(`/admin/${tipo}/all`);
        const data = await res.json();
        data.forEach(item => {
            const tr = document.createElement('tr');
            const statusStyle = item.ativo ? 'color:green;' : 'color:red;';
            tr.innerHTML = `<td>${item.nome}</td><td style="${statusStyle}">${item.ativo ? 'Ativo' : 'Inativo'}</td><td><button onclick="alterarStatusItem('${tipo}', ${item.id}, ${!item.ativo})">${item.ativo ? 'Desativar' : 'Reativar'}</button></td>`;
            tbody.appendChild(tr);
        });
    } catch (err) { console.error(`Erro ao carregar ${tipo}:`, err); }
};
window.adicionarItem = async function(tipo) {
    const nomeInput = document.getElementById(tipo === 'tipos' ? 'novoTipoNome' : 'novaLotacaoNome');
    const nome = nomeInput.value.trim();
    if (!nome) { alert('O nome não pode ser vazio.'); return; }
    try {
        await fetchWithAuth(`/admin/${tipo}`, { method: 'POST', body: JSON.stringify({ nome }) });
        nomeInput.value = '';
        carregarTabelaGestao(tipo);
        await carregarOpcoesDropdowns();
    } catch (err) { alert(`Erro ao adicionar item.`); }
};
window.alterarStatusItem = async function(tipo, id, novoStatus) {
    const acao = novoStatus ? 'reativar' : 'desativar';
    if (confirm(`Tem certeza que deseja ${acao} este item?`)) {
        try {
            await fetchWithAuth(`/admin/${tipo}/${id}/status`, { method: 'PUT', body: JSON.stringify({ ativo: novoStatus }) });
            carregarTabelaGestao(tipo);
            await carregarOpcoesDropdowns();
        } catch (err) { alert(`Erro ao ${acao} o item.`); }
    }
};
window.gerarBackup = async function() {
  const dataInicio = document.getElementById('backupDataInicio').value;
  const dataFim = document.getElementById('backupDataFim').value;
  if (!dataInicio || !dataFim) { alert("Por favor, selecione o período completo."); return; }
  try {
    const params = new URLSearchParams({dataInicio, dataFim});
    const url = `/protocolos/backup?${params.toString()}`;
    const response = await fetchWithAuth(url);
    if (!response.ok) { const textoErro = await response.text(); alert(`Erro ao gerar backup: ${textoErro || response.statusText}`); return; }
    const blob = await response.blob();
    const urlBlob = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = urlBlob;
    a.download = `backup_protocolos_${dataInicio}_a_${dataFim}.xlsx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(urlBlob);
  } catch (error) { console.error("Erro ao gerar backup:", error); }
};
window.renderizarPaginacao = function(totalItens, paginaAtual, idContainer, callback) {
    const container = document.getElementById(idContainer);
    container.innerHTML = '';
    const totalPaginas = Math.ceil(totalItens / itensPorPagina);
    if (totalPaginas <= 1) return;
    let maxPagesToShow = 5;
    let startPage, endPage;
    if (totalPaginas <= maxPagesToShow) { startPage = 1; endPage = totalPaginas; }
    else {
        const maxPagesBeforeCurrent = Math.floor(maxPagesToShow / 2);
        const maxPagesAfterCurrent = Math.ceil(maxPagesToShow / 2) - 1;
        if (paginaAtual <= maxPagesBeforeCurrent) { startPage = 1; endPage = maxPagesToShow; }
        else if (paginaAtual + maxPagesAfterCurrent >= totalPaginas) { startPage = totalPaginas - maxPagesToShow + 1; endPage = totalPaginas; }
        else { startPage = paginaAtual - maxPagesBeforeCurrent; endPage = paginaAtual + maxPagesAfterCurrent; }
    }
    if (paginaAtual > 1) { const prevBtn = document.createElement('button'); prevBtn.textContent = '«'; prevBtn.onclick = () => callback(paginaAtual - 1); container.appendChild(prevBtn); }
    if (startPage > 1) { const firstBtn = document.createElement('button'); firstBtn.textContent = '1'; firstBtn.onclick = () => callback(1); container.appendChild(firstBtn); if (startPage > 2) { const ellipsis = document.createElement('span'); ellipsis.textContent = '...'; container.appendChild(ellipsis); } }
    for (let i = startPage; i <= endPage; i++) { const btn = document.createElement('button'); btn.textContent = i; if (i === paginaAtual) { btn.disabled = true; btn.style.fontWeight = 'bold'; btn.style.backgroundColor = '#ccc'; } btn.onclick = () => callback(i); container.appendChild(btn); }
    if (endPage < totalPaginas) { if (endPage < totalPaginas - 1) { const ellipsis = document.createElement('span'); ellipsis.textContent = '...'; container.appendChild(ellipsis); } const lastBtn = document.createElement('button'); lastBtn.textContent = totalPaginas; lastBtn.onclick = () => callback(totalPaginas); container.appendChild(lastBtn); }
    if (paginaAtual < totalPaginas) { const nextBtn = document.createElement('button'); nextBtn.textContent = '»'; nextBtn.onclick = () => callback(paginaAtual + 1); container.appendChild(nextBtn); }
};
window.voltarDeMeusProtocolos = function() { mostrarTela('menu'); };
window.preencherCamposServidor = function(servidor) {
    if (!servidor) { document.getElementById('nome').value = ''; document.getElementById('lotacao').value = ''; document.getElementById('cargo').value = ''; document.getElementById('unidade').value = ''; }
    else { document.getElementById('nome').value = servidor.nome || ''; document.getElementById('lotacao').value = servidor.lotacao || ''; document.getElementById('cargo').value = servidor.cargo || ''; document.getElementById('unidade').value = servidor.unidade_de_exercicio || ''; }
};
window.abrirModalAlterarSenha = function() {
    document.getElementById('senhaAtual').value = '';
    document.getElementById('alterarNovaSenha').value = '';
    document.getElementById('confirmarNovaSenha').value = '';
    document.getElementById('modalAlterarSenha').style.display = 'flex';
};
window.confirmarAlteracaoSenha = async function() {
    const senhaAtual = document.getElementById('senhaAtual').value;
    const novaSenha = document.getElementById('alterarNovaSenha').value;
    const confirmarSenha = document.getElementById('confirmarNovaSenha').value;
    if (!senhaAtual || !novaSenha || !confirmarSenha) { alert('Por favor, preencha todos os campos.'); return; }
    if (novaSenha !== confirmarSenha) { alert('A nova senha e a confirmação não são iguais.'); return; }
    if (novaSenha.length < 4) { alert('A nova senha deve ter pelo menos 4 caracteres.'); return; }
    try {
        const res = await fetchWithAuth('/usuarios/minha-senha', {
            method: 'PUT',
            body: JSON.stringify({ senhaAtual: senhaAtual, novaSenha: novaSenha })
        });
        const data = await res.json();
        alert(data.mensagem);
        if (data.sucesso) { fecharModal('modalAlterarSenha'); }
    } catch(err) { alert('Erro ao conectar com o servidor para alterar a senha.'); }
};
