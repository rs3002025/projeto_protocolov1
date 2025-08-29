// middleware/validators.js

const validate = (schema) => (req, res, next) => {
  const errors = [];

  for (const key in schema) {
    const rule = schema[key];
    const value = req.body[key];

    // Check for presence
    if (rule.required && (value === undefined || value === null || value === '')) {
      errors.push(`${key} é obrigatório.`);
      continue; // No need to check other rules if it's missing
    }

    // Skip other checks if value is not present and not required
    if (value === undefined || value === null || value === '') {
        continue;
    }

    // Check for type
    if (rule.type && typeof value !== rule.type) {
      errors.push(`${key} deve ser do tipo ${rule.type}.`);
    }

    // Check for min length
    if (rule.minLength && value.length < rule.minLength) {
      errors.push(`${key} deve ter no mínimo ${rule.minLength} caracteres.`);
    }

    // Check for email format
    if (rule.isEmail) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(value)) {
        errors.push(`${key} não é um email válido.`);
      }
    }
  }

  if (errors.length > 0) {
    return res.status(400).json({ sucesso: false, mensagem: 'Erro de validação.', erros: errors });
  }

  next();
};

const userCreationSchema = {
  nome: { required: true, type: 'string' },
  login: { required: true, type: 'string', minLength: 4 },
  senha: { required: true, type: 'string', minLength: 6 },
  email: { required: true, type: 'string', isEmail: true },
  tipo: { required: true, type: 'string' },
};

module.exports = {
  validate,
  userCreationSchema,
};
