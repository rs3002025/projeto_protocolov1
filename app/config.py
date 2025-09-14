import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-secreta-muito-dificil-de-adivinhar'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # A URL do banco de dados será definida dinamicamente
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:jQxcYjVcLejOYCtPXmPGweRyoQPxQdnt@metro.proxy.rlwy.net:34866/railway'

    # Credenciais do Super Administrador
    SUPER_ADMIN_LOGIN = os.environ.get('SUPER_ADMIN_LOGIN') or 'superadmin'
    SUPER_ADMIN_PASSWORD = os.environ.get('SUPER_ADMIN_PASSWORD') or 'superadmin'
