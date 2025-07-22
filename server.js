const express = require('express');
const path = require('path');
const cors = require('cors');
const pool = require('./db');
const protocoloRoutes = require('./routes/protocolos');

const app = express();
const port = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Serve arquivos estáticos da pasta public
app.use(express.static(path.join(__dirname, 'public')));

// Rotas de API
app.use('/protocolos', protocoloRoutes);

// Rota de login
app.post('/login', async (req, res) => {
  const { login, senha } = req.body;
  try {
    const result = await pool.query(
      'SELECT nome, tipo, email FROM usuarios WHERE login = $1 AND senha = $2',
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
  const { nome, login, senha, tipo, email } = req.body;
  try {
    await pool.query(
      'INSERT INTO usuarios (nome, login, senha, tipo, email) VALUES ($1, $2, $3, $4, $5)',
      [nome, login, senha, tipo, email]
    );
    res.json({ sucesso: true, mensagem: 'Usuário cadastrado com sucesso.' });
  } catch (err) {
    console.error('Erro ao cadastrar usuário:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao cadastrar usuário.' });
  }
});

// Rota para listar usuários
app.get('/usuarios', async (req, res) => {
  try {
    const result = await pool.query('SELECT id, nome, login, tipo, email FROM usuarios');
    res.json({ usuarios: result.rows });
  } catch (err) {
    console.error('Erro ao buscar usuários:', err);
    res.status(500).json({ erro: 'Erro no servidor' });
  }
});

// Rota raiz para carregar o frontend
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Inicia o servidor
app.listen(port, () => {
  console.log(`Servidor rodando na porta ${port}`);
});
