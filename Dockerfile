FROM python:3.12-slim

# Create non-root user
RUN useradd -m appuser

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 8000

# Start Uvicorn server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]