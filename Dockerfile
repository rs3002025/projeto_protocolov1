# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Install system dependencies for WeasyPrint and set locale
RUN apt-get update && apt-get install -y \
    locales \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libpangocairo-1.0-0 \
    fonts-liberation \
    libffi-dev \
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
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Atualiza o esquema de forma idempotente antes de iniciar cada implantação.
CMD ["sh", "-c", "python bootstrap_db.py && gunicorn --bind 0.0.0.0:${PORT:-8080} --workers ${WEB_CONCURRENCY:-2} --timeout 60 app:app"]
