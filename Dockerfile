# Use an official Python image as a base
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependency file and install the packages
# This is only re-executed when requirements.txt changes, which speeds up the build.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the working directory
COPY . .

# Specify that the container listens on port 8000
EXPOSE 8000

# The command to start the application with Gunicorn
# We use 4 worker processes and bind the server to all network interfaces
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "app:app"]
