// routes/dashboard.js
const express = require('express');
const router = express.Router();
const { authMiddleware } = require('../middleware/auth');
const db = require('../db');

// --- ROTAS PARA NOTIFICAÇÕES ---
router.get('/notificacoes/:usuarioLogin', authMiddleware, async (req, res, next) => {
  const { usuarioLogin } = req.params;
  try {
    const result = await db.query("SELECT COUNT(id) FROM protocolos WHERE responsavel = $1 AND visto = FALSE", [usuarioLogin]);
    const count = result.rows.length > 0 ? parseInt(result.rows[0].count, 10) : 0;
    res.json({ count });
  } catch (err) {
    next(err);
  }
});

router.post('/notificacoes/ler', authMiddleware, async (req, res, next) => {
  const { usuarioLogin } = req.body;
  try {
    await db.query("UPDATE protocolos SET visto = TRUE WHERE responsavel = $1 AND visto = FALSE", [usuarioLogin]);
    res.json({ sucesso: true });
  } catch (err) {
    next(err);
  }
});

// --- ROTA PARA DASHBOARD ---
router.get('/stats', authMiddleware, async (req, res, next) => {
    try {
        const { dataInicio, dataFim, status, tipo, lotacao } = req.query;

        let baseConditions = 'WHERE 1=1';
        const params = [];

        function addCondition(field, value, operator = '=', caseInsensitive = false) {
            if (value) {
                params.push(value);
                const op = caseInsensitive ? 'ILIKE' : operator;
                baseConditions += ` AND ${field} ${op} $${params.length}`;
            }
        }
        addCondition('status', status);
        addCondition('tipo_requerimento', tipo);
        addCondition('lotacao', lotacao);
        if (dataInicio) { params.push(dataInicio); baseConditions += ` AND data_solicitacao >= $${params.length}`; }
        if (dataFim) { params.push(dataFim); baseConditions += ` AND data_solicitacao <= $${params.length}`; }

        const novosPeriodoQuery = `SELECT COUNT(id) FROM protocolos ${baseConditions}`;
        const novosPeriodoResult = await db.query(novosPeriodoQuery, params);

        const pendentesAntigosResult = await db.query("SELECT COUNT(id) FROM protocolos WHERE status NOT IN ('Finalizado', 'Concluído') AND data_solicitacao <= current_date - interval '15 days'");

        const topTiposQuery = `SELECT tipo_requerimento, COUNT(id) as total FROM protocolos ${baseConditions} AND tipo_requerimento IS NOT NULL AND tipo_requerimento != '' GROUP BY tipo_requerimento ORDER BY total DESC LIMIT 5`;
        const topTiposResult = await db.query(topTiposQuery, params);

        const stats = {
            novosNoPeriodo: novosPeriodoResult.rows.length > 0 ? parseInt(novosPeriodoResult.rows[0].count, 10) : 0,
            pendentesAntigos: pendentesAntigosResult.rows.length > 0 ? parseInt(pendentesAntigosResult.rows[0].count, 10) : 0,
            topTipos: topTiposResult.rows
        };
        res.json(stats);
    } catch (err) {
        next(err);
    }
});

module.exports = router;
