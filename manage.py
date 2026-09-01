"""Comandos administrativos executados no console do Railway."""
import argparse
import os

from app import app, bcrypt, db
from models import Organizacao, Usuario


def create_organization(args):
    password = os.getenv('ADMIN_PASSWORD')
    if not password or len(password) < 8:
        raise SystemExit('Defina ADMIN_PASSWORD com pelo menos 8 caracteres apenas durante a execução do comando.')

    with app.app_context():
        slug = args.slug.strip().lower()
        if Organizacao.query.filter_by(slug=slug).first():
            raise SystemExit(f'A organização {slug!r} já existe.')
        organization = Organizacao(nome=args.name.strip(), slug=slug, ativo=True)
        db.session.add(organization)
        db.session.flush()
        admin = Usuario(
            tenant_id=organization.id,
            nome=args.admin_name.split()[0],
            nome_completo=args.admin_name,
            login=args.admin_login,
            email=args.admin_email,
            senha=bcrypt.generate_password_hash(password).decode('utf-8'),
            tipo='admin',
            status='ativo',
        )
        db.session.add(admin)
        db.session.commit()
        print(f'Organização {slug!r} e administrador criados com sucesso.')


parser = argparse.ArgumentParser()
subcommands = parser.add_subparsers(required=True)
create = subcommands.add_parser('create-organization')
create.add_argument('--slug', required=True)
create.add_argument('--name', required=True)
create.add_argument('--admin-login', required=True)
create.add_argument('--admin-name', required=True)
create.add_argument('--admin-email')
create.set_defaults(handler=create_organization)

arguments = parser.parse_args()
arguments.handler(arguments)
