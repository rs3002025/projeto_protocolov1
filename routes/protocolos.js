const express = require('express');
const router = express.Router();
const db = require('../db');
const { authMiddleware } = require('../middleware/auth');
const ExcelJS = require('exceljs');
const multer = require('multer');
const supabase = require('../supabase-client');
const path = require('path');

const storage = multer.memoryStorage();
const upload = multer({
    storage: storage,
    limits: { fileSize: 10 * 1024 * 1024 }
});

router.post('/', authMiddleware, async (req, res) => {
  try {
    const { numero, nome, matricula, endereco, municipio, bairro, cep, telefone, cpf, rg, cargo, lotacao, unidade, tipo, requerAo, dataSolicitacao, complemento, status, responsavel } = req.body;
    const result = await db.query(`
      INSERT INTO protocolos (numero, nome, matricula, endereco, municipio, bairro, cep, telefone, cpf, rg, cargo, lotacao, unidade_exercicio, tipo_requerimento, requer_ao, data_solicitacao, observacoes, status, responsavel, visto)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20) RETURNING id`,
      [numero||'', nome||'', matricula||'', endereco||'', municipio||'', bairro||'', cep||'', telefone||'', cpf||'', rg||'', cargo||'', lotacao||'', unidade||'', tipo||'', requerAo||'', dataSolicitacao||null, complemento||'', status||'Aberto', responsavel||'', false]
    );
    res.json({ sucesso: true, mensagem: 'Protocolo salvo com sucesso.', novoProtocoloId: result.rows[0].id });
  } catch (error) {
    if (error.code === '23505') return res.status(400).json({ sucesso: false, mensagem: 'Número de protocolo já existe!' });
    console.error('❌ Erro ao salvar protocolo:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor.' });
  }
});

router.post('/:id/anexos', authMiddleware, upload.single('anexo'), async (req, res) => {
    const { id } = req.params;
    const file = req.file;
    if (!file) return res.status(400).json({ sucesso: false, mensagem: "Nenhum arquivo enviado." });
    const fileName = `${Date.now()}-${file.originalname.replace(/\s/g, '_')}`;
    const filePath = `${id}/${fileName}`;
    try {
        const { error: uploadError } = await supabase.storage.from('protocolos').upload(filePath, file.buffer, { contentType: file.mimetype });
        if (uploadError) throw uploadError;
        await db.query(`INSERT INTO anexos (protocolo_id, file_name, storage_path, file_size, mime_type) VALUES ($1, $2, $3, $4, $5)`, [id, file.originalname, filePath, file.size, file.mimetype]);
        res.json({ sucesso: true, mensagem: 'Anexo enviado com sucesso!' });
    } catch (error) {
        console.error("❌ Erro no upload do anexo:", error);
        res.status(500).json({ sucesso: false, mensagem: "Erro no servidor ao enviar anexo." });
    }
});

router.get('/:id/anexos', authMiddleware, async (req, res) => {
    const { id } = req.params;
    try {
        const result = await db.query("SELECT id, file_name, created_at, file_size FROM anexos WHERE protocolo_id = $1 ORDER BY created_at DESC", [id]);
        res.json({ sucesso: true, anexos: result.rows });
    } catch (error) {
        console.error("❌ Erro ao listar anexos:", error);
        res.status(500).json({ sucesso: false, mensagem: "Erro ao buscar anexos." });
    }
});

router.get('/anexos/:anexo_id/download', authMiddleware, async (req, res) => {
    const { anexo_id } = req.params;
    try {
        const anexoResult = await db.query("SELECT storage_path FROM anexos WHERE id = $1", [anexo_id]);
        if (anexoResult.rows.length === 0) return res.status(404).json({ sucesso: false, mensagem: "Anexo não encontrado." });
        const { data, error } = await supabase.storage.from('protocolos').createSignedUrl(anexoResult.rows[0].storage_path, 60);
        if (error) throw error;
        res.json({ sucesso: true, url: data.signedUrl });
    } catch (error) {
        console.error("❌ Erro ao gerar link de download:", error);
        res.status(500).json({ sucesso: false, mensagem: "Erro ao gerar link de download." });
    }
});

router.delete('/anexos/:anexo_id', authMiddleware, async (req, res) => {
    const { anexo_id } = req.params;
    try {
        const anexoResult = await db.query("SELECT storage_path FROM anexos WHERE id = $1", [anexo_id]);
        if (anexoResult.rows.length === 0) return res.status(404).json({ sucesso: false, mensagem: "Anexo não encontrado." });
        await supabase.storage.from('protocolos').remove([anexoResult.rows[0].storage_path]);
        await db.query("DELETE FROM anexos WHERE id = $1", [anexo_id]);
        res.json({ sucesso: true, mensagem: "Anexo excluído com sucesso." });
    } catch (error) {
        console.error("❌ Erro ao excluir anexo:", error);
        res.status(500).json({ sucesso: false, mensagem: "Erro ao excluir anexo." });
    }
});

router.post('/atualizar', authMiddleware, async (req, res) => {
  try {
    const { protocoloId, novoStatus, novoResponsavel, observacao } = req.body;
    const { login: usuarioLogado } = req.user;
    await db.query(`UPDATE protocolos SET status = $1, responsavel = $2, visto = FALSE WHERE id = $3`, [novoStatus, novoResponsavel, protocoloId]);
    await db.query(`INSERT INTO historico_protocolos (protocolo_id, status, responsavel, observacao) VALUES ($1, $2, $3, $4)`, [protocoloId, novoStatus, usuarioLogado, observacao || '']);
    res.json({ sucesso: true, mensagem: 'Protocolo atualizado com histórico salvo.' });
  } catch (error) {
    console.error('❌ Erro ao atualizar protocolo e salvar histórico:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor ao atualizar protocolo.' });
  }
});

router.get('/pesquisa', authMiddleware, async (req, res) => {
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

router.get('/backup', authMiddleware, async (req, res) => {
  // ... (código do backup inalterado)
});

router.get('/historico/:id', authMiddleware, async (req, res) => {
  // ... (código do histórico inalterado)
});

router.get('/meus/:responsavel', authMiddleware, async (req, res) => {
  // ... (código de meus protocolos inalterado)
});

router.get('/ultimoNumero/:ano', authMiddleware, async (req, res) => {
  // ... (código do último número inalterado)
});

router.get('/servidor/:matricula', authMiddleware, async (req, res) => {
  // ... (código do servidor inalterado)
});

router.get('/notificacoes/:usuarioLogin', authMiddleware, async (req, res) => {
  // ... (código de notificações inalterado)
});

router.post('/notificacoes/ler', authMiddleware, async (req, res) => {
  // ... (código de ler notificações inalterado)
});

router.get('/dashboard-stats', authMiddleware, async (req, res) => {
  // ... (código do dashboard inalterado)
});

router.get('/', authMiddleware, async (req, res) => {
  // ... (código de listar todos inalterado)
});

router.get('/:id', authMiddleware, async (req, res) => {
  // ... (código de buscar por id inalterado)
});

router.put('/:id', authMiddleware, async (req, res) => {
  // ... (código de atualizar completo inalterado)
});

router.delete('/:id', authMiddleware, async (req, res) => {
  // ... (código de excluir inalterado)
});

module.exports = router;
