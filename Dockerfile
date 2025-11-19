# Use the official Playwright image with matching version
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright (same version as image)
RUN pip install playwright==1.46.0

# Install browsers
RUN playwright install chromium firefox webkit

# Expose the port
EXPOSE 10000

ENV PORT=10000

# Start the Flask app using Gunicorn
CMD gunicorn --workers=2 --timeout=300 --bind 0.0.0.0:$PORT main:app


