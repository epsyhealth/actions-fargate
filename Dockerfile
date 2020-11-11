FROM python:3-slim

RUN pip install poetry

RUN poetry install
