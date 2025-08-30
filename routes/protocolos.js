// routes/protocolos.js
const express = require('express');
const router = express.Router();
const { authMiddleware } = require('../middleware/auth');
const db = require('../db');
const ExcelJS = require('exceljs');
const multer = require('multer');
const supabase = require('../supabase-client');
const path = require('path');

const storage = multer.memoryStorage();
const upload = multer({
    storage: storage,
    limits: { fileSize: 10 * 1024 * 1024 }
});

router.post('/', authMiddleware, async (req, res, next) => {
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
        false
    ]);
    const novoProtocoloId = result.rows[0].id;

    // Adiciona o primeiro registro ao histórico
    await db.query(`
      INSERT INTO historico_protocolos (protocolo_id, status, responsavel, observacao)
      VALUES ($1, $2, $3, $4)
    `, [novoProtocoloId, status, responsavel, 'Protocolo criado no sistema.']);

    res.json({ sucesso: true, mensagem: 'Protocolo salvo com sucesso.', novoProtocoloId: novoProtocoloId });
  } catch (error) {
    next(error);
  }
});

router.post('/:id/anexos', authMiddleware, upload.single('anexo'), async (req, res, next) => {
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
        next(error);
    }
});

router.get('/:id/anexos', authMiddleware, async (req, res, next) => {
    const { id } = req.params;
    try {
        const result = await db.query(
            "SELECT id, file_name, created_at, file_size FROM anexos WHERE protocolo_id = $1 ORDER BY created_at DESC",
            [id]
        );
        res.json({ sucesso: true, anexos: result.rows });
    } catch (error) {
        next(error);
    }
});

router.get('/anexos/:anexo_id/download', authMiddleware, async (req, res, next) => {
    const { anexo_id } = req.params;
    try {
        const anexoResult = await db.query("SELECT storage_path FROM anexos WHERE id = $1", [anexo_id]);
        if (anexoResult.rows.length === 0) {
            return res.status(404).json({ sucesso: false, mensagem: "Anexo não encontrado." });
        }
        const storagePath = anexoResult.rows[0].storage_path;
        const { data, error } = await supabase.storage
            .from('protocolos')
            .createSignedUrl(storagePath, 60);
        if (error) throw error;
        res.json({ sucesso: true, url: data.signedUrl });
    } catch (error) {
        next(error);
    }
});

router.delete('/anexos/:anexo_id', authMiddleware, async (req, res, next) => {
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
        next(error);
    }
});

router.post('/atualizar', authMiddleware, async (req, res, next) => {
  try {
    const { protocoloId, novoStatus, novoResponsavel, observacao } = req.body;
    const { login: usuarioLogado } = req.user;
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
    next(error);
  }
});

router.get('/pesquisa', authMiddleware, async (req, res, next) => {
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

    query += ' ORDER BY data_solicitacao DESC';
    const result = await db.query(query, params);
    res.json({ protocolos: result.rows });
  } catch (error) {
    next(error);
  }
});

router.get('/backup', authMiddleware, async (req, res, next) => {
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
    next(error);
  }
});

router.get('/historico/:id', authMiddleware, async (req, res, next) => {
  const protocoloId = req.params.id;
  try {
    const result = await db.query(`SELECT * FROM historico_protocolos WHERE protocolo_id = $1 ORDER BY data_movimentacao DESC`, [protocoloId]);
    res.json({ historico: result.rows });
  } catch (error) {
    next(error);
  }
});

router.get('/meus/:responsavel', authMiddleware, async (req, res, next) => {
  const responsavel = req.params.responsavel;
  try {
    const result = await db.query(`SELECT id, numero, nome, matricula, tipo_requerimento, status, responsavel FROM protocolos WHERE responsavel = $1 ORDER BY id DESC`, [responsavel]);
    res.json({ protocolos: result.rows });
  } catch (error) {
    next(error);
  }
});

router.get('/ultimoNumero/:ano', authMiddleware, async (req, res, next) => {
  const { ano } = req.params;
  try {
    const { rows } = await db.query(`SELECT numero FROM protocolos WHERE numero LIKE $1`, [`%/${ano}`]);
    const numeros = rows.map(r => parseInt(r.numero.split('/')[0], 10)).filter(n => !isNaN(n));
    const max = numeros.length > 0 ? Math.max(...numeros) : 0;
    res.json({ ultimo: max });
  } catch (err) {
    next(err);
  }
});

router.get('/servidor/:matricula', authMiddleware, async (req, res, next) => {
  const matricula = req.params.matricula;
  try {
    const result = await db.query(`SELECT matricula, nome, lotacao, cargo, unidade_de_exercicio FROM servidores WHERE matricula = $1 LIMIT 1`, [matricula]);
    if (result.rows.length === 0) {
      return res.status(404).json({ mensagem: 'Servidor não encontrado' });
    }
    res.json(result.rows[0]);
  } catch (error) {
    next(error);
  }
});

router.get('/', authMiddleware, async (req, res, next) => {
  try {
    const result = await db.query(`SELECT id, numero, nome, matricula, tipo_requerimento, status, responsavel FROM protocolos ORDER BY id DESC`);
    res.json({ protocolos: result.rows });
  } catch (error) {
    next(error);
  }
});

router.get('/:id', authMiddleware, async (req, res, next) => {
  const protocoloId = req.params.id;
  try {
    const result = await db.query(`SELECT * FROM protocolos WHERE id = $1`, [protocoloId]);
    if (result.rows.length === 0) {
      return res.status(404).json({ sucesso: false, mensagem: 'Protocolo não encontrado.' });
    }
    res.json({ protocolo: result.rows[0] });
  } catch (error) {
    next(error);
  }
});

router.put('/:id', authMiddleware, async (req, res, next) => {
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
        next(err);
    }
});

router.delete('/:id', authMiddleware, async (req, res, next) => {
    const { id } = req.params;
    try {
        await db.query('DELETE FROM historico_protocolos WHERE protocolo_id = $1', [id]);
        const result = await db.query('DELETE FROM protocolos WHERE id = $1', [id]);

        if (result.rowCount === 0) {
            return res.status(404).json({ sucesso: false, mensagem: 'Protocolo não encontrado para exclusão.' });
        }

        res.json({ sucesso: true, mensagem: 'Protocolo e seu histórico foram excluídos com sucesso!' });
    } catch (err) {
        next(err);
    }
});

module.exports = router;
