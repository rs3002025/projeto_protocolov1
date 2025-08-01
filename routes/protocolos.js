const express = require('express');
const router = express.Router();
const db = require('../db'); // conexão com Supabase
const ExcelJS = require('exceljs');

// Salvar novo protocolo com verificação de número duplicado
router.post('/', async (req, res) => {
  try {
    const {
      numero, nome, matricula, endereco, municipio, bairro, cep,
      telefone, cpf, rg, cargo, lotacao, unidade, tipo,
      requerAo, dataSolicitacao, complemento,
      status, responsavel
    } = req.body;

    console.log('✅ Dados recebidos:', req.body);

    const existente = await db.query(`SELECT id FROM protocolos WHERE numero = $1`, [numero]);
    if (existente.rows.length > 0) {
      return res.status(400).json({ sucesso: false, mensagem: 'Número de protocolo já existe!' });
    }

    await db.query(`
      INSERT INTO protocolos (
        numero, nome, matricula, endereco, municipio, bairro, cep,
        telefone, cpf, rg, cargo, lotacao, unidade_exercicio, tipo_requerimento,
        requer_ao, data_solicitacao, observacoes, status, responsavel
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7,
        $8, $9, $10, $11, $12, $13, $14,
        $15, $16, $17, $18, $19
      )
    `, [
      numero || '', nome || '', matricula || '', endereco || '', municipio || '', bairro || '', cep || '',
      telefone || '', cpf || '', rg || '', cargo || '', lotacao || '', unidade || '', tipo || '',
      requerAo || '', dataSolicitacao || null, complemento || '', status || 'Aberto', responsavel || ''
    ]);

    res.json({ sucesso: true, mensagem: 'Protocolo salvo com sucesso.' });

  } catch (error) {
    console.error('❌ Erro ao salvar protocolo:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor.' });
  }
});

// Atualizar status/responsável e registrar histórico
router.post('/atualizar', async (req, res) => {
  try {
    const { protocoloId, novoStatus, novoResponsavel, observacao, usuarioLogado } = req.body;

    await db.query(`
      UPDATE protocolos
      SET status = $1,
          responsavel = $2
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

// Pesquisa de protocolos com filtros
router.get('/pesquisa', async (req, res) => {
  try {
    const { numero, nome, status } = req.query;

    let query = 'SELECT numero, nome, status, data_solicitacao FROM protocolos WHERE 1=1';
    const params = [];

    if (numero) {
      query += ' AND numero LIKE $' + (params.length + 1);
      params.push(`%${numero}%`);
    }

    if (nome) {
      query += ' AND nome LIKE $' + (params.length + 1);
      params.push(`%${nome}%`);
    }

    if (status) {
      query += ' AND status = $' + (params.length + 1);
      params.push(status);
    }

    query += ' ORDER BY data_solicitacao DESC';

    const result = await db.query(query, params);
    res.json({ protocolos: result.rows });

  } catch (error) {
    console.error('Erro na pesquisa:', error);
    res.status(500).json({ erro: 'Erro na pesquisa' });
  }
});

// Buscar histórico de protocolo
router.get('/historico/:id', async (req, res) => {
  const protocoloId = req.params.id;
  try {
    const result = await db.query(`
      SELECT * FROM historico_protocolos
      WHERE protocolo_id = $1
      ORDER BY data_movimentacao DESC
    `, [protocoloId]);

    res.json({ historico: result.rows });
  } catch (error) {
    console.error('❌ Erro ao buscar histórico:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao buscar histórico.' });
  }
});

// Listar todos os protocolos
router.get('/', async (req, res) => {
  try {
    const result = await db.query(`
      SELECT id, numero, nome, matricula, tipo_requerimento, status, responsavel
      FROM protocolos
      ORDER BY id DESC
    `);
    res.json({ protocolos: result.rows });
  } catch (error) {
    console.error('❌ Erro ao listar protocolos:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao listar protocolos.' });
  }
});

// Listar protocolos do responsável (Meus Protocolos)
router.get('/meus/:responsavel', async (req, res) => {
  const responsavel = req.params.responsavel;
  try {
    const result = await db.query(`
      SELECT id, numero, nome, matricula, tipo_requerimento, status, responsavel
      FROM protocolos
      WHERE responsavel = $1
      ORDER BY id DESC
    `, [responsavel]);
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
    const { rows } = await db.query(`
      SELECT numero FROM protocolos
      WHERE numero LIKE $1
      ORDER BY numero DESC LIMIT 1
    `, [`${ano}-%`]);

    if (rows.length > 0) {
      const ultimo = parseInt(rows[0].numero.split('-')[1], 10);
      res.json({ ultimo });
    } else {
      res.json({ ultimo: 0 });
    }
  } catch (err) {
    console.error("Erro ao buscar último número:", err);
    res.status(500).json({ erro: "Erro interno" });
  }
});

// Rota filtro por data (sem gerar arquivo)
router.get('/filtro', async (req, res) => {
  const { dataInicio, dataFim } = req.query;

  if (!dataInicio || !dataFim) {
    return res.status(400).json({ erro: 'Informe dataInicio e dataFim no formato YYYY-MM-DD' });
  }

  try {
    const result = await db.query(`
      SELECT * FROM protocolos
      WHERE data_solicitacao BETWEEN $1 AND $2
      ORDER BY data_solicitacao
    `, [dataInicio, dataFim]);

    res.json({ protocolos: result.rows });
  } catch (err) {
    console.error('Erro na filtragem:', err);
    res.status(500).json({ erro: 'Erro ao buscar protocolos por data' });
  }
});

// Rota para gerar backup/exportar protocolos por período em Excel
router.get('/backup', async (req, res) => {
  try {
    const { dataInicio, dataFim } = req.query;

    if (!dataInicio || !dataFim) {
      return res.status(400).json({ sucesso: false, mensagem: 'Informe dataInicio e dataFim (YYYY-MM-DD)' });
    }

    const result = await db.query(`
      SELECT * FROM protocolos
      WHERE data_solicitacao BETWEEN $1 AND $2
      ORDER BY data_solicitacao
    `, [dataInicio, dataFim]);

    if (result.rows.length === 0) {
      return res.status(404).json({ sucesso: false, mensagem: 'Nenhum protocolo encontrado nesse período.' });
    }

    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('Backup Protocolos');

    sheet.columns = [
      { header: 'Número', key: 'numero' },
      { header: 'Matrícula', key: 'matricula' },
      { header: 'Nome', key: 'nome' },
      { header: 'Endereço', key: 'endereco' },
      { header: 'Município', key: 'municipio' },
      { header: 'Bairro', key: 'bairro' },
      { header: 'CEP', key: 'cep' },
      { header: 'Telefone', key: 'telefone' },
      { header: 'CPF', key: 'cpf' },
      { header: 'RG', key: 'rg' },
      { header: 'Cargo', key: 'cargo' },
      { header: 'Lotação', key: 'lotacao' },
      { header: 'Unidade', key: 'unidade_exercicio' },
      { header: 'Tipo de Requerimento', key: 'tipo_requerimento' },
      { header: 'Requer ao', key: 'requer_ao' },
      { header: 'Data Solicitação', key: 'data_solicitacao' },
      { header: 'Observações', key: 'observacoes' },
      { header: 'Data Envio', key: 'data_envio' },
      { header: 'Status', key: 'status' },
      { header: 'Responsável', key: 'responsavel' }
    ];

    result.rows.forEach(row => sheet.addRow(row));

    const fileName = `backup_protocolos_${dataInicio}_a_${dataFim}.xlsx`;

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${fileName}"`);

    await workbook.xlsx.write(res);
    res.end();

  } catch (error) {
    console.error('Erro ao gerar backup:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao gerar backup.' });
  }
});

router.put('/usuarios/:id', async (req, res) => {
  try {
    const { id } = req.params;
    const { login, tipo, email, nome_completo, cpf } = req.body;

    await pool.query(`
      UPDATE usuarios
      SET login = $1,
          tipo = $2,
          email = $3,
          nome_completo = $4,
          cpf = $5
      WHERE id = $6
    `, [login, tipo, email, nome_completo, cpf, id]);

    res.json({ sucesso: true, mensagem: 'Usuário atualizado com sucesso.' });
  } catch (err) {
    console.error(err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao atualizar usuário.' });
  }
});


// Buscar protocolo completo pelo ID
router.get('/:id', async (req, res) => {
  const protocoloId = req.params.id;
  try {
    const result = await db.query(`
      SELECT * FROM protocolos WHERE id = $1
    `, [protocoloId]);

    if (result.rows.length === 0) {
      return res.status(404).json({ sucesso: false, mensagem: 'Protocolo não encontrado.' });
    }

    res.json({ protocolo: result.rows[0] });
  } catch (error) {
    console.error('❌ Erro ao buscar protocolo por ID:', error);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao buscar protocolo.' });
  }
});

module.exports = router;
