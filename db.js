const { Pool } = require('pg');

const pool = new Pool({
  connectionString: 'postgresql://postgres:Caravela300c@db.lugrnpsyhzlegxwfvzqq.supabase.co:5432/postgres',
  ssl: { rejectUnauthorized: false }
});

module.exports = pool;
