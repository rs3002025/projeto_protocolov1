const { Client } = require('pg');

const client = new Client({
  connectionString: 'postgresql://postgres:Caravela300c@db.lugrnpsyhzlegxwfvzqq.supabase.co:5432/postgres',
  ssl: { rejectUnauthorized: false }
});

client.connect()
  .then(() => {
    console.log('Conectado ao banco de dados com sucesso!');
    return client.query('SELECT NOW()');
  })
  .then(res => {
    console.log('Hora atual no banco:', res.rows[0]);
    client.end();
  })
  .catch(err => console.error('Erro ao conectar no banco:', err.stack));
