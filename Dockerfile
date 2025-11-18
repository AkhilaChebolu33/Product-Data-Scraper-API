# Use the official Playwright image with Python and all dependencies
FROM mcr.microsoft.com/playwright/python:latest

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright
RUN pip install playwright==1.56.0

# Install all browsers from playwright (chromium, webkit, firefox)
RUN playwright install

# Install Chromium
RUN playwright install chromium

# Install Chromium
RUN playwright install webkit

# Install Chromium
RUN playwright install firefox


# Expose the port your app runs on
EXPOSE 10000

# Set default environment variable for PORT if not provided
ENV PORT=10000

# Start the Flask app using Gunicorn with extended timeout
CMD gunicorn --workers=2 --timeout=300 --bind 0.0.0.0:$PORT main:app


