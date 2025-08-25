// Variáveis Globais

const itensPorPagina = 10;

let paginaAtualTodos = 1;

let paginaAtualMeus = 1;

let tiposChartInstance = null;

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

const response = await fetch(`/protocolos/servidor/${encodeURIComponent(matricula)}`);

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

if (data.sucesso && data.usuario) {

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

await fetch('/protocolos/notificacoes/ler', {

method: 'POST', headers: { 'Content-Type': 'application/json' },

body: JSON.stringify({ usuarioLogin })

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

const res = await fetch(`/protocolos/ultimoNumero/${anoAtual}`);

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

const res = await fetch('/protocolos', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(protocolo) });

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

const res = await fetch('/protocolos');

const data = await res.json();

tbody.innerHTML = "";

const inicio = (pagina - 1) * itensPorPagina;

const fim = inicio + itensPorPagina;

const paginaDados = data.protocolos.slice(inicio, fim);

if (paginaDados.length === 0) tbody.innerHTML = "<tr><td colspan='7'>Nenhum protocolo encontrado.</td></tr>";

paginaDados.forEach(p => {

const tr = document.createElement('tr');

const isAdmin = window.nivelUsuario === 'admin' || window.nivelUsuario === 'padrao';

const adminButtons = isAdmin ? `

<button onclick="abrirModalEditarProtocolo(${p.id})">Editar</button>

<button onclick="excluirProtocolo(${p.id})" style="background-color:#c82333;">Excluir</button>

` : '';

tr.innerHTML = `

<td class="col-numero">${p.numero}</td>

<td class="col-matricula">${p.matricula}</td>

<td class="col-nome">${p.nome}</td>

<td class="col-tipo">${p.tipo_requerimento}</td>

<td class="col-status">${p.status}</td>

<td class="col-responsavel">${p.responsavel}</td>

<td class="col-acao">

<div class="action-buttons">

<button onclick="abrirAtualizar(${p.id})">Atualizar</button>

<button onclick="abrirModalEncaminhar(${p.id})">Encaminhar</button>

<button onclick="previsualizarPDF(${p.id})">Documento</button>

${adminButtons}

</div>

<details id="hist_${p.id}" ontoggle="carregarHistorico(this, ${p.id})">

<summary>Histórico</summary>

</details>

</td>`;

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

const res = await fetch(`/protocolos/meus/${usuarioLogin}`);

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

const adminButtons = isAdmin ? `

<button onclick="abrirModalEditarProtocolo(${p.id})">Editar</button>

<button onclick="excluirProtocolo(${p.id})" style="background-color:#c82333;">Excluir</button>

` : '';

tr.innerHTML = `

<td class="col-numero">${p.numero}</td>

<td class="col-nome">${p.nome}</td>

<td class="col-status">${p.status}</td>

<td class="col-acao">

<div class="action-buttons">

<button onclick="abrirAtualizar(${p.id})">Atualizar</button>

<button onclick="abrirModalEncaminhar(${p.id})">Encaminhar</button>

<button onclick="previsualizarPDF(${p.id})">Documento</button>

${adminButtons}

</div>

<details id="hist_${p.id}" ontoggle="carregarHistorico(this, ${p.id})">

<summary>Histórico</summary>

</details>

</td>`;

tbody.appendChild(tr);

});

renderizarPaginacao(data.protocolos.length, pagina, 'paginacaoMeusProtocolos', listarMeusProtocolos);

} catch (error) { console.error("Erro ao listar meus protocolos:", error); tbody.innerHTML = "<tr><td colspan='4'>Erro ao carregar protocolos.</td></tr>"; }

};

window.limparFiltrosMeusProtocolos = function() {

document.getElementById('filtroMeusProtocolosNumero').value = '';

document.getElementById('filtroMeusProtocolosNome').value = '';

listarMeusProtocolos();

};

window.fecharModal = function(modalId) { document.getElementById(modalId).style.display = 'none'; };

window.abrirModalEncaminhar = async function(idProtocolo) {

try {

const res = await fetch('/usuarios');

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

const response = await fetch('/protocolos/atualizar', {

method: 'POST',

headers: { 'Content-Type': 'application/json' },

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

const response = await fetch(`/protocolos/atualizar`, {

method: 'POST',

headers: { 'Content-Type': 'application/json' },

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

const res = await fetch(`/protocolos/historico/${protocoloId}`);

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

// FIM DA PARTE 1 de 2
// PARTE 2 de 2



// Funções de CRUD e Modais para Protocolos

window.abrirModalEditarProtocolo = async function(id) {

try {

const response = await fetch(`/protocolos/${id}`);

if (!response.ok) throw new Error('Protocolo não encontrado.');


const protocolo = await response.json();

const modal = document.getElementById('modalEditarProtocolo');


// Popula os campos do modal com os dados do protocolo

modal.querySelector('#editProtocoloId').value = protocolo.id;

modal.querySelector('#editNumeroProtocolo').value = protocolo.numero;

modal.querySelector('#editMatricula').value = protocolo.matricula;

modal.querySelector('#editNome').value = protocolo.nome;

modal.querySelector('#editCpf').value = protocolo.cpf;

modal.querySelector('#editRg').value = protocolo.rg;

modal.querySelector('#editDataExpedicao').value = protocolo.data_expedicao ? new Date(protocolo.data_expedicao).toISOString().split('T')[0] : '';

modal.querySelector('#editTelefone').value = protocolo.telefone;

modal.querySelector('#editCep').value = protocolo.cep;

modal.querySelector('#editEndereco').value = protocolo.endereco;

modal.querySelector('#editBairro').value = protocolo.bairro;

modal.querySelector('#editMunicipio').value = protocolo.municipio;

modal.querySelector('#editCargo').value = protocolo.cargo;

modal.querySelector('#editUnidade').value = protocolo.unidade;

modal.querySelector('#editRequerAo').value = protocolo.requer_ao;

modal.querySelector('#editDataSolicitacao').value = protocolo.data_solicitacao ? new Date(protocolo.data_solicitacao).toISOString().split('T')[0] : '';

modal.querySelector('#editComplemento').value = protocolo.complemento;



// Popula e seleciona os dropdowns

const tipoSelect = modal.querySelector('#editTipo');

tipoSelect.innerHTML = '<option value="">Selecione...</option>';

window.opcoesTipos.forEach(opt => tipoSelect.innerHTML += `<option value="${opt.nome}" ${protocolo.tipo_requerimento === opt.nome ? 'selected' : ''}>${opt.nome}</option>`);



const lotacaoSelect = modal.querySelector('#editLotacao');

lotacaoSelect.innerHTML = '<option value="">Selecione...</option>';

window.opcoesLotacoes.forEach(opt => lotacaoSelect.innerHTML += `<option value="${opt.nome}" ${protocolo.lotacao === opt.nome ? 'selected' : ''}>${opt.nome}</option>`);



modal.style.display = 'flex';

} catch (error) {

console.error('Erro ao abrir modal de edição:', error);

alert('❌ Erro ao carregar dados do protocolo.');

}

};

window.salvarEdicaoProtocolo = async function() {

const modal = document.getElementById('modalEditarProtocolo');

const protocoloId = modal.querySelector('#editProtocoloId').value;



const dadosAtualizados = {

numero: modal.querySelector('#editNumeroProtocolo').value,

matricula: modal.querySelector('#editMatricula').value,

nome: modal.querySelector('#editNome').value,

cpf: modal.querySelector('#editCpf').value,

rg: modal.querySelector('#editRg').value,

data_expedicao: modal.querySelector('#editDataExpedicao').value,

telefone: modal.querySelector('#editTelefone').value,

cep: modal.querySelector('#editCep').value,

endereco: modal.querySelector('#editEndereco').value,

bairro: modal.querySelector('#editBairro').value,

municipio: modal.querySelector('#editMunicipio').value,

cargo: modal.querySelector('#editCargo').value,

unidade: modal.querySelector('#editUnidade').value,

requer_ao: modal.querySelector('#editRequerAo').value,

data_solicitacao: modal.querySelector('#editDataSolicitacao').value,

tipo_requerimento: modal.querySelector('#editTipo').value,

lotacao: modal.querySelector('#editLotacao').value,

complemento: modal.querySelector('#editComplemento').value,

};



try {

const response = await fetch(`/protocolos/${protocoloId}`, {

method: 'PUT',

headers: { 'Content-Type': 'application/json' },

body: JSON.stringify(dadosAtualizados)

});

const data = await response.json();

if (data.sucesso) {

alert('✅ Protocolo atualizado com sucesso!');

fecharModal('modalEditarProtocolo');

if (document.getElementById('protocolos').classList.contains('active')) listarProtocolos();

if (document.getElementById('meusProtocolos').classList.contains('active')) listarMeusProtocolos();

} else {

alert('❌ Erro ao atualizar o protocolo: ' + (data.mensagem || 'Erro desconhecido.'));

}

} catch (error) {

console.error('Erro ao salvar edição:', error);

alert('❌ Erro de conexão ao salvar as alterações.');

}

};

window.excluirProtocolo = async function(id) {

if (confirm("Tem certeza que deseja excluir este protocolo? Esta ação não pode ser desfeita.")) {

try {

const res = await fetch(`/protocolos/${id}`, { method: 'DELETE' });

const data = await res.json();

if (data.sucesso) {

alert("✅ Protocolo excluído.");

if (document.getElementById('protocolos').classList.contains('active')) listarProtocolos();

if (document.getElementById('meusProtocolos').classList.contains('active')) listarMeusProtocolos();

} else {

alert("❌ Erro ao excluir.");

}

} catch (error) { console.error("Erro ao excluir:", error); }

}

};

window.previsualizarPDF = function(idProtocolo) {

window.open(`/protocolos/pdf/${idProtocolo}`, '_blank');

};



// Funções da Tela de Configuração

window.atualizarListaUsuarios = async function() {

const tbody = document.getElementById('tabelaUsuarios');

tbody.innerHTML = "<tr><td colspan='5'>Carregando...</td></tr>";

try {

const res = await fetch('/usuarios');

const data = await res.json();

tbody.innerHTML = '';

data.usuarios.forEach(u => {

const tr = document.createElement('tr');

tr.innerHTML = `

<td>${u.nome}</td><td>${u.login}</td><td>${u.tipo}</td><td>${u.status}</td>

<td>

<button onclick='abrirModalUsuario(${JSON.stringify(u)})'>Editar</button>

<button onclick='excluirUsuario(${u.id})' style="background-color:#c82333;">Excluir</button>

</td>

`;

tbody.appendChild(tr);

});

} catch (error) { console.error("Erro ao listar usuários:", error); }

};

window.abrirModalUsuario = function(usuario = null) {

const modal = document.getElementById('modalUsuario');

const form = document.getElementById('formUsuario');

form.reset();

document.getElementById('usuarioId').value = '';

document.getElementById('senhaUsuario').required = true;


if (usuario) {

document.getElementById('usuarioId').value = usuario.id;

document.getElementById('nomeUsuario').value = usuario.nome;

document.getElementById('loginUsuario').value = usuario.login;

document.getElementById('tipoUsuario').value = usuario.tipo;

document.getElementById('statusUsuario').value = usuario.status;

document.getElementById('senhaUsuario').required = false; // Senha não é obrigatória na edição

}

modal.style.display = 'flex';

};

window.salvarUsuario = async function() {

const id = document.getElementById('usuarioId').value;

const senha = document.getElementById('senhaUsuario').value;

const confirmSenha = document.getElementById('confirmSenhaUsuario').value;



if (senha !== confirmSenha) {

alert("As senhas não coincidem!");

return;

}


const usuario = {

nome: document.getElementById('nomeUsuario').value,

login: document.getElementById('loginUsuario').value,

tipo: document.getElementById('tipoUsuario').value,

status: document.getElementById('statusUsuario').value,

};

if (senha) usuario.senha = senha;



const url = id ? `/usuarios/${id}` : '/usuarios';

const method = id ? 'PUT' : 'POST';


try {

const res = await fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(usuario) });

const data = await res.json();

if (data.sucesso) {

alert('✅ Usuário salvo com sucesso!');

fecharModal('modalUsuario');

atualizarListaUsuarios();

} else {

alert('❌ Erro: ' + (data.mensagem || "Não foi possível salvar."));

}

} catch (error) { console.error('Erro ao salvar usuário:', error); }

};

window.excluirUsuario = async function(id) {

if (confirm('Tem certeza que deseja excluir este usuário?')) {

try {

const res = await fetch(`/usuarios/${id}`, { method: 'DELETE' });

const data = await res.json();

if (data.sucesso) {

alert('✅ Usuário excluído.');

atualizarListaUsuarios();

} else {

alert('❌ Erro ao excluir usuário: ' + data.mensagem);

}

} catch (error) { console.error('Erro ao excluir usuário:', error); }

}

};

window.carregarTabelaGestao = async function(tipo) {

const tbodyId = tipo === 'tipos' ? 'tabelaTipos' : 'tabelaLotacoes';

const tbody = document.getElementById(tbodyId);

tbody.innerHTML = "<tr><td colspan='2'>Carregando...</td></tr>";

try {

const res = await fetch(`/gestao/${tipo}`);

const data = await res.json();

tbody.innerHTML = '';

data.forEach(item => {

const tr = document.createElement('tr');

tr.innerHTML = `

<td>${item.nome}</td>

<td><button onclick="excluirItemGestao(${item.id}, '${tipo}')" style="background-color:#c82333;">Excluir</button></td>

`;

tbody.appendChild(tr);

});

} catch (err) { console.error(`Erro ao carregar ${tipo}:`, err); }

};

window.adicionarItemGestao = async function(tipo) {

const inputId = tipo === 'tipos' ? 'novoTipo' : 'novaLotacao';

const nome = document.getElementById(inputId).value.trim();

if (!nome) return;

try {

const res = await fetch(`/gestao/${tipo}`, {

method: 'POST', headers: { 'Content-Type': 'application/json' },

body: JSON.stringify({ nome })

});

const data = await res.json();

if (data.sucesso) {

document.getElementById(inputId).value = '';

carregarTabelaGestao(tipo);

carregarOpcoesDropdowns(); // Atualiza as opções globais

} else {

alert('Erro: ' + data.mensagem);

}

} catch (err) { console.error(`Erro ao adicionar ${tipo}:`, err); }

};

window.excluirItemGestao = async function(id, tipo) {

if (confirm(`Tem certeza que deseja excluir este item?`)) {

try {

const res = await fetch(`/gestao/${tipo}/${id}`, { method: 'DELETE' });

const data = await res.json();

if (data.sucesso) {

carregarTabelaGestao(tipo);

carregarOpcoesDropdowns(); // Atualiza as opções globais

} else {

alert('Erro: ' + data.mensagem);

}

} catch (err) { console.error(`Erro ao excluir ${tipo}:`, err); }

}

};



// Funções da Tela de Relatórios

window.popularFiltrosRelatorio = function() {

const tipoSelect = document.getElementById('filtroRelatorioTipo');

const lotacaoSelect = document.getElementById('filtroRelatorioLotacao');

tipoSelect.innerHTML = '<option value="">Todos</option>';

lotacaoSelect.innerHTML = '<option value="">Todas</option>';

window.opcoesTipos.forEach(opt => tipoSelect.innerHTML += `<option value="${opt.nome}">${opt.nome}</option>`);

window.opcoesLotacoes.forEach(opt => lotacaoSelect.innerHTML += `<option value="${opt.nome}">${opt.nome}</option>`);

};

window.pesquisarProtocolos = async function() {

const filtros = {

numero: document.getElementById('filtroRelatorioNumero').value,

nome: document.getElementById('filtroRelatorioNome').value,

cpf: document.getElementById('filtroRelatorioCpf').value,

dataInicio: document.getElementById('filtroRelatorioDataInicio').value,

dataFim: document.getElementById('filtroRelatorioDataFim').value,

tipo: document.getElementById('filtroRelatorioTipo').value,

lotacao: document.getElementById('filtroRelatorioLotacao').value,

status: document.getElementById('filtroRelatorioStatus').value,

};

const query = new URLSearchParams(filtros).toString();

const tbody = document.getElementById('tabelaRelatorios');

tbody.innerHTML = '<tr><td colspan="6">Buscando...</td></tr>';

try {

const res = await fetch(`/relatorios/pesquisa?${query}`);

const data = await res.json();

tbody.innerHTML = '';

if (data.protocolos.length > 0) {

document.getElementById('totalResultados').textContent = `Total de resultados: ${data.protocolos.length}`;

data.protocolos.forEach(p => {

const tr = document.createElement('tr');

tr.innerHTML = `

<td>${p.numero}</td>

<td>${p.nome}</td>

<td>${p.tipo_requerimento}</td>

<td>${new Date(p.data_solicitacao).toLocaleDateString('pt-BR')}</td>

<td>${p.status}</td>

<td>${p.responsavel}</td>

`;

tbody.appendChild(tr);

});

} else {

document.getElementById('totalResultados').textContent = 'Total de resultados: 0';

tbody.innerHTML = '<tr><td colspan="6">Nenhum resultado encontrado.</td></tr>';

}

} catch(err) { console.error(err); }

};

window.gerarRelatorio = function(formato) {

const filtros = {

numero: document.getElementById('filtroRelatorioNumero').value,

nome: document.getElementById('filtroRelatorioNome').value,

cpf: document.getElementById('filtroRelatorioCpf').value,

dataInicio: document.getElementById('filtroRelatorioDataInicio').value,

dataFim: document.getElementById('filtroRelatorioDataFim').value,

tipo: document.getElementById('filtroRelatorioTipo').value,

lotacao: document.getElementById('filtroRelatorioLotacao').value,

status: document.getElementById('filtroRelatorioStatus').value,

};

const query = new URLSearchParams(filtros).toString();

window.open(`/relatorios/${formato}?${query}`, '_blank');

};



// Funções da Tela de Dashboard

window.popularFiltrosDashboard = function() {

const anoSelect = document.getElementById('filtroDashboardAno');

const anoAtual = new Date().getFullYear();

for (let i = anoAtual; i >= anoAtual - 10; i--) {

anoSelect.innerHTML += `<option value="${i}">${i}</option>`;

}

};

window.carregarDashboard = async function() {

const ano = document.getElementById('filtroDashboardAno').value;

try {

const res = await fetch(`/dashboard/dados?ano=${ano}`);

const data = await res.json();

renderizarGraficos(data);

} catch(err) { console.error('Erro ao carregar dados do dashboard:', err); }

};

window.renderizarGraficos = function(data) {

if (tiposChartInstance) { tiposChartInstance.destroy(); }

const ctxTipos = document.getElementById('graficoTipos').getContext('2d');

tiposChartInstance = new Chart(ctxTipos, {

type: 'doughnut',

data: {

labels: data.porTipo.map(d => d.tipo),

datasets: [{

label: 'Protocolos por Tipo',

data: data.porTipo.map(d => d.total),

backgroundColor: ['#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8', '#6c757d', '#343a40', '#6610f2', '#fd7e14', '#20c997'],

}]

},

options: { responsive: true, maintainAspectRatio: false, legend: { position: 'right' } }

});

// Aqui podem ser adicionados outros gráficos (por status, por mês, etc.)

};





// Funções Auxiliares e de Notificação

async function carregarOpcoesDropdowns() {

try {

const [tiposRes, lotacoesRes] = await Promise.all([

fetch('/gestao/tipos'),

fetch('/gestao/lotacoes')

]);

window.opcoesTipos = await tiposRes.json();

window.opcoesLotacoes = await lotacoesRes.json();

} catch (error) {

console.error("Erro ao carregar opções de dropdowns:", error);

}

}

function popularDropdownsFormulario() {

const tipoSelect = document.getElementById('tipo');

const lotacaoSelect = document.getElementById('lotacao');

tipoSelect.innerHTML = '<option value="">Selecione o tipo...</option>';

lotacaoSelect.innerHTML = '<option value="">Selecione a lotação...</option>';

window.opcoesTipos.forEach(opt => tipoSelect.innerHTML += `<option value="${opt.nome}">${opt.nome}</option>`);

window.opcoesLotacoes.forEach(opt => lotacaoSelect.innerHTML += `<option value="${opt.nome}">${opt.nome}</option>`);

}

function preencherCamposServidor(servidor) {

document.getElementById('nome').value = servidor?.nome || '';

document.getElementById('cpf').value = servidor?.cpf || '';

document.getElementById('rg').value = servidor?.rg || '';

document.getElementById('cargo').value = servidor?.cargo || '';

document.getElementById('lotacao').value = servidor?.lotacao || '';

}

function renderizarPaginacao(totalItens, paginaAtual, containerId, funcaoCallback) {

const container = document.getElementById(containerId);

container.innerHTML = "";

const totalPaginas = Math.ceil(totalItens / itensPorPagina);

if (totalPaginas <= 1) return;

const criarBotao = (texto, pagina, desabilitado = false, ativo = false) => {

const btn = document.createElement('button');

btn.textContent = texto;

btn.disabled = desabilitado;

if (ativo) btn.classList.add('active');

btn.onclick = () => funcaoCallback(pagina);

container.appendChild(btn);

};

criarBotao('<<', 1, paginaAtual === 1);

criarBotao('<', paginaAtual - 1, paginaAtual === 1);

for (let i = 1; i <= totalPaginas; i++) {

if (i === paginaAtual || (i >= paginaAtual - 2 && i <= paginaAtual + 2)) {

criarBotao(i, i, false, i === paginaAtual);

}

}

criarBotao('>', paginaAtual + 1, paginaAtual === totalPaginas);

criarBotao('>>', totalPaginas, paginaAtual === totalPaginas);

}

async function verificarNotificacoes() {

const usuarioLogin = localStorage.getItem('usuarioLogin');

if (!usuarioLogin) return;

try {

const res = await fetch(`/protocolos/notificacoes/${usuarioLogin}`);

const data = await res.json();

const badge = document.getElementById('notification-badge');

if (data.naoLidas > 0) {

badge.textContent = data.naoLidas;

badge.style.display = 'flex';

} else {

badge.style.display = 'none';

}

} catch(err) {

console.error('Erro ao verificar notificações:', err);

}

}
