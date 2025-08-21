
FROM python:3.12-slim

RUN apt-get -q -y update \
    && apt-get install -y gcc \
    && apt-get install -y curl \
    && apt-get install -y vim \
    && apt-get install -y postgresql-client \
    && DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y postfix && \
    apt-get update && apt-get install -y sudo  && \
    apt-get install -y telnet


ENV USERNAME=ts-app
ENV WORKING_DIR=/home/ts-app
ENV POSTFIX_START_CMD="/usr/sbin/service postfix start"
ENV POSTFIX_COPY_RESOLV_CMD="/bin/cp /etc/resolv.conf /var/spool/postfix/etc/resolv.conf"


WORKDIR ${WORKING_DIR}

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .


RUN groupadd ${USERNAME} && \
    useradd -g ${USERNAME} ${USERNAME}


RUN chown -R ${USERNAME}:www-data ${WORKING_DIR} \
    && chmod -R u=rwx,g=rwx ${WORKING_DIR}


RUN echo ${USERNAME}' ALL=(ALL) NOPASSWD: '${POSTFIX_START_CMD} >> /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}

RUN echo ${USERNAME}' ALL=(ALL) NOPASSWD: '${POSTFIX_COPY_RESOLV_CMD} >> /etc/sudoers.d/${USERNAME} && \
    chmod 0440 /etc/sudoers.d/${USERNAME}


USER ${USERNAME}
ENV PATH "$PATH:/home/${USERNAME}/.local/bin"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 


EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "user_service.wsgi:application"]

