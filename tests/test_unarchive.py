"""Provas isoladas de desarquivamento, sem acesso a bancos reais."""
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from flask import session

os.environ["SECRET_KEY"] = "isolated-unarchive-test-key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TENANT_SUBDOMAINS_ENABLED"] = "false"
from app import app, db, verify_audit_chain
from models import Organizacao, Usuario, Protocolo, HistoricoProtocolo


class UnarchiveTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with app.app_context():
            assert db.engine.url.drivername == "sqlite"
            # Outras suítes podem remover a pasta do SQLite compartilhado.
            database = db.engine.url.database
            if database and database != ':memory:':
                Path(database).parent.mkdir(parents=True, exist_ok=True)
            db.drop_all()
            db.create_all()
            a = Organizacao(nome="Teste A", slug="teste-a")
            b = Organizacao(nome="Teste B", slug="teste-b")
            db.session.add_all([a, b])
            db.session.flush()
            self.tenant, self.other = a.id, b.id
            self.users = {}
            for role in ("admin", "protocolista", "tramitador", "consulta"):
                u = Usuario(tenant_id=a.id, nome=role, login=role, senha="not-a-real-credential", tipo=role)
                db.session.add(u)
                db.session.flush()
                self.users[role] = u.get_id()
            global_admin = Usuario(tenant_id=None, nome="Global", login="global", senha="not-a-real-credential", tipo="admin", is_platform_admin=True)
            db.session.add(global_admin)
            db.session.flush()
            self.users["global"] = global_admin.get_id()
            p = Protocolo(tenant_id=a.id, numero="0001/2026", nome="Fictício", status="ARQUIVADO", arquivado_em=datetime(2026, 1, 1), responsavel="responsavel-preservado")
            foreign = Protocolo(tenant_id=b.id, numero="0001/2026", nome="Outro cliente", status="ARQUIVADO", arquivado_em=datetime(2026, 1, 1))
            db.session.add_all([p, foreign])
            db.session.commit()
            self.pid, self.foreign = p.id, foreign.id
        self.client = app.test_client()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, role):
        with self.client.session_transaction() as s:
            s["_user_id"] = str(self.users[role])
            s["_fresh"] = True
            if role == "global":
                s["active_tenant_id"] = self.tenant

    def post(self, reason="Retomar análise por solicitação do interessado.", pid=None):
        return self.client.post(f"/protocolo/{pid or self.pid}/desarquivar", data={"justificativa": reason})

    def test_admin_reopens_and_audits(self):
        self.login("admin")
        self.assertEqual(self.post().status_code, 302)
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            self.assertIsNone(p.arquivado_em)
            self.assertEqual(p.status, "EM ANÁLISE")
            self.assertEqual(p.numero, "0001/2026")
            self.assertEqual(p.responsavel, "responsavel-preservado")
            events = HistoricoProtocolo.query.filter_by(protocolo_id=p.id, acao="DESARQUIVAMENTO").all()
            self.assertEqual(len(events), 1)
            self.assertIn("Retomar análise", events[0].observacao)
            self.assertTrue(verify_audit_chain(self.tenant)[0])
        self.post()
        with app.app_context():
            self.assertEqual(HistoricoProtocolo.query.filter_by(protocolo_id=self.pid, acao="DESARQUIVAMENTO").count(), 1)

    def test_protocolista_and_legacy_archive(self):
        self.login("protocolista")
        with app.app_context():
            db.session.get(Protocolo, self.pid).arquivado_em = None
            db.session.commit()
        self.assertEqual(self.post().status_code, 302)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, "EM ANÁLISE")

    def test_reopening_clears_current_conclusion_but_preserves_history(self):
        self.login('admin')
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            p.finalizado_em = datetime(2026, 1, 1)
            p.resultado_final = 'Conclusão anterior.'
            db.session.add(HistoricoProtocolo(tenant_id=self.tenant, protocolo_id=self.pid,
                status='CONCLUÍDO', acao='FINALIZACAO', responsavel='admin',
                observacao='Conclusão anterior.'))
            db.session.commit()
        self.assertEqual(self.post().status_code, 302)
        with app.app_context():
            p = db.session.get(Protocolo, self.pid)
            self.assertIsNone(p.finalizado_em)
            self.assertIsNone(p.resultado_final)
            self.assertEqual(HistoricoProtocolo.query.filter_by(protocolo_id=self.pid,
                acao='FINALIZACAO').one().observacao, 'Conclusão anterior.')
            self.assertTrue(verify_audit_chain(self.tenant)[0])

    def test_global_admin_with_selected_client(self):
        self.login("global")
        self.assertEqual(self.post().status_code, 302)
        with app.app_context():
            self.assertIsNone(db.session.get(Protocolo, self.pid).arquivado_em)

    def test_other_roles_cannot_reopen(self):
        for role in ("consulta", "tramitador"):
            self.login(role)
            self.assertIn(self.post().status_code, (302, 403))
            with app.app_context():
                self.assertEqual(db.session.get(Protocolo, self.pid).status, "ARQUIVADO")

    def test_other_tenant_is_not_found(self):
        self.login("admin")
        self.assertEqual(self.post(pid=self.foreign).status_code, 404)
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.foreign).status, "ARQUIVADO")

    def test_reason_and_post_required(self):
        self.login("admin")
        for reason in ("", "   ", "x" * 2001):
            self.assertEqual(self.post(reason).status_code, 302)
            with app.app_context():
                self.assertEqual(db.session.get(Protocolo, self.pid).status, "ARQUIVADO")
        self.assertEqual(self.client.get(f"/protocolo/{self.pid}/desarquivar").status_code, 405)


    def test_anonymous_and_global_without_client_cannot_reopen(self):
        self.assertEqual(self.post().status_code, 302)
        self.login("global")
        with self.client.session_transaction() as s:
            s.pop("active_tenant_id", None)
        response = self.post()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/plataforma", response.headers["Location"])
        with app.app_context():
            self.assertEqual(db.session.get(Protocolo, self.pid).status, "ARQUIVADO")

    def test_csrf_required(self):
        self.login("admin")
        app.config["WTF_CSRF_ENABLED"] = True
        try:
            self.assertEqual(self.post().status_code, 400)
            with app.app_context():
                self.assertEqual(db.session.get(Protocolo, self.pid).status, "ARQUIVADO")
        finally:
            app.config["WTF_CSRF_ENABLED"] = False

    def test_form_visible_only_when_permitted_and_archived(self):
        for role in ("admin", "protocolista"):
            self.login(role)
            html = self.client.get(f"/protocolo/{self.pid}").get_data(as_text=True)
            self.assertIn(f'/protocolo/{self.pid}/desarquivar', html)
            self.assertIn('name="justificativa"', html)
        self.post()
        html = self.client.get(f"/protocolo/{self.pid}").get_data(as_text=True)
        self.assertNotIn(f'/protocolo/{self.pid}/desarquivar', html)
        self.login("consulta")
        html = self.client.get(f"/protocolo/{self.pid}").get_data(as_text=True)
        self.assertNotIn(f'/protocolo/{self.pid}/desarquivar', html)


if __name__ == "__main__":
    unittest.main()

