// routes/api.js
const express = require('express');
const router = express.Router();
const db = require('../db');

// Rotas públicas para usuários autenticados (não-admins) irão aqui.

// Rota para obter tipos de requerimento ativos
router.get('/tipos', async (req, res, next) => {
    try {
        const result = await db.query("SELECT nome FROM tipos_requerimento WHERE ativo = TRUE ORDER BY nome ASC");
        res.json(result.rows.map(r => r.nome));
    } catch (err) { next(err); }
});

// Rota para obter lotações ativas
router.get('/lotacoes', async (req, res, next) => {
    try {
        const result = await db.query("SELECT nome FROM lotacoes WHERE ativo = TRUE ORDER BY nome ASC");
        res.json(result.rows.map(r => r.nome));
    } catch (err) { next(err); }
});

// Rota para obter bairros distintos
router.get('/bairros', async (req, res, next) => {
    try {
        const result = await db.query("SELECT DISTINCT bairro FROM protocolos WHERE bairro IS NOT NULL AND bairro <> '' ORDER BY bairro ASC");
        res.json(result.rows.map(r => r.bairro));
    } catch (err) { next(err); }
});

module.exports = router;
