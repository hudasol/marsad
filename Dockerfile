# Marsad service + dashboard + MCP. Build: docker build -t marsad .   Run: docker run -p 8000:8000 marsad
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[sim,api,mcp,adapters]"
EXPOSE 8000
USER nobody
# Advisory service; set MARSAD_API_KEY to require a key.
CMD ["marsad", "serve", "--host", "0.0.0.0", "--port", "8000"]
