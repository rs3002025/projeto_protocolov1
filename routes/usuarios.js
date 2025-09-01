// routes/usuarios.js
const express = require('express');
const router = express.Router();
const bcrypt = require('bcrypt');
const pool = require('../db');
const { authMiddleware, adminMiddleware, authTodosUsuariosLogadosMiddleware } = require('../middleware/auth');
const { validate, userCreationSchema } = require('../middleware/validators');

// Rota para cadastrar novo usuário
// Path: /usuarios
router.post('/', validate(userCreationSchema), async (req, res, next) => {
  const { login, senha, tipo, email, nome, cpf } = req.body;
  try {
    const saltRounds = 10;
    const hashedPassword = await bcrypt.hash(senha, saltRounds);
    await pool.query(
      `INSERT INTO usuarios (login, senha, tipo, email, nome, cpf, status) VALUES ($1, $2, $3, $4, $5, $6, 'ativo')`,
      [login, hashedPassword, tipo, email, nome, cpf]
    );
    res.status(201).json({ sucesso: true, mensagem: 'Usuário cadastrado com sucesso.' });
  } catch (err) {
    next(err);
  }
});

// Rota para listar todos os usuários (Admin)
// Path: /usuarios
router.get('/', authMiddleware, authTodosUsuariosLogadosMiddleware, async (req, res, next) => {
  try {
    const result = await pool.query('SELECT id, nome, login, email, cpf, tipo, status FROM usuarios ORDER BY nome ASC');
    res.json({ usuarios: result.rows });
  } catch (err) {
    next(err);
  }
});

// Rota para o próprio usuário alterar sua senha (Apenas autenticado)
// Path: /usuarios/minha-senha
router.put('/minha-senha', authMiddleware, async (req, res, next) => {
    const { login } = req.user;
    const { senhaAtual, novaSenha } = req.body;

    if (!login || !senhaAtual || !novaSenha) {
        return res.status(400).json({ sucesso: false, mensagem: "Dados incompletos." });
    }
    try {
        const userResult = await pool.query('SELECT id, senha FROM usuarios WHERE login = $1', [login]);
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
        await pool.query('UPDATE usuarios SET senha = $1 WHERE login = $2', [hashedNewPassword, login]);
        res.json({ sucesso: true, mensagem: "Senha alterada com sucesso!" });
    } catch (err) {
        next(err);
    }
});

// Rota para ATUALIZAR dados de um usuário (Admin)
// Path: /usuarios/:id
router.put('/:id', authMiddleware, adminMiddleware, async (req, res, next) => {
  const { id } = req.params;
  const { nome, login, email, tipo, cpf } = req.body;
  try {
    await pool.query(
      'UPDATE usuarios SET nome = $1, login = $2, email = $3, tipo = $4, cpf = $5 WHERE id = $6',
      [nome, login, email, tipo, cpf, id]
    );
    res.json({ sucesso: true, mensagem: 'Usuário atualizado com sucesso.' });
  } catch (err) {
    next(err);
  }
});

// Rota para RESETAR A SENHA de um usuário (Admin)
// Path: /usuarios/:id/senha
router.put('/:id/senha', authMiddleware, adminMiddleware, async (req, res, next) => {
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
    next(err);
  }
});

// Rota para DESATIVAR/REATIVAR um usuário (Admin)
// Path: /usuarios/:id/status
router.put('/:id/status', authMiddleware, adminMiddleware, async (req, res, next) => {
  const { id } = req.params;
  const { status } = req.body;
  try {
    await pool.query('UPDATE usuarios SET status = $1 WHERE id = $2', [status, id]);
    res.json({ sucesso: true, mensagem: `Usuário ${status === 'ativo' ? 'reativado' : 'desativado'} com sucesso.` });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
