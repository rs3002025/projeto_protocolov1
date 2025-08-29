require('dotenv').config();

const JWT_SECRET = process.env.JWT_SECRET || 'DEFAULT_INSECURE_SECRET_REPLACE_IN_PRODUCTION';

if (process.env.NODE_ENV !== 'test' && !process.env.JWT_SECRET) {
  console.warn('\n!!! ATENÇÃO: A variável de ambiente JWT_SECRET não está definida. Usando um segredo padrão inseguro. Defina esta variável em produção! !!!\n');
}

module.exports = {
  JWT_SECRET,
  PORT: process.env.PORT || 3000,
};
