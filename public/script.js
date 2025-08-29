// ================================================================= //
// ============  NOVA FUNÇÃO PARA AUTENTICAÇÃO ===================== //
// ================================================================= //
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('protocolo-token');

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const finalOptions = {
        ...options,
        headers,
    };

    const response = await fetch(url, finalOptions);

    // Se o token for inválido ou expirado, o servidor retornará 401 ou 403.
    // Nesse caso, o usuário é deslogado para evitar erros.
    if (response.status === 401 || response.status === 403) {
        console.error("Token inválido ou expirado. Fazendo logout.");
        // Não mostrar um alert aqui para não ser intrusivo. Apenas desloga.
        sair();
        // Lança um erro para interromper a execução da função que chamou e evitar mais erros.
        throw new Error("Token inválido ou expirado.");
    }

    return response;
}


// Variáveis Globais
const itensPorPagina = 10;
let paginaAtualTodos = 1;
let paginaAtualMeus = 1;
let tiposChartInstance = null;
let protocoloParaGerar = null;
window.opcoesTipos = [];
window.opcoesLotacoes = [];

// Funções de Inicialização
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
            mostrarTela('menu');
            verificarNotificacoes();
        });

    } else {
        mostrarTela('login');
    }

    document.getElementById('matricula').addEventListener('blur', async function() {
        const matricula = this.value.trim();
        if (!matricula) { preencherCamposServidor(null); return; }
        try {
            // fetchWithAuth usado aqui
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
            // fetch para API externa (ViaCEP) não usa fetchWithAuth
            const response = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
            const data = await response.json();
            if (data.erro) { alert('CEP não encontrado!'); return; }
            document.getElementById('endereco').value = data.logradouro || '';
            document.getElementById('bairro').value = data.bairro || '';
            document.getElementById('municipio').value = data.localidade || '';
        } catch (error) { console.error('Erro ao buscar CEP:', error); alert('Erro ao buscar o CEP.'); }
    });
});

// Funções Globais
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
            // Armazena o token no localStorage
            localStorage.setItem('protocolo-token', data.token);
            localStorage.setItem('usuarioLogado', data.usuario.nome);
            localStorage.setItem('usuarioLogin', data.usuario.login);
            localStorage.setItem('nivelUsuario', data.usuario.tipo);
            window.location.reload();
        } else {
            msg.textContent = data.mensagem || "Usuário ou senha incorretos.";
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
  
  const protocolo = { /* ... (mesmo objeto de protocolo) ... */ };

  try {
      const res = await fetchWithAuth('/protocolos', { method: 'POST', body: JSON.stringify(protocolo) });
      const data = await res.json();
      // ... (mesma lógica de tratamento de resposta) ...
  } catch(err) { alert('❌ Erro na conexão: ' + err.message); }
};

window.listarProtocolos = async function(pagina = 1) {
  const tbody = document.getElementById('tabelaProtocolos');
  tbody.innerHTML = "<tr><td colspan='7'>Carregando...</td></tr>";
  paginaAtualTodos = pagina;
  try {
    const res = await fetchWithAuth('/protocolos');
    const data = await res.json();
    // ... (mesma lógica de renderização da tabela) ...
  } catch (error) { console.error("Erro ao listar protocolos:", error); tbody.innerHTML = "<tr><td colspan='7'>Erro ao carregar protocolos.</td></tr>"; }
};

window.listarMeusProtocolos = async function(pagina = 1) {
    const tbody = document.getElementById('meusProtocolosTabela');
    tbody.innerHTML = "<tr><td colspan='4'>Carregando...</td></tr>";
    paginaAtualMeus = pagina;
    try {
        const usuarioLogin = localStorage.getItem('usuarioLogin');
        if (!usuarioLogin) { /* ... */ return; }
        const res = await fetchWithAuth(`/protocolos/meus/${usuarioLogin}`);
        let data = await res.json();
        // ... (mesma lógica de renderização e filtro) ...
    } catch (error) { console.error("Erro ao listar meus protocolos:", error); tbody.innerHTML = "<tr><td colspan='4'>Erro ao carregar protocolos.</td></tr>"; }
};

window.abrirModalEncaminhar = async function(idProtocolo) {
  try {
    const res = await fetchWithAuth('/usuarios');
    const data = await res.json();
    // ... (mesma lógica do modal) ...
  } catch (error) { alert('Erro ao carregar usuários'); console.error(error); }
};

window.confirmarEncaminhamento = async function() {
  // ...
  try {
    const response = await fetchWithAuth('/protocolos/atualizar', {
      method: 'POST', body: JSON.stringify({ /* ... */ })
    });
    // ... (mesma lógica) ...
  } catch (err) { console.error(err); alert('❌ Erro ao encaminhar protocolo'); }
};

window.confirmarAtualizacaoStatus = async function() {
  // ...
  try {
    const response = await fetchWithAuth(`/protocolos/atualizar`, {
      method: 'POST', body: JSON.stringify({ /* ... */ })
    });
    // ... (mesma lógica) ...
  } catch (error) { console.error("Erro na atualização:", error); }
};

window.carregarHistorico = async function(detailsElement, protocoloId) {
    // ...
    try {
        const res = await fetchWithAuth(`/protocolos/historico/${protocoloId}`);
        // ... (mesma lógica) ...
    } catch (error) { /* ... */ }
};

window.abrirModalEditarProtocolo = async function(protocoloId) {
    try {
        const res = await fetchWithAuth(`/protocolos/${protocoloId}`);
        // ... (mesma lógica) ...
    } catch (err) { /* ... */ }
};

window.confirmarEdicaoProtocolo = async function() {
    // ...
    try {
        const res = await fetchWithAuth(`/protocolos/${protocoloId}`, {
            method: 'PUT', body: JSON.stringify(protocolo)
        });
        // ... (mesma lógica) ...
    } catch(err) { /* ... */ }
};

window.excluirProtocolo = async function(protocoloId) {
    if (confirm(/* ... */)) {
        try {
            const res = await fetchWithAuth(`/protocolos/${protocoloId}`, { method: 'DELETE' });
            // ... (mesma lógica) ...
        } catch(err) { /* ... */ }
    }
};

window.previsualizarPDF = async function(id, isPrint = false) {
  // ...
  if (id !== null) {
      try {
          const res = await fetchWithAuth(`/protocolos/${id}`);
          // ... (mesma lógica) ...
      } catch (err) { /* ... */ }
  }
  // ...
};

window.pesquisarProtocolos = async function() {
  // ...
  try {
    const res = await fetchWithAuth(`/protocolos/pesquisa?${params.toString()}`);
    // ... (mesma lógica) ...
  } catch (error) { console.error("Erro ao pesquisar protocolos:", error); }
};

window.verificarNotificacoes = async function() {
  const usuarioLogin = localStorage.getItem('usuarioLogin');
  if (!usuarioLogin) return;
  try {
    const res = await fetchWithAuth(`/protocolos/notificacoes/${usuarioLogin}`);
    // ... (mesma lógica) ...
  } catch (err) { console.error('Erro ao verificar notificações:', err); }
};

window.carregarDashboard = async function() {
    // ...
    try {
        const res = await fetchWithAuth(`/protocolos/dashboard-stats?${params.toString()}`);
        // ... (mesma lógica) ...
    } catch (err) { console.error("Erro ao carregar dados do dashboard:", err); }
};

window.cadastrarUsuario = async function() {
  // ...
  try {
    const res = await fetchWithAuth('/usuarios', { method: 'POST', body: JSON.stringify({ /* ... */ }) });
    // ... (mesma lógica) ...
  } catch (error) { console.error('Erro ao cadastrar usuário:', error); }
};

window.atualizarListaUsuarios = async function() {
  try {
    const response = await fetchWithAuth('/usuarios');
    // ... (mesma lógica) ...
  } catch (error) { alert('Erro ao carregar usuários: ' + error.message); }
};

window.confirmarEdicaoUsuario = async function() {
  // ...
  try {
    const res = await fetchWithAuth(`/usuarios/${id}`, { method: 'PUT', body: JSON.stringify(usuario) });
    // ... (mesma lógica) ...
  } catch(err) { alert('Erro ao salvar alterações.'); }
};

window.confirmarResetSenha = async function() {
  // ...
  try {
    const res = await fetchWithAuth(`/usuarios/${id}/senha`, { method: 'PUT', body: JSON.stringify({ novaSenha }) });
    // ... (mesma lógica) ...
  } catch(err) { alert('Erro ao resetar senha.'); }
};

window.alterarStatusUsuario = async function(id, novoStatus) {
  // ...
    try {
      const res = await fetchWithAuth(`/usuarios/${id}/status`, { method: 'PUT', body: JSON.stringify({ status: novoStatus }) });
      // ... (mesma lógica) ...
    } catch(err) { alert(`Erro ao ${acao} usuário.`); }
};

window.carregarOpcoesDropdowns = async function() {
    try {
        const [tiposRes, lotacoesRes] = await Promise.all([
            fetchWithAuth('/admin/tipos'),
            fetchWithAuth('/admin/lotacoes')
        ]);
        window.opcoesTipos = await tiposRes.json();
        window.opcoesLotacoes = await lotacoesRes.json();
    } catch (err) { console.error("Erro ao carregar opções de dropdowns:", err); }
};

window.adicionarItem = async function(tipo) {
    // ...
    try {
        await fetchWithAuth(`/admin/${tipo}`, { method: 'POST', body: JSON.stringify({ nome }) });
        // ... (mesma lógica) ...
    } catch (err) { alert(`Erro ao adicionar item.`); }
};

window.alterarStatusItem = async function(tipo, id, novoStatus) {
    // ...
        try {
            await fetchWithAuth(`/admin/${tipo}/${id}/status`, { method: 'PUT', body: JSON.stringify({ ativo: novoStatus }) });
            // ... (mesma lógica) ...
        } catch (err) { alert(`Erro ao ${acao} o item.`); }
};

window.gerarBackup = async function() {
  // ...
  try {
    const url = `/protocolos/backup?${params.toString()}`;
    const response = await fetchWithAuth(url);
    // ... (mesma lógica) ...
  } catch (error) { console.error("Erro ao gerar backup:", error); }
};

window.confirmarAlteracaoSenha = async function() {
    // ...
    try {
        const res = await fetchWithAuth('/usuarios/minha-senha', {
            method: 'PUT', body: JSON.stringify({ /* ... */ })
        });
        // ... (mesma lógica) ...
    } catch(err) { alert('Erro ao conectar com o servidor para alterar a senha.'); }
};
// Funções omitidas para brevidade, mas todas as chamadas `fetch` internas foram substituídas por `fetchWithAuth`
// ... (resto do arquivo inalterado)
