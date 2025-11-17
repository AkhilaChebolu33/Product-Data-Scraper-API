# Use the official Playwright image with Python and all dependencies
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port your app runs on
EXPOSE 10000

# Set default environment variable for PORT if not provided
ENV PORT=10000

# Start the Flask app using Gunicorn with extended timeout
CMD ["gunicorn", "--workers=1", "--timeout=300", "--bind", "0.0.0.0:10000", "main:app"]


