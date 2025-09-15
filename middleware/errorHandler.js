// middleware/errorHandler.js

/**
 * Centralized error handler middleware.
 * This should be the last middleware added to the app.
 */
function errorHandler(err, req, res, next) {
  // Log the error for debugging purposes.
  // In a production environment, you might want to use a more sophisticated logger.
  console.error(err);

  // If the error has a specific status code and message, use it.
  // This allows us to create custom errors elsewhere and have them handled here.
  if (err.statusCode) {
    return res.status(err.statusCode).json({
      sucesso: false,
      mensagem: err.message || 'Ocorreu um erro.',
    });
  }

  // For unique constraint violations from PostgreSQL (code '23505')
  if (err.code === '23505') {
      return res.status(400).json({
          sucesso: false,
          mensagem: 'O registro já existe e não pode ser duplicado.'
      });
  }

  // For all other errors, send a generic 500 Internal Server Error response.
  // This prevents leaking implementation details to the client.
  res.status(500).json({
    sucesso: false,
    mensagem: 'Erro interno no servidor.',
  });
}

module.exports = errorHandler;
