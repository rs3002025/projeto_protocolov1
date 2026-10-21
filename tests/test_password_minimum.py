"""Regressão isolada da política de senha; não acessa banco nem credenciais."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PasswordMinimumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
        functions = [node for node in module.body if isinstance(node, ast.FunctionDef)
                     and node.name in {"_strong_password", "_portal_password_valid"}]
        namespace = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "password-policy", "exec"), namespace)
        cls.admin_valid = staticmethod(namespace["_strong_password"])
        cls.portal_valid = staticmethod(namespace["_portal_password_valid"])

    def test_admin_boundary(self):
        self.assertFalse(self.admin_valid("Exemplo"))
        self.assertTrue(self.admin_valid("Exemplo8"))
        self.assertTrue(self.admin_valid("Exemplo89"))
        self.assertTrue(self.admin_valid("UmaSenhaLonga2026"))

    def test_existing_guards_preserved(self):
        self.assertFalse(self.admin_valid(" Exemplo8"))
        self.assertFalse(self.admin_valid("Exemplo8 "))
        self.assertFalse(self.admin_valid("a" * 129))
        self.assertFalse(self.admin_valid("123456789012"))

    def test_portal_keeps_existing_composition(self):
        self.assertTrue(self.portal_valid("Exemplo8"))
        self.assertFalse(self.portal_valid("Exempl8"))
        self.assertFalse(self.portal_valid("exemplo8"))
        self.assertFalse(self.portal_valid("EXEMPLO8"))
        self.assertFalse(self.portal_valid("Exemplos"))

    def test_all_creation_forms_use_eight(self):
        module = ast.parse((ROOT / "forms.py").read_text(encoding="utf-8"))
        seen = set()
        for node in module.body:
            if isinstance(node, ast.ClassDef) and node.name in {
                    "RegistrationForm", "AdminUserCreationForm", "PlatformAdminCreationForm"}:
                for field in node.body:
                    if (isinstance(field, ast.Assign)
                            and any(isinstance(target, ast.Name) and target.id == "senha"
                                    for target in field.targets)):
                        mins = [kw.value.value for call in ast.walk(field)
                                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                                and call.func.id == "Length" for kw in call.keywords
                                if kw.arg == "min"]
                        self.assertEqual(mins, [8])
                        seen.add(node.name)
        self.assertEqual(len(seen), 3)

    def test_initial_password_screen_matches_backend(self):
        html = (ROOT / "templates/trocar_senha_inicial.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('minlength="8"'), 2)
        self.assertIn("pelo menos 8 caracteres", html)
        self.assertNotIn("12 caracteres", html)


if __name__ == "__main__":
    unittest.main()
