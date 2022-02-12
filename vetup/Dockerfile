FROM python:3.10.2-slim-bullseye

WORKDIR /usr/src/flask_app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
COPY . /usr/src/flask_app


