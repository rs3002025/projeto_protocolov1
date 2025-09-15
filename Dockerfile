# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir makes the image smaller
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code to the working directory
COPY . .

# Make port available to the world outside this container
# (Gunicorn will bind to the PORT variable provided by Railway)
EXPOSE 8080

# Define environment variable for the port
ENV PORT 8080

# Run app.py when the container launches
# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
