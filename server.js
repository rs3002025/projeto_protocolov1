// server.js
const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');
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

const app = express();
const port = process.env.PORT || 3000;

// Middlewares
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));
app.use('/protocolos', protocoloRoutes);
// Protegendo todas as rotas de admin com autenticação e verificação de admin
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

    // Verifica se a senha armazenada é um hash bcrypt ou texto plano
    if (storedPassword && (storedPassword.startsWith('$2a$') || storedPassword.startsWith('$2b$'))) {
      passwordIsValid = await bcrypt.compare(senha, storedPassword);
    } else {
      // É uma senha em texto plano (legado), parte da migração transparente
      passwordIsValid = (senha === storedPassword);
      if (passwordIsValid) {
        // Migra a senha para hash de forma transparente
        const saltRounds = 10;
        const hash = await bcrypt.hash(senha, saltRounds);
        await pool.query('UPDATE usuarios SET senha = $1 WHERE id = $2', [hash, user.id]);
      }
    }

    if (passwordIsValid) {
      // Não enviar a senha de volta para o cliente
      const userResponse = {
          nome: user.nome,
          login: user.login,
          tipo: user.tipo,
          email: user.email
      };

      // Gerar o token JWT
      const token = jwt.sign(
        { login: user.login, tipo: user.tipo },
        process.env.JWT_SECRET,
        { expiresIn: '8h' } // Token expira em 8 horas
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
    await pool.query(`
      INSERT INTO usuarios (login, senha, tipo, email, nome, cpf, status)
      VALUES ($1, $2, $3, $4, $5, $6, 'ativo')
    `, [login, hashedPassword, tipo, email, nome, cpf]);
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
    // O login do usuário vem do token decodificado, não do corpo da requisição
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
      <!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Consulta de Protocolo</title>
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
          <h1>Consulta de Protocolo</h1><p><strong>Número:</strong> ${protocolo.numero}</p><p><strong>Requerente:</strong> ${protocolo.nome}</p>
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

// Inicia o servidor apenas se não estiver em ambiente de teste
if (process.env.NODE_ENV !== 'test') {
  app.listen(port, () => {
    console.log(`Servidor rodando na porta ${port}`);
  });
}

module.exports = app; // Exporta o app para ser usado nos testes
