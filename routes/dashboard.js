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
router.get('/dashboard-stats', authMiddleware, async (req, res, next) => {
    try {
        let { dataInicio, dataFim, status, tipo, lotacao, evolucaoPeriodo = '30d', evolucaoAgrupamento = 'day' } = req.query;

        // --- Lógica de Condições e Parâmetros ---
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

        // --- Tratamento de Datas ---
        let novosPeriodoConditions = baseConditions;
        const novosPeriodoParams = [...params];
        if (dataInicio) {
            novosPeriodoParams.push(dataInicio);
            novosPeriodoConditions += ` AND data_solicitacao >= $${novosPeriodoParams.length}`;
        }
        if (dataFim) {
            novosPeriodoParams.push(dataFim);
            novosPeriodoConditions += ` AND data_solicitacao <= $${novosPeriodoParams.length}`;
        }
        // Se não houver data de início, define o padrão de 7 dias para a consulta de "novos no período"
        if (!dataInicio) {
            novosPeriodoConditions += ` AND data_solicitacao >= current_date - interval '7 days'`;
        }

        // --- Execução das Consultas ---
        const novosPeriodoQuery = `SELECT COUNT(id) FROM protocolos ${novosPeriodoConditions}`;
        const novosPeriodoResult = await db.query(novosPeriodoQuery, novosPeriodoParams);

        const pendentesAntigosResult = await db.query("SELECT COUNT(id) FROM protocolos WHERE status NOT IN ('Finalizado', 'Concluído') AND data_solicitacao <= current_date - interval '15 days'");

        const topTiposQuery = `SELECT tipo_requerimento, COUNT(id) as total FROM protocolos ${baseConditions} AND tipo_requerimento IS NOT NULL AND tipo_requerimento != '' GROUP BY tipo_requerimento ORDER BY total DESC LIMIT 5`;
        const topTiposResult = await db.query(topTiposQuery, params);

        const statusResult = await db.query(`SELECT status, COUNT(id) as total FROM protocolos ${baseConditions} AND status IS NOT NULL AND status != '' GROUP BY status`, params);

        // --- Lógica da Consulta de Evolução Dinâmica ---
        let evolucaoQuery;
        const groupBy = evolucaoAgrupamento === 'month' ? `date_trunc('month', data_solicitacao)` : `DATE(data_solicitacao)`;
        let whereClause = '';

        switch (evolucaoPeriodo) {
            case '7d':
                whereClause = `WHERE data_solicitacao >= current_date - interval '7 days'`;
                break;
            case 'month':
                whereClause = `WHERE date_trunc('month', data_solicitacao) = date_trunc('month', current_date)`;
                break;
            case 'all':
                whereClause = '';
                break;
            case '30d':
            default:
                whereClause = `WHERE data_solicitacao >= current_date - interval '30 days'`;
                break;
        }
        evolucaoQuery = `SELECT ${groupBy} as "intervalo", COUNT(id) as total FROM protocolos ${whereClause} GROUP BY "intervalo" ORDER BY "intervalo" ASC`;
        const evolucaoResult = await db.query(evolucaoQuery);

        const finalizadosResult = await db.query(`SELECT COUNT(id) FROM protocolos ${baseConditions} AND status IN ('Finalizado', 'Concluído')`, params);

        // --- Montagem do Objeto de Resposta ---
        const stats = {
            novosNoPeriodo: novosPeriodoResult.rows.length > 0 ? parseInt(novosPeriodoResult.rows[0].count, 10) : 0,
            pendentesAntigos: pendentesAntigosResult.rows.length > 0 ? parseInt(pendentesAntigosResult.rows[0].count, 10) : 0,
            topTipos: topTiposResult.rows,
            statusProtocolos: statusResult.rows,
            evolucaoProtocolos: evolucaoResult.rows,
            totalFinalizados: finalizadosResult.rows.length > 0 ? parseInt(finalizadosResult.rows[0].count, 10) : 0
        };
        res.json(stats);
    } catch (err) {
        next(err);
    }
});

module.exports = router;
