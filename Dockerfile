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

# Register bundled OpenSSL 1.1 compatibility libraries
RUN cp lib/lib*.so* /usr/lib/ 2>/dev/null || true && \
    cp lib/lib*.so* /usr/lib/x86_64-linux-gnu/ 2>/dev/null || true && \
    ldconfig 2>/dev/null || true

# Expose Render PORT and configure .NET globalization
ENV PORT=5000
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
ENV COMPlus_GlobalizationInvariant=1
ENV LD_LIBRARY_PATH=/app/lib:$LD_LIBRARY_PATH
EXPOSE 5000

CMD ["python", "app.py"]
