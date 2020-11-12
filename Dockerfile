FROM python:3-slim

RUN pip install poetry

WORKDIR /src

COPY . /src

RUN poetry build -f wheel \
  && pip install ./dist/actions_fargate-*-py3-none-any.whl

RUN rm -rf /src

ENTRYPOINT ["fargate"]
