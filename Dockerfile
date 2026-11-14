FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home mentor && mkdir /data && chown mentor:mentor /data
COPY --chown=mentor:mentor app.py mentor_core.py mentor_auth.py auth_ui.py core.py questions.json chapters.json variants.json chapter_tests.json ./
COPY --chown=mentor:mentor .streamlit .streamlit
USER mentor
ENV MENTOR_DB=/data/mentor.db
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
