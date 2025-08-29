const jwt = require('jsonwebtoken');

// Use o segredo do ambiente ou um segredo padrão INSEGURO com um aviso.
const JWT_SECRET = process.env.JWT_SECRET || 'DEFAULT_INSECURE_SECRET_REPLACE_IN_PRODUCTION';

if (process.env.NODE_ENV !== 'test' && !process.env.JWT_SECRET) {
  console.warn('\n!!! ATENÇÃO: A variável de ambiente JWT_SECRET não está definida. Usando um segredo padrão inseguro. Defina esta variável em produção! !!!\n');
}

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

module.exports = {
  authMiddleware,
  adminMiddleware,
};
