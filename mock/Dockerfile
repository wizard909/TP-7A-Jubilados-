FROM python:3.12-slim
WORKDIR /mock
COPY vendor ./vendor
RUN pip install --no-index --find-links=./vendor "fastapi>=0.115,<1" "uvicorn>=0.30,<1"
COPY mock/main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
