// routes/protocolos.js
const express = require('express');
const router = express.Router();
const db = require('../db');
const ExcelJS = require('exceljs');
const multer = require('multer');
const supabase = require('../supabase-client');
const path = require('path');

// Configuração do Multer para upload de arquivos em memória
const storage = multer.memoryStorage();
const upload = multer({
    storage: storage,
    limits: { fileSize: 10 * 1024 * 1024 } // Limite de 10MB
});

// Salvar novo protocolo
router.post('/', async (req, res) => {
  try {
    const { numero, nome, matricula, endereco, municipio, bairro, cep, telefone, cpf, rg, cargo, lotacao, unidade, tipo, requerAo, dataSolicitacao, complemento, status, responsavel } = req.body;
    
    const result = await db.query(`
      INSERT INTO protocolos (numero, nome, matricula, endereco, municipio, bairro, cep, telefone, cpf, rg, cargo, lotacao, unidade_exercicio, tipo_requerimento, requer_ao, data_solicitacao, observacoes, status, responsavel, visto)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
      RETURNING id
    `, [
        numero || '', nome || '', matricula || '', endereco || '', municipio || '', bairro || '', cep || '', telefone || '', cpf || '', rg || '', 
        cargo || '', lotacao || '', unidade || '', tipo || '', requerAo || '', dataSolicitacao || null, complemento || '', status || 'Aberto', 
        responsavel || '', 
        false // <-- 20º valor para a coluna "visto"
    ]);
    
    const novoProtocoloId = result.rows[0].id;
    res.json({ sucesso: true, mensagem: 'Protocolo salvo com sucesso.', novoProtocoloId: novoProtocoloId });

  } catch (error) {
    if (error.code === '23505') { 
      return res.status(400).json({ sucesso: false, mensagem: 'Número de protocolo já existe!' });
    }
    console.error('❌ Erro ao salvar protocolo:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor.' });
  }
});


// ROTA PARA FAZER UPLOAD DE ANEXOS
router.post('/:id/anexos', upload.single('anexo'), async (req, res) => {
    const { id } = req.params;
    const file = req.file;
    if (!file) {
        return res.status(400).json({ sucesso: false, mensagem: "Nenhum arquivo enviado." });
    }
    const fileName = `${Date.now()}-${file.originalname.replace(/\s/g, '_')}`;
    const filePath = `${id}/${fileName}`;
    try {
        const { error: uploadError } = await supabase.storage
            .from('protocolos')
            .upload(filePath, file.buffer, { contentType: file.mimetype });
        if (uploadError) throw uploadError;
        await db.query(`
            INSERT INTO anexos (protocolo_id, file_name, storage_path, file_size, mime_type)
            VALUES ($1, $2, $3, $4, $5)
        `, [id, file.originalname, filePath, file.size, file.mimetype]);
        res.json({ sucesso: true, mensagem: 'Anexo enviado com sucesso!' });
    } catch (error) {
        console.error("❌ Erro no upload do anexo:", error);
        res.status(500).json({ sucesso: false, mensagem: "Erro no servidor ao enviar anexo." });
    }
});

// ROTA PARA LISTAR ANEXOS DE UM PROTOCOLO
router.get('/:id/anexos', async (req, res) => {
    const { id } = req.params;
    try {
        const result = await db.query(
            "SELECT id, file_name, created_at, file_size FROM anexos WHERE protocolo_id = $1 ORDER BY created_at DESC",
            [id]
        );
        res.json({ sucesso: true, anexos: result.rows });
    } catch (error) {
        console.error("❌ Erro ao listar anexos:", error);
        res.status(500).json({ sucesso: false, mensagem: "Erro ao buscar anexos." });
    }
});

// ROTA PARA GERAR LINK DE DOWNLOAD DE UM ANEXO
router.get('/anexos/:anexo_id/download', async (req, res) => {
    const { anexo_id } = req.params;
    try {
        const anexoResult = await db.query("SELECT storage_path FROM anexos WHERE id = $1", [anexo_id]);
        if (anexoResult.rows.length === 0) {
            return res.status(404).json({ sucesso: false, mensagem: "Anexo não encontrado." });
        }
        const storagePath = anexoResult.rows[0].storage_path;
        const { data, error } = await supabase.storage
            .from('protocolos')
            .createSignedUrl(storagePath, 60); // Link válido por 60 segundos
        if (error) throw error;
        res.json({ sucesso: true, url: data.signedUrl });
    } catch (error) {
        console.error("❌ Erro ao gerar link de download:", error);
        res.status(500).json({ sucesso: false, mensagem: "Erro ao gerar link de download." });
    }
});

// ROTA PARA EXCLUIR UM ANEXO ESPECÍFICO
router.delete('/anexos/:anexo_id', async (req, res) => {
    const { anexo_id } = req.params;
    try {
        const anexoResult = await db.query("SELECT storage_path FROM anexos WHERE id = $1", [anexo_id]);
        if (anexoResult.rows.length === 0) {
            return res.status(404).json({ sucesso: false, mensagem: "Anexo não encontrado." });
        }
        const storagePath = anexoResult.rows[0].storage_path;
        await supabase.storage.from('protocolos').remove([storagePath]);
        await db.query("DELETE FROM anexos WHERE id = $1", [anexo_id]);
        res.json({ sucesso: true, mensagem: "Anexo excluído com sucesso." });
    } catch (error) {
        console.error("❌ Erro ao excluir anexo:", error);
        res.status(500).json({ sucesso: false, mensagem: "Erro ao excluir anexo." });
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

    // CORREÇÃO AQUI: Removido o "+ 1"
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

    // CORREÇÃO AQUI: Removido o "+ 1"
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

// Listar protocolos do responsável (Meus Protocolos)
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

// Buscar último número de protocolo do ano
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

// GET /protocolos/servidor/:matricula
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

// --- ROTAS PARA NOTIFICAÇÕES ---
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

// --- ROTA PARA DASHBOARD (CORRIGIDA E COM FILTROS) ---
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


// --- ROTAS GLOBAIS (DEVEM VIR POR ÚLTIMO) ---

// Listar todos os protocolos
router.get('/', async (req, res) => {
  try {
    const result = await db.query(`SELECT id, numero, nome, matricula, tipo_requerimento, status, responsavel FROM protocolos ORDER BY id DESC`);
    res.json({ protocolos: result.rows });
  } catch (error) {
    console.error('❌ Erro ao listar protocolos:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao listar protocolos.' });
  }
});

// Buscar protocolo completo pelo ID (DEVE SER A ÚLTIMA ROTA GET)
router.get('/:id', async (req, res) => {
  const protocoloId = req.params.id;
  try {
    const result = await db.query(`SELECT * FROM protocolos WHERE id = $1`, [protocoloId]);
    if (result.rows.length === 0) {
      return res.status(404).json({ sucesso: false, mensagem: 'Protocolo não encontrado.' });
    }
    res.json({ protocolo: result.rows[0] });
  } catch (error) {
    console.error('❌ Erro ao buscar protocolo por ID:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao buscar protocolo.' });
  }
});

// ROTA PARA ATUALIZAR (EDITAR) UM PROTOCOLO COMPLETO
router.put('/:id', async (req, res) => {
    const { id } = req.params;
    const { 
        numero, nome, matricula, endereco, municipio, bairro, cep, telefone, 
        cpf, rg, cargo, lotacao, unidade, tipo, requerAo, dataSolicitacao, complemento 
    } = req.body;

    try {
        await db.query(`
            UPDATE protocolos SET
                numero = $1, nome = $2, matricula = $3, endereco = $4, municipio = $5, bairro = $6,
                cep = $7, telefone = $8, cpf = $9, rg = $10, cargo = $11, lotacao = $12, 
                unidade_exercicio = $13, tipo_requerimento = $14, requer_ao = $15, 
                data_solicitacao = $16, observacoes = $17
            WHERE id = $18
        `, [
            numero, nome, matricula, endereco, municipio, bairro, cep, telefone, 
            cpf, rg, cargo, lotacao, unidade, tipo, requerAo, dataSolicitacao, complemento, id
        ]);
        res.json({ sucesso: true, mensagem: 'Protocolo atualizado com sucesso!' });
    } catch (err) {
        console.error('❌ Erro ao atualizar protocolo:', err);
        res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor ao atualizar o protocolo.' });
    }
});

// ROTA PARA EXCLUIR UM PROTOCOLO
router.delete('/:id', async (req, res) => {
    const { id } = req.params;
    try {
        // Primeiro, deleta o histórico associado para evitar registros órfãos
        await db.query('DELETE FROM historico_protocolos WHERE protocolo_id = $1', [id]);
        
        // Depois, deleta o protocolo principal
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

module.exports = router;
