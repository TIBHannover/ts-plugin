
FROM python:3.12-slim

RUN apt-get -q -y update \
    && apt-get install -y gcc \
    && apt-get install -y curl \
    && apt-get install -y vim \
    && apt-get install -y postgresql-client \
    && apt-get install -y telnet


ENV USERNAME=ts-app
ENV WORKING_DIR=/home/ts-app


WORKDIR ${WORKING_DIR}

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .


RUN groupadd ${USERNAME} && \
    useradd -g ${USERNAME} ${USERNAME}


RUN chown -R ${USERNAME}:www-data ${WORKING_DIR} \
    && chmod -R u=rwx,g=rwx ${WORKING_DIR}


USER ${USERNAME}
ENV PATH "$PATH:/home/${USERNAME}/.local/bin"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["uvicorn", "user_service.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "3"]
