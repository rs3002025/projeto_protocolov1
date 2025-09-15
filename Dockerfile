# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the locale to pt_BR.UTF-8
# This avoids potential encoding issues with filenames or content
RUN apt-get update && apt-get install -y locales && rm -rf /var/lib/apt/lists/* \
    && echo "pt_BR.UTF-8 UTF-8" >> /etc/locale.gen \
    && locale-gen pt_BR.UTF-8 \
    && update-locale LANG=pt_BR.UTF-8
ENV LANG pt_BR.UTF-8
ENV LANGUAGE pt_BR:pt
ENV LC_ALL pt_BR.UTF-8

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code to the working directory
COPY . .

# Expose the port the app runs on
EXPOSE 8080

# Run the application with Gunicorn
# The port is hardcoded to 8080 as per the user's example.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
