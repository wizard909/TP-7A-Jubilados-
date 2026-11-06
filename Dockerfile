FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
COPY vendor ./vendor
RUN pip install --no-index --find-links=./vendor -r requirements.txt
COPY app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
