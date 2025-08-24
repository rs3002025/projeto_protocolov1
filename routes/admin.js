// routes/admin.js

const express = require('express');

const router = express.Router();

const db = require('../db');



// --- ROTAS PARA TIPOS DE REQUERIMENTO ---



// Listar todos os tipos (ativos e inativos) para a tela de gestão

router.get('/tipos/all', async (req, res) => {

    try {

        const result = await db.query('SELECT * FROM tipos_requerimento ORDER BY nome ASC');

        res.json(result.rows);

    } catch (err) { res.status(500).json({ erro: err.message }); }

});



// Listar apenas tipos ativos para os formulários

router.get('/tipos', async (req, res) => {

    try {

        const result = await db.query("SELECT nome FROM tipos_requerimento WHERE ativo = TRUE ORDER BY nome ASC");

        res.json(result.rows.map(r => r.nome));

    } catch (err) { res.status(500).json({ erro: err.message }); }

});



// Adicionar novo tipo

router.post('/tipos', async (req, res) => {

    const { nome } = req.body;

    try {

        await db.query('INSERT INTO tipos_requerimento (nome) VALUES ($1)', [nome]);

        res.json({ sucesso: true });

    } catch (err) { res.status(500).json({ erro: err.message }); }

});



// Alterar status (ativar/desativar)

router.put('/tipos/:id/status', async (req, res) => {

    const { id } = req.params;

    const { ativo } = req.body;

    try {

        await db.query('UPDATE tipos_requerimento SET ativo = $1 WHERE id = $2', [ativo, id]);

        res.json({ sucesso: true });

    } catch (err) { res.status(500).json({ erro: err.message }); }

});





// --- ROTAS PARA LOTAÇÕES ---



// Listar todas as lotações (ativas e inativas)

router.get('/lotacoes/all', async (req, res) => {

    try {

        const result = await db.query('SELECT * FROM lotacoes ORDER BY nome ASC');

        res.json(result.rows);

    } catch (err) { res.status(500).json({ erro: err.message }); }

});



// Listar apenas lotações ativas

router.get('/lotacoes', async (req, res) => {

    try {

        const result = await db.query("SELECT nome FROM lotacoes WHERE ativo = TRUE ORDER BY nome ASC");

        res.json(result.rows.map(r => r.nome));

    } catch (err) { res.status(500).json({ erro: err.message }); }

});



// Adicionar nova lotação

router.post('/lotacoes', async (req, res) => {

    const { nome } = req.body;

    try {

        await db.query('INSERT INTO lotacoes (nome) VALUES ($1)', [nome]);

        res.json({ sucesso: true });

    } catch (err) { res.status(500).json({ erro: err.message }); }

});



// Alterar status da lotação

router.put('/lotacoes/:id/status', async (req, res) => {

    const { id } = req.params;

    const { ativo } = req.body;

    try {

        await db.query('UPDATE lotacoes SET ativo = $1 WHERE id = $2', [ativo, id]);

        res.json({ sucesso: true });

    } catch (err) { res.status(500).json({ erro: err.message }); }

});



module.exports = router;
