FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system -r pyproject.toml
COPY . .
CMD ["python", "main.py"]