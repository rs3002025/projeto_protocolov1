const jwt = require('jsonwebtoken');
const { JWT_SECRET } = require('../config');

const authMiddleware = (req, res, next) => {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ sucesso: false, mensagem: 'Acesso negado. Nenhum token fornecido.' });
  }

  const token = authHeader.split(' ')[1];

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.user = decoded;
    next();
  } catch (err) {
    res.status(403).json({ sucesso: false, mensagem: 'Token inválido ou expirado.' });
  }
};

const adminMiddleware = (req, res, next) => {
  if (req.user && req.user.tipo === 'admin') {
    next();
  } else {
    res.status(403).json({ sucesso: false, mensagem: 'Acesso negado. Requer permissão de administrador.' });
  }
};

const authTodosUsuariosLogadosMiddleware = (req, res, next) => {
  if (req.user && (req.user.tipo === 'admin' || req.user.tipo === 'padrao' || req.user.tipo === 'usuario')) {
    next();
  } else {
    res.status(403).json({ sucesso: false, mensagem: 'Acesso negado. Requer permissão de administrador, padrão ou usuário.' });
  }
};

module.exports = {
  authMiddleware,
  adminMiddleware,
  authTodosUsuariosLogadosMiddleware,
};
