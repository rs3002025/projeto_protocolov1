# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the locale to pt_BR.UTF-8
RUN apt-get update && apt-get install -y locales && rm -rf /var/lib/apt/lists/* \
    && echo "pt_BR.UTF-8 UTF-8" >> /etc/locale.gen \
    && locale-gen pt_BR.UTF-8
ENV LANG pt_BR.UTF-8
ENV LANGUAGE pt_BR:pt
ENV LC_ALL pt_BR.UTF-8

WORKDIR /app

COPY requirements.txt .

# --- DEBUGGING STEP 1: Verify the requirements.txt content ---
RUN echo "--- Verifying requirements.txt content ---" && cat /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- DEBUGGING STEP 2: List installed packages ---
RUN echo "--- Listing installed packages after install ---" && pip list

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
