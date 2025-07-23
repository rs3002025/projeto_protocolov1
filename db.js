const { Pool } = require('pg');

const pool = new Pool({
  connectionString: 'postgresql://postgres.lugrnpsyhzlegxwfvzqq:Caravela300c@aws-0-sa-east-1.pooler.supabase.com:5432/postgres',
  ssl: { rejectUnauthorized: false }
});

module.exports = pool;
