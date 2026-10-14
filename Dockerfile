FROM python:3.12-slim

# Install system dependencies required by Aspose.CAD on Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdiplus \
    fontconfig \
    libicu-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Render PORT
ENV PORT=5000
EXPOSE 5000

CMD ["python", "app.py"]
