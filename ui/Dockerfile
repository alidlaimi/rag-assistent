# UI-Image: nur Streamlit – spricht ausschliesslich mit der API, braucht kein Modell
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN pip install "streamlit>=1.40" "requests>=2.31" "pandas>=2.0"
COPY ui ./ui

RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8501
CMD ["streamlit", "run", "ui/Chat.py", "--server.address=0.0.0.0", "--server.port=8501", \
     "--browser.gatherUsageStats=false"]
