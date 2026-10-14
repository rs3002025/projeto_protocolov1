# Use an official Python runtime as a parent image
FROM python:3.12.15-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1

# Install system dependencies for WeasyPrint and set locale
RUN apt-get update && apt-get install -y \
    locales \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libpangocairo-1.0-0 \
    fonts-liberation \
    libffi-dev \
    postgresql-client \
    && echo "pt_BR.UTF-8 UTF-8" >> /etc/locale.gen \
    && locale-gen pt_BR.UTF-8 \
    && update-locale LANG=pt_BR.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for locale
ENV LANG pt_BR.UTF-8
ENV LANGUAGE pt_BR:pt
ENV LC_ALL pt_BR.UTF-8

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt requirements.lock requirements-hashes.lock ./

# Install Python dependencies
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.1 \
    && python -c "import pip,pathlib,shutil; assert pip.__version__ == '26.2.1'; stale = pathlib.Path(pip.__file__).resolve().parent.parent / 'pip-25.0.1.dist-info'; shutil.rmtree(stale) if stale.is_dir() else None" \
    && python -m pip install --no-cache-dir --require-hashes --only-binary=:all: --no-deps -r requirements-hashes.lock \
    && python -m pip check

# Copy the rest of the application's code
COPY . .

RUN python scripts/verify_runtime.py

# Expose the port the app runs on
EXPOSE 8080

# Atualiza o esquema de forma idempotente antes de iniciar cada implantação.
CMD ["sh", "-c", "python scripts/verify_runtime.py && python bootstrap_db.py && gunicorn --bind 0.0.0.0:${PORT:-8080} --workers ${WEB_CONCURRENCY:-2} --timeout 60 app:app"]


