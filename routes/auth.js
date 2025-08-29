// routes/auth.js
const express = require('express');
const router = express.Router();
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const pool = require('../db');
const { JWT_SECRET } = require('../config');

// Rota de login
router.post('/login', async (req, res, next) => {
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
    next(err);
  }
});

module.exports = router;
