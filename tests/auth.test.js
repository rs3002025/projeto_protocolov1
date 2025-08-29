const request = require('supertest');
const app = require('../server'); // Precisamos exportar o app de server.js
const pool = require('../db');
const bcrypt = require('bcrypt');

// Silenciar os logs de erro esperados durante os testes
beforeAll(() => {
  jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterAll(async () => {
  // Limpar dados de teste e fechar a conexão com o banco
  await pool.query("DELETE FROM usuarios WHERE login LIKE 'testuser%'");
  pool.end();
  console.error.mockRestore();
});

describe('Auth Endpoints', () => {
  let adminToken;
  let userToken;

  beforeAll(async () => {
    // Criar usuários de teste
    const adminPassword = 'password123';
    const userPassword = 'password456';
    const adminHash = await bcrypt.hash(adminPassword, 10);
    const userHash = await bcrypt.hash(userPassword, 10);

    await pool.query(
      "INSERT INTO usuarios (login, senha, tipo, email, nome, cpf, status) VALUES ('testuseradmin', $1, 'admin', 'admin@test.com', 'Admin Test', '11122233344', 'ativo') ON CONFLICT (login) DO NOTHING",
      [adminHash]
    );
    await pool.query(
      "INSERT INTO usuarios (login, senha, tipo, email, nome, cpf, status) VALUES ('testuserregular', $1, 'user', 'user@test.com', 'User Test', '55566677788', 'ativo') ON CONFLICT (login) DO NOTHING",
      [userHash]
    );
  });

  it('POST /login - should login an admin user and return a token', async () => {
    const res = await request(app)
      .post('/login')
      .send({
        login: 'testuseradmin',
        senha: 'password123',
      });
    expect(res.statusCode).toEqual(200);
    expect(res.body.sucesso).toBe(true);
    expect(res.body).toHaveProperty('token');
    adminToken = res.body.token;
  });

  it('POST /login - should login a regular user and return a token', async () => {
    const res = await request(app)
      .post('/login')
      .send({
        login: 'testuserregular',
        senha: 'password456',
      });
    expect(res.statusCode).toEqual(200);
    expect(res.body.sucesso).toBe(true);
    expect(res.body).toHaveProperty('token');
    userToken = res.body.token;
  });

    it('POST /login - should fail with wrong password', async () => {
    const res = await request(app)
      .post('/login')
      .send({
        login: 'testuseradmin',
        senha: 'wrongpassword',
      });
    expect(res.statusCode).toEqual(401);
    expect(res.body.sucesso).toBe(false);
  });

  it('GET /usuarios - should be forbidden for regular user', async () => {
    const res = await request(app)
      .get('/usuarios')
      .set('Authorization', `Bearer ${userToken}`);
    expect(res.statusCode).toEqual(403);
  });

    it('GET /usuarios - should be forbidden without a token', async () => {
    const res = await request(app).get('/usuarios');
    expect(res.statusCode).toEqual(401);
  });

  it('GET /usuarios - should be successful for admin user', async () => {
    const res = await request(app)
      .get('/usuarios')
      .set('Authorization', `Bearer ${adminToken}`);
    expect(res.statusCode).toEqual(200);
    expect(Array.isArray(res.body.usuarios)).toBe(true);
  });
});
