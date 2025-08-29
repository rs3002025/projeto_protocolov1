// server.js
require('dotenv').config();
const express = require('express');
const path = require('path');
const cors = require('cors');
const pool = require('./db');
const protocoloRoutes = require('./routes/protocolos');
const adminRoutes = require('./routes/admin');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { authMiddleware, adminMiddleware } = require('./middleware/auth');

// Use o segredo do ambiente ou um segredo padrão INSEGURO com um aviso.
const JWT_SECRET = process.env.JWT_SECRET || 'DEFAULT_INSECURE_SECRET_REPLACE_IN_PRODUCTION';

if (process.env.NODE_ENV !== 'test' && !process.env.JWT_SECRET) {
  console.warn('\n!!! ATENÇÃO: A variável de ambiente JWT_SECRET não está definida. Usando um segredo padrão inseguro. Defina esta variável em produção! !!!\n');
}

const app = express();
const port = process.env.PORT || 3000;

// Middlewares
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use('/protocolos', protocoloRoutes);
app.use('/admin', authMiddleware, adminMiddleware, adminRoutes);

// Rota de login
app.post('/login', async (req, res) => {
  const { login, senha } = req.body;
  if (!login || !senha) {
    return res.status(400).json({ sucesso: false, mensagem: 'Login e senha são obrigatórios.' });
  }

  try {
    const result = await pool.query(
      "SELECT id, nome, login, tipo, email, senha as password_or_hash FROM usuarios WHERE login = $1 AND status = 'ativo'",
      [login]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({ sucesso: false, mensagem: 'Login ou senha inválidos.' });
    }

    const user = result.rows[0];
    const storedPassword = user.password_or_hash;
    let passwordIsValid = false;

    if (storedPassword && (storedPassword.startsWith('$2a$') || storedPassword.startsWith('$2b$'))) {
      passwordIsValid = await bcrypt.compare(senha, storedPassword);
    } else {
      passwordIsValid = (senha === storedPassword);
      if (passwordIsValid) {
        const saltRounds = 10;
        const hash = await bcrypt.hash(senha, saltRounds);
        await pool.query('UPDATE usuarios SET senha = $1 WHERE id = $2', [hash, user.id]);
      }
    }

    if (passwordIsValid) {
      const userResponse = { nome: user.nome, login: user.login, tipo: user.tipo, email: user.email };
      const token = jwt.sign(
        { login: user.login, tipo: user.tipo },
        JWT_SECRET,
        { expiresIn: '8h' }
      );
      res.json({ sucesso: true, usuario: userResponse, token: token });
    } else {
      res.status(401).json({ sucesso: false, mensagem: 'Login ou senha inválidos.' });
    }
  } catch (err) {
    console.error('Erro no login:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro interno no servidor.' });
  }
});

// Rota para cadastrar novo usuário
app.post('/usuarios', async (req, res) => {
  const { login, senha, tipo, email, nome, cpf } = req.body;
   if (!login || !senha) {
      return res.status(400).json({ sucesso: false, mensagem: "Login e senha são obrigatórios." });
  }
  try {
    const saltRounds = 10;
    const hashedPassword = await bcrypt.hash(senha, saltRounds);
    await pool.query(
      `INSERT INTO usuarios (login, senha, tipo, email, nome, cpf, status) VALUES ($1, $2, $3, $4, $5, $6, 'ativo')`,
      [login, hashedPassword, tipo, email, nome, cpf]
    );
    res.status(201).json({ sucesso: true, mensagem: 'Usuário cadastrado com sucesso.' });
  } catch (err) {
    console.error('Erro ao cadastrar usuário:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao cadastrar usuário.' });
  }
});

// Rota para listar todos os usuários (Admin)
app.get('/usuarios', authMiddleware, adminMiddleware, async (req, res) => {
  try {
    const result = await pool.query('SELECT id, nome, login, email, cpf, tipo, status FROM usuarios ORDER BY nome ASC');
    res.json({ usuarios: result.rows });
  } catch (err) {
    console.error('Erro ao buscar usuários:', err);
    res.status(500).json({ erro: 'Erro no servidor' });
  }
});

// Rota para o próprio usuário alterar sua senha (Apenas autenticado)
app.put('/usuarios/minha-senha', authMiddleware, async (req, res) => {
    const { usuarioLogin } = req.user;
    const { senhaAtual, novaSenha } = req.body;

    if (!usuarioLogin || !senhaAtual || !novaSenha) {
        return res.status(400).json({ sucesso: false, mensagem: "Dados incompletos." });
    }
    try {
        const userResult = await pool.query('SELECT id, senha FROM usuarios WHERE login = $1', [usuarioLogin]);
        if (userResult.rows.length === 0) {
            return res.status(404).json({ sucesso: false, mensagem: "Usuário não encontrado." });
        }

        const user = userResult.rows[0];
        const storedPassword = user.senha;
        let passwordIsValid = false;

        if (storedPassword && (storedPassword.startsWith('$2a$') || storedPassword.startsWith('$2b$'))) {
            passwordIsValid = await bcrypt.compare(senhaAtual, storedPassword);
        } else {
            passwordIsValid = (senhaAtual === storedPassword);
        }

        if (!passwordIsValid) {
            return res.status(403).json({ sucesso: false, mensagem: "A senha atual está incorreta." });
        }

        const saltRounds = 10;
        const hashedNewPassword = await bcrypt.hash(novaSenha, saltRounds);
        await pool.query('UPDATE usuarios SET senha = $1 WHERE login = $2', [hashedNewPassword, usuarioLogin]);
        res.json({ sucesso: true, mensagem: "Senha alterada com sucesso!" });
    } catch (err) {
        console.error('Erro ao alterar a própria senha:', err);
        res.status(500).json({ sucesso: false, mensagem: 'Erro no servidor ao alterar a senha.' });
    }
});

// Rota para ATUALIZAR dados de um usuário (Admin)
app.put('/usuarios/:id', authMiddleware, adminMiddleware, async (req, res) => {
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

// Rota para RESETAR A SENHA de um usuário (Admin)
app.put('/usuarios/:id/senha', authMiddleware, adminMiddleware, async (req, res) => {
  const { id } = req.params;
  const { novaSenha } = req.body;
  if (!novaSenha) {
      return res.status(400).json({ sucesso: false, mensagem: "A nova senha é obrigatória." });
  }
  try {
    const saltRounds = 10;
    const hashedPassword = await bcrypt.hash(novaSenha, saltRounds);
    await pool.query('UPDATE usuarios SET senha = $1 WHERE id = $2', [hashedPassword, id]);
    res.json({ sucesso: true, mensagem: 'Senha atualizada com sucesso.' });
  } catch (err) {
    console.error('Erro ao resetar senha:', err);
    res.status(500).json({ sucesso: false, mensagem: 'Erro ao resetar senha.' });
  }
});

// Rota para DESATIVAR/REATIVAR um usuário (Admin)
app.put('/usuarios/:id/status', authMiddleware, adminMiddleware, async (req, res) => {
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

// Rota PÚBLICA para consulta de protocolo via QR Code
app.get('/consulta/:ano/:numero', async (req, res) => {
  // ... (código da rota pública inalterado)
});

// Rota raiz: abre o index.html
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Inicia o servidor apenas se não estiver em ambiente de teste
if (process.env.NODE_ENV !== 'test') {
  app.listen(port, () => {
    console.log(`Servidor rodando na porta ${port}`);
  });
}

module.exports = app;
