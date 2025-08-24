// routes/protocolos.js
const express = require('express');
const router = express.Router();
const db = require('../db');
const ExcelJS = require('exceljs');
const multer = require('multer');
const supabase = require('../supabase-client');
const path = require('path');

// Configuração do Multer para upload de arquivos em memória, com limite de 10MB
const storage = multer.memoryStorage();
const upload = multer({ 
    storage: storage,
    limits: { fileSize: 10 * 1024 * 1024 } // 10MB
});

// Salvar novo protocolo (agora retorna o ID do novo protocolo)
router.post('/', async (req, res) => {
  try {
    const { numero, nome, matricula, endereco, municipio, bairro, cep, telefone, cpf, rg, cargo, lotacao, unidade, tipo, requerAo, dataSolicitacao, complemento, status, responsavel } = req.body;
    
    // A query agora usa RETURNING id para pegar o ID do protocolo recém-criado
    const result = await db.query(`
      INSERT INTO protocolos (numero, nome, matricula, endereco, municipio, bairro, cep, telefone, cpf, rg, cargo, lotacao, unidade_exercicio, tipo_requerimento, requer_ao, data_solicitacao, observacoes, status, responsavel, visto)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, FALSE)
      RETURNING id
    `, [numero || '', nome || '', matricula || '', endereco || '', municipio || '', bairro || '', cep || '', telefone || '', cpf || '', rg || '', cargo || '', lotacao || '', unidade || '', tipo || '', requerAo || '', dataSolicitacao || null, complemento || '', status || 'Aberto', responsavel || '']);
    
    const novoProtocoloId = result.rows[0].id;
    res.json({ sucesso: true, mensagem: 'Protocolo salvo com sucesso.', novoProtocoloId: novoProtocoloId });

  } catch (error) {
    if (error.code === '23505') { // Código de erro para violação de unique constraint (número duplicado)
        return res.status(400).json({ sucesso: false, mensagem: 'Número de protocolo já existe!' });
    }
    console.error('❌ Erro ao salvar protocolo:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor.' });
  }
});

// Atualizar status/responsável e registrar histórico
router.post('/atualizar', async (req, res) => {
  try {
    const { protocoloId, novoStatus, novoResponsavel, observacao, usuarioLogado } = req.body;
    await db.query(`
      UPDATE protocolos SET status = $1, responsavel = $2, visto = FALSE
      WHERE id = $3
    `, [novoStatus, novoResponsavel, protocoloId]);
    await db.query(`
      INSERT INTO historico_protocolos (protocolo_id, status, responsavel, observacao)
      VALUES ($1, $2, $3, $4)
    `, [protocoloId, novoStatus, usuarioLogado, observacao || '']);
    res.json({ sucesso: true, mensagem: 'Protocolo atualizado com histórico salvo.' });
  } catch (error) {
    console.error('❌ Erro ao atualizar protocolo e salvar histórico:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor ao atualizar protocolo.' });
  }
});

// Pesquisa de protocolos com filtros avançados
router.get('/pesquisa', async (req, res) => {
  try {
    const { numero, nome, status, dataInicio, dataFim, tipo, lotacao } = req.query;
    let query = `SELECT id, numero, nome, matricula, tipo_requerimento, status, responsavel, data_solicitacao FROM protocolos WHERE 1=1`;
    const params = [];

    if (numero) { params.push(`%${numero}%`); query += ` AND numero LIKE $${params.length}`; }
    if (nome) { params.push(`%${nome}%`); query += ` AND nome ILIKE $${params.length}`; }
    if (status) { params.push(status); query += ` AND status = $${params.length}`; }
    if (dataInicio) { params.push(dataInicio); query += ` AND data_solicitacao >= $${params.length}`; }
    if (dataFim) { params.push(dataFim); query += ` AND data_solicitacao <= $${params.length}`; }
    if (tipo) { params.push(tipo); query += ` AND tipo_requerimento = $${params.length}`; }
    if (lotacao) { params.push(lotacao); query += ` AND lotacao = $${params.length}`; }

    query += ' ORDER BY data_solicitacao DESC';
    const result = await db.query(query, params);
    res.json({ protocolos: result.rows });
  } catch (error) {
    console.error('Erro na pesquisa avançada:', error);
    res.status(500).json({ erro: 'Erro na pesquisa avançada' });
  }
});

// Gerar backup/exportar protocolos por período em Excel
router.get('/backup', async (req, res) => {
  try {
    const { numero, nome, status, dataInicio, dataFim, tipo, lotacao } = req.query;
    let query = `SELECT * FROM protocolos WHERE 1=1`;
    const params = [];
    if (numero) { params.push(`%${numero}%`); query += ` AND numero LIKE $${params.length}`; }
    if (nome) { params.push(`%${nome}%`); query += ` AND nome ILIKE $${params.length}`; }
    if (status) { params.push(status); query += ` AND status = $${params.length}`; }
    if (dataInicio) { params.push(dataInicio); query += ` AND data_solicitacao >= $${params.length}`; }
    if (dataFim) { params.push(dataFim); query += ` AND data_solicitacao <= $${params.length}`; }
    if (tipo) { params.push(tipo); query += ` AND tipo_requerimento = $${params.length}`; }
    if (lotacao) { params.push(lotacao); query += ` AND lotacao = $${params.length}`; }
    query += ' ORDER BY data_solicitacao';
    const result = await db.query(query, params);
    if (result.rows.length === 0) {
      return res.status(404).send('Nenhum protocolo encontrado com os filtros informados.');
    }
    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('Backup Protocolos');
    sheet.columns = [ { header: 'Número', key: 'numero' }, { header: 'Matrícula', key: 'matricula' }, { header: 'Nome', key: 'nome' }, { header: 'Endereço', key: 'endereco' }, { header: 'Município', key: 'municipio' }, { header: 'Bairro', key: 'bairro' }, { header: 'CEP', key: 'cep' }, { header: 'Telefone', key: 'telefone' }, { header: 'CPF', key: 'cpf' }, { header: 'RG', key: 'rg' }, { header: 'Cargo', key: 'cargo' }, { header: 'Lotação', key: 'lotacao' }, { header: 'Unidade', key: 'unidade_exercicio' }, { header: 'Tipo de Requerimento', key: 'tipo_requerimento' }, { header: 'Requer ao', key: 'requer_ao' }, { header: 'Data Solicitação', key: 'data_solicitacao' }, { header: 'Observações', key: 'observacoes' }, { header: 'Status', key: 'status' }, { header: 'Responsável', key: 'responsavel' }];
    sheet.addRows(result.rows);
    const fileName = `backup_protocolos.xlsx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${fileName}"`);
    await workbook.xlsx.write(res);
    res.end();
  } catch (error) {
    console.error('Erro ao gerar backup:', error);
    res.status(500).send('Erro ao gerar backup.');
  }
});

// --- ROTAS ESPECÍFICAS (DEVEM VIR ANTES DE /:id) ---

// Buscar histórico de protocolo
router.get('/historico/:id', async (req, res) => { /* ... (código existente) */ });
// Listar protocolos do responsável (Meus Protocolos)
router.get('/meus/:responsavel', async (req, res) => { /* ... (código existente) */ });
// Buscar último número de protocolo do ano
router.get('/ultimoNumero/:ano', async (req, res) => { /* ... (código existente) */ });
// GET /protocolos/servidor/:matricula
router.get('/servidor/:matricula', async (req, res) => { /* ... (código existente) */ });
// --- ROTAS PARA NOTIFICAÇÕES ---
router.get('/notificacoes/:usuarioLogin', async (req, res) => { /* ... (código existente) */ });
router.post('/notificacoes/ler', async (req, res) => { /* ... (código existente) */ });
// --- ROTA PARA DASHBOARD ---
router.get('/dashboard-stats', async (req, res) => { /* ... (código existente) */ });

// --- CÓDIGO COMPLETO DAS FUNÇÕES ACIMA (PARA REFERÊNCIA) ---
router.get('/historico/:id', async (req, res) => {
  const protocoloId = req.params.id;
  try {
    const result = await db.query(`SELECT * FROM historico_protocolos WHERE protocolo_id = $1 ORDER BY data_movimentacao DESC`, [protocoloId]);
    res.json({ historico: result.rows });
  } catch (error) {
    console.error('❌ Erro ao buscar histórico:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao buscar histórico.' });
  }
});
router.get('/meus/:responsavel', async (req, res) => {
  const responsavel = req.params.responsavel;
  try {
    const result = await db.query(`SELECT id, numero, nome, matricula, tipo_requerimento, status, responsavel FROM protocolos WHERE responsavel = $1 ORDER BY id DESC`, [responsavel]);
    res.json({ protocolos: result.rows });
  } catch (error) {
    console.error('❌ Erro ao listar protocolos do responsável:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao listar seus protocolos.' });
  }
});
router.get('/ultimoNumero/:ano', async (req, res) => {
  const { ano } = req.params;
  try {
    const { rows } = await db.query(`SELECT numero FROM protocolos WHERE numero LIKE $1`, [`%/${ano}`]);
    const numeros = rows.map(r => parseInt(r.numero.split('/')[0], 10)).filter(n => !isNaN(n));
    const max = numeros.length > 0 ? Math.max(...numeros) : 0;
    res.json({ ultimo: max });
  } catch (err) {
    console.error("Erro ao buscar último número:", err);
    res.status(500).json({ erro: "Erro interno" });
  }
});
router.get('/servidor/:matricula', async (req, res) => {
  const matricula = req.params.matricula;
  try {
    const result = await db.query(`SELECT matricula, nome, lotacao, cargo, unidade_de_exercicio FROM servidores WHERE matricula = $1 LIMIT 1`, [matricula]);
    if (result.rows.length === 0) {
      return res.status(404).json({ mensagem: 'Servidor não encontrado' });
    }
    res.json(result.rows[0]);
  } catch (error) {
    console.error('Erro ao buscar servidor:', error);
    res.status(500).json({ mensagem: 'Erro interno no servidor' });
  }
});
router.get('/notificacoes/:usuarioLogin', async (req, res) => {
  const { usuarioLogin } = req.params;
  try {
    const result = await db.query("SELECT COUNT(id) FROM protocolos WHERE responsavel = $1 AND visto = FALSE", [usuarioLogin]);
    const count = result.rows.length > 0 ? parseInt(result.rows[0].count, 10) : 0;
    res.json({ count });
  } catch (err) {
    console.error('Erro ao buscar notificações:', err);
    res.status(500).json({ count: 0 });
  }
});
router.post('/notificacoes/ler', async (req, res) => {
  const { usuarioLogin } = req.body;
  try {
    await db.query("UPDATE protocolos SET visto = TRUE WHERE responsavel = $1 AND visto = FALSE", [usuarioLogin]);
    res.json({ sucesso: true });
  } catch (err) {
    console.error('Erro ao marcar notificações como lidas:', err);
    res.status(500).json({ sucesso: false });
  }
});
router.get('/dashboard-stats', async (req, res) => {
    try {
        const { dataInicio, dataFim, status, tipo, lotacao } = req.query;
        
        let baseConditions = 'WHERE 1=1';
        const params = [];
        function addCondition(field, value, operator = '=', caseInsensitive = false) {
            if (value) {
                params.push(value);
                const op = caseInsensitive ? 'ILIKE' : operator;
                baseConditions += ` AND ${field} ${op} $${params.length}`;
            }
        }
        addCondition('status', status);
        addCondition('tipo_requerimento', tipo);
        addCondition('lotacao', lotacao);
        if (dataInicio) { params.push(dataInicio); baseConditions += ` AND data_solicitacao >= $${params.length}`; }
        if (dataFim) { params.push(dataFim); baseConditions += ` AND data_solicitacao <= $${params.length}`; }

        const novosPeriodoQuery = `SELECT COUNT(id) FROM protocolos ${baseConditions}`;
        const novosPeriodoResult = await db.query(novosPeriodoQuery, params);

        const pendentesAntigosResult = await db.query("SELECT COUNT(id) FROM protocolos WHERE status NOT IN ('Finalizado', 'Concluído') AND data_solicitacao <= current_date - interval '15 days'");

        const topTiposQuery = `SELECT tipo_requerimento, COUNT(id) as total FROM protocolos ${baseConditions} AND tipo_requerimento IS NOT NULL AND tipo_requerimento != '' GROUP BY tipo_requerimento ORDER BY total DESC LIMIT 5`;
        const topTiposResult = await db.query(topTiposQuery, params);

        const stats = {
            novosNoPeriodo: novosPeriodoResult.rows.length > 0 ? parseInt(novosPeriodoResult.rows[0].count, 10) : 0,
            pendentesAntigos: pendentesAntigosResult.rows.length > 0 ? parseInt(pendentesAntigosResult.rows[0].count, 10) : 0,
            topTipos: topTiposResult.rows
        };
        res.json(stats);
    } catch (err) {
        console.error('Erro ao buscar estatísticas do dashboard:', err);
        res.status(500).json({ erro: 'Erro no servidor ao buscar estatísticas' });
    }
});
router.get('/', async (req, res) => {
  try {
    const result = await db.query(`SELECT id, numero, nome, matricula, tipo_requerimento, status, responsavel FROM protocolos ORDER BY id DESC`);
    res.json({ protocolos: result.rows });
  } catch (error) {
    console.error('❌ Erro ao listar protocolos:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao listar protocolos.' });
  }
});

// --- NOVAS ROTAS PARA ANEXOS DE ARQUIVOS ---
// (Adicione aqui)

// --- ROTAS DE EDIÇÃO E EXCLUSÃO DE PROTOCOLOS ---
router.put('/:id', async (req, res) => { /* ... (código existente) */ });
router.delete('/:id', async (req, res) => { /* ... (código existente) */ });
// --- (As implementações completas estão no bloco final) ---

// --- CÓDIGO COMPLETO DAS FUNÇÕES ACIMA ---
router.put('/:id', async (req, res) => {
    const { id } = req.params;
    const { numero, nome, matricula, endereco, municipio, bairro, cep, telefone, cpf, rg, cargo, lotacao, unidade, tipo, requerAo, dataSolicitacao, complemento } = req.body;
    try {
        await db.query(`
            UPDATE protocolos SET numero = $1, nome = $2, matricula = $3, endereco = $4, municipio = $5, bairro = $6, cep = $7, telefone = $8, cpf = $9, rg = $10, cargo = $11, lotacao = $12, unidade_exercicio = $13, tipo_requerimento = $14, requer_ao = $15, data_solicitacao = $16, observacoes = $17
            WHERE id = $18
        `, [ numero, nome, matricula, endereco, municipio, bairro, cep, telefone, cpf, rg, cargo, lotacao, unidade, tipo, requerAo, dataSolicitacao, complemento, id ]);
        res.json({ sucesso: true, mensagem: 'Protocolo atualizado com sucesso!' });
    } catch (err) {
        console.error('❌ Erro ao atualizar protocolo:', err);
        res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor ao atualizar o protocolo.' });
    }
});
router.delete('/:id', async (req, res) => {
    const { id } = req.params;
    try {
        await db.query('DELETE FROM historico_protocolos WHERE protocolo_id = $1', [id]);
        const result = await db.query('DELETE FROM protocolos WHERE id = $1', [id]);
        if (result.rowCount === 0) {
            return res.status(404).json({ sucesso: false, mensagem: 'Protocolo não encontrado para exclusão.' });
        }
        res.json({ sucesso: true, mensagem: 'Protocolo e seu histórico foram excluídos com sucesso!' });
    } catch (err) {
        console.error('❌ Erro ao excluir protocolo:', err);
        res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor ao excluir o protocolo.' });
    }
});

// DEVE SER A ÚLTIMA ROTA GET
router.get('/:id', async (req, res) => {
  const protocoloId = req.params.id;
  try {
    const result = await db.query(`SELECT * FROM protocolos WHERE id = $1`, [protocoloId]);
    if (result.rows.length === 0) {
      return res.status(404).json({ sucesso: false, mensagem: 'Protocolo não encontrado.' });
    }
    res.json({ protocolo: result.rows[0], sucesso: true });
  } catch (error) {
    console.error('❌ Erro ao buscar protocolo por ID:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao buscar protocolo.' });
  }
});

module.exports = router;
