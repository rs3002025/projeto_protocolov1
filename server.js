// server.js
require('dotenv').config();
const express = require('express');
const path = require('path');
const cors = require('cors');
const { authMiddleware, adminMiddleware } = require('./middleware/auth');
const errorHandler = require('./middleware/errorHandler');
const { PORT } = require('./config');

// Import route handlers
const protocoloRoutes = require('./routes/protocolos');
const adminRoutes = require('./routes/admin');
const authRoutes = require('./routes/auth');
const userRoutes = require('./routes/usuarios');
const dashboardRoutes = require('./routes/dashboard');
const apiRoutes = require('./routes/api');

const app = express();

// Middlewares
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Mount routers
app.use('/', authRoutes); // Handles /login
app.use('/usuarios', userRoutes); // Handles /usuarios, /usuarios/:id, etc.
app.use('/api', authMiddleware, apiRoutes);

// Mount specific protocol routes BEFORE generic ones to avoid conflicts with /:id
app.use('/protocolos', dashboardRoutes); // Handles /protocolos/dashboard-stats, /protocolos/notificacoes/*
app.use('/protocolos', protocoloRoutes); // Handles the rest of the protocol routes

// Rota PÚBLICA para consulta de protocolo via QR Code
const pool = require('./db');
app.get('/consulta/:ano/:numero', async (req, res) => {
  // ... (código da rota pública inalterado)
});

// Rota raiz: abre o index.html
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Centralized Error Handler - MUST be the last middleware
app.use(errorHandler);

// Inicia o servidor apenas se não estiver em ambiente de teste
if (process.env.NODE_ENV !== 'test') {
  app.listen(PORT, () => {
    console.log(`Servidor rodando na porta ${PORT}`);
  });
}

module.exports = app;
