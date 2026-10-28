# Marsad service + dashboard + MCP. Build: docker build -t marsad .   Run: docker run -p 8000:8000 -e MARSAD_API_KEY=changeme marsad
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[sim,api,mcp,adapters]"
EXPOSE 8000
USER nobody
# The service refuses to bind 0.0.0.0 without a key: docker run -p 8000:8000 -e MARSAD_API_KEY=... marsad
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/v1/health', timeout=2)"
CMD ["marsad", "serve", "--host", "0.0.0.0", "--port", "8000"]
