// server.js
const express = require('express');
const path = require('path');
const cors = require('cors');
const pool = require('./db');
const protocoloRoutes = require('./routes/protocolos');
const adminRoutes = require('./routes/admin');

const app = express();
const port = process.env.PORT || 3000;

// Middlewares
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use('/protocolos', protocoloRoutes);
app.use('/admin', adminRoutes);

// Rota de login
app.post('/login', async (req, res) => {
  const { login, senha } = req.body;
  try {
    const result = await pool.query(
      "SELECT nome, login, tipo, email FROM usuarios WHERE login = $1 AND senha = $2 AND status = 'ativo'",
      [login, senha]
    );

    if (result.rows.length > 0) {
      res.json({ sucesso: true, usuario: result.rows[0] });
    } else {
      res.json({ sucesso: false, mensagem: 'Login ou senha inválidos.' });
    }
  } catch (err) {
    console.error('Erro no login:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro interno no servidor.' });
  }
});

// Rota para cadastrar novo usuário
app.post('/usuarios', async (req, res) => {
  const { login, senha, tipo, email, nome, cpf } = req.body;
  try {
    await pool.query(`
      INSERT INTO usuarios (login, senha, tipo, email, nome, cpf, status)
      VALUES ($1, $2, $3, $4, $5, $6, 'ativo')
    `, [login, senha, tipo, email, nome, cpf]);
    res.json({ sucesso: true, mensagem: 'Usuário cadastrado com sucesso.' });
  } catch (err) {
    console.error('Erro ao cadastrar usuário:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao cadastrar usuário.' });
  }
});

// Rota para listar todos os usuários
app.get('/usuarios', async (req, res) => {
  try {
    const result = await pool.query('SELECT id, nome, login, email, cpf, tipo, status FROM usuarios ORDER BY nome ASC');
    res.json({ usuarios: result.rows });
  } catch (err) {
    console.error('Erro ao buscar usuários:', err);
    res.status(500).json({ erro: 'Erro no servidor' });
  }
});

// Rota para ATUALIZAR dados de um usuário
app.put('/usuarios/:id', async (req, res) => {
  const { id } = req.params;
  const { nome, login, email, tipo, cpf } = req.body;
  try {
    await pool.query(
      'UPDATE usuarios SET nome = $1, login = $2, email = $3, tipo = $4, cpf = $5 WHERE id = $6',
      [nome, login, email, tipo, cpf, id]
    );
    res.json({ sucesso: true, mensagem: 'Usuário atualizado com sucesso.' });
  } catch (err) {
    console.error('Erro ao atualizar usuário:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao atualizar usuário.' });
  }
});

// Rota para RESETAR A SENHA (Admin)
app.put('/usuarios/:id/senha', async (req, res) => {
  const { id } = req.params;
  const { novaSenha } = req.body;
  try {
    await pool.query('UPDATE usuarios SET senha = $1 WHERE id = $2', [novaSenha, id]);
    res.json({ sucesso: true, mensagem: 'Senha atualizada com sucesso.' });
  } catch (err) {
    console.error('Erro ao resetar senha:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao resetar senha.' });
  }
});

// Rota para DESATIVAR/REATIVAR um usuário (Admin)
app.put('/usuarios/:id/status', async (req, res) => {
  const { id } = req.params;
  const { status } = req.body;
  try {
    await pool.query('UPDATE usuarios SET status = $1 WHERE id = $2', [status, id]);
    res.json({ sucesso: true, mensagem: `Usuário ${status === 'ativo' ? 'reativado' : 'desativado'} com sucesso.` });
  } catch (err) {
    console.error('Erro ao alterar status do usuário:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao alterar status do usuário.' });
  }
});

// Rota para o próprio usuário alterar sua senha
app.put('/usuarios/minha-senha', async (req, res) => {
    const { usuarioLogin, senhaAtual, novaSenha } = req.body;
    if (!usuarioLogin || !senhaAtual || !novaSenha) {
        return res.status(400).json({ sucesso: false, mensagem: "Dados incompletos." });
    }
    try {
        const userResult = await pool.query('SELECT senha FROM usuarios WHERE login = $1', [usuarioLogin]);
        if (userResult.rows.length === 0) {
            return res.status(404).json({ sucesso: false, mensagem: "Usuário não encontrado." });
        }
        const user = userResult.rows[0];
        if (user.senha !== senhaAtual) {
            return res.status(403).json({ sucesso: false, mensagem: "A senha atual está incorreta." });
        }
        await pool.query('UPDATE usuarios SET senha = $1 WHERE login = $2', [novaSenha, usuarioLogin]);
        res.json({ sucesso: true, mensagem: "Senha alterada com sucesso!" });
    } catch (err) {
        console.error('Erro ao alterar a própria senha:', err);
        res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor ao alterar a senha.' });
    }
});


// Rota PÚBLICA para consulta de protocolo via QR Code
app.get('/consulta/:ano/:numero', async (req, res) => {
  try {
    const { ano, numero } = req.params;
    const numeroProtocolo = `${String(numero).padStart(4, '0')}/${ano}`;
    const result = await pool.query(
      'SELECT numero, nome, status FROM protocolos WHERE numero = $1',
      [numeroProtocolo]
    );

    if (result.rows.length === 0) {
      return res.status(404).send('<h1>Protocolo não encontrado</h1>');
    }
    const protocolo = result.rows[0];
    res.send(`
      <!DOCTYPE html>
      <html lang="pt-BR">
      <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Consulta de Protocolo</title>
        <style>
          body { font-family: Arial, sans-serif; background-color: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
          .card { background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); text-align: center; max-width: 90%; }
          h1 { color: #2e7d32; margin-bottom: 20px; } p { font-size: 1.1em; color: #333; margin: 10px 0; }
          strong { color: #555; } .status { font-weight: bold; font-size: 1.2em; padding: 8px 15px; border-radius: 5px; color: white; }
          .status.Concluído, .status.Finalizado { background-color: #28a745; }
          .status.Em.análise, .status.Pendente.de.documento { background-color: #ffc107; color: #333; }
          .status.Enviado, .status.Encaminhado { background-color: #17a2b8; }
        </style>
      </head>
      <body>
        <div class="card">
          <h1>Consulta de Protocolo</h1>
          <p><strong>Número:</strong> ${protocolo.numero}</p>
          <p><strong>Requerente:</strong> ${protocolo.nome}</p>
          <p><strong>Status:</strong> <span class="status ${protocolo.status.replace(/\s+/g, '.')}">${protocolo.status}</span></p>
        </div>
      </body>
      </html>
    `);
  } catch (err) {
    console.error('Erro na consulta pública:', err);
    res.status(500).send('<h1>Erro ao consultar protocolo.</h1>');
  }
});

// Rota raiz: abre o index.html
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Inicia o servidor
app.listen(port, () => {
  console.log(`Servidor rodando na porta ${port}`);
});
