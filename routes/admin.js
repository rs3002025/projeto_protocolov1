// routes/admin.js
const express = require('express');
const router = express.Router();
const db = require('../db');
const supabase = require('../supabase-client');

// --- ROTAS PARA TIPOS DE REQUERIMENTO ---

router.get('/tipos/all', async (req, res, next) => {
    try {
        const result = await db.query('SELECT * FROM tipos_requerimento ORDER BY nome ASC');
        res.json(result.rows);
    } catch (err) { next(err); }
});


router.post('/tipos', async (req, res, next) => {
    const { nome } = req.body;
    try {
        await db.query('INSERT INTO tipos_requerimento (nome) VALUES ($1)', [nome]);
        res.json({ sucesso: true });
    } catch (err) { next(err); }
});

router.put('/tipos/:id/status', async (req, res, next) => {
    const { id } = req.params;
    const { ativo } = req.body;
    try {
        await db.query('UPDATE tipos_requerimento SET ativo = $1 WHERE id = $2', [ativo, id]);
        res.json({ sucesso: true });
    } catch (err) { next(err); }
});


// --- ROTAS PARA LOTAÇÕES ---

router.get('/lotacoes/all', async (req, res, next) => {
    try {
        const result = await db.query('SELECT * FROM lotacoes ORDER BY nome ASC');
        res.json(result.rows);
    } catch (err) { next(err); }
});


router.post('/lotacoes', async (req, res, next) => {
    const { nome } = req.body;
    try {
        await db.query('INSERT INTO lotacoes (nome) VALUES ($1)', [nome]);
        res.json({ sucesso: true });
    } catch (err) { next(err); }
});

router.put('/lotacoes/:id/status', async (req, res, next) => {
    const { id } = req.params;
    const { ativo } = req.body;
    try {
        await db.query('UPDATE lotacoes SET ativo = $1 WHERE id = $2', [ativo, id]);
        res.json({ sucesso: true });
    } catch (err) { next(err); }
});


// --- NOVA ROTA PARA EXCLUSÃO DE ANEXOS EM MASSA ---
router.delete('/anexos-antigos', async (req, res, next) => {
    const { dataFim } = req.query;
    if (!dataFim) {
        return res.status(400).json({ sucesso: false, mensagem: "É necessário fornecer uma data final." });
    }

    try {
        const { rows: anexosParaExcluir } = await db.query(
            "SELECT id, storage_path FROM anexos WHERE created_at <= $1",
            [dataFim]
        );

        if (anexosParaExcluir.length === 0) {
            return res.json({ sucesso: true, mensagem: "Nenhum anexo encontrado para exclusão no período informado." });
        }

        const storagePaths = anexosParaExcluir.map(anexo => anexo.storage_path);
        const anexoIds = anexosParaExcluir.map(anexo => anexo.id);

        const { error: storageError } = await supabase.storage
            .from('protocolos')
            .remove(storagePaths);

        if (storageError) {
            console.error("Erro ao excluir arquivos do Storage, mas continuando para limpar o banco:", storageError);
        }

        await db.query("DELETE FROM anexos WHERE id = ANY($1::bigint[])", [anexoIds]);
        
        res.json({ sucesso: true, mensagem: `${anexosParaExcluir.length} anexo(s) foram excluídos com sucesso.` });

    } catch (err) {
        next(err);
    }
});


module.exports = router;
