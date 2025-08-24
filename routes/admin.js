// routes/admin.js
const express = require('express');
const router = express.Router();
const db = require('../db');
const supabase = require('../supabase-client'); // Adicionado para interagir com o Storage

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


// --- NOVA ROTA PARA EXCLUSÃO DE ANEXOS EM MASSA ---
router.delete('/anexos-antigos', async (req, res) => {
    const { dataFim } = req.query;
    if (!dataFim) {
        return res.status(400).json({ sucesso: false, mensagem: "É necessário fornecer uma data final." });
    }

    try {
        // Passo 1: Encontrar os anexos antigos no banco de dados
        const { rows: anexosParaExcluir } = await db.query(
            "SELECT id, storage_path FROM anexos WHERE created_at <= $1",
            [dataFim]
        );

        if (anexosParaExcluir.length === 0) {
            return res.json({ sucesso: true, mensagem: "Nenhum anexo encontrado para exclusão no período informado." });
        }

        const storagePaths = anexosParaExcluir.map(anexo => anexo.storage_path);
        const anexoIds = anexosParaExcluir.map(anexo => anexo.id);

        // Passo 2: Excluir os arquivos do Supabase Storage
        const { error: storageError } = await supabase.storage
            .from('protocolos')
            .remove(storagePaths);

        if (storageError) {
            // Mesmo com erro no storage, prossegue para apagar do banco para manter consistência
            console.error("Erro ao excluir arquivos do Storage, mas continuando para limpar o banco:", storageError);
        }

        // Passo 3: Excluir os registros da tabela 'anexos'
        await db.query("DELETE FROM anexos WHERE id = ANY($1::bigint[])", [anexoIds]);
        
        res.json({ sucesso: true, mensagem: `${anexosParaExcluir.length} anexo(s) foram excluídos com sucesso.` });

    } catch (err) {
        console.error("❌ Erro na exclusão em massa de anexos:", err);
        res.status(500).json({ sucesso: false, mensagem: "Erro no servidor ao excluir anexos." });
    }
});


module.exports = router;
