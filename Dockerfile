FROM ubuntu:latest

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

RUN apt-get update \
 && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python-dev \
    python3-pip \
 && rm -rf /var/lib/apt/lists/* \
 && pip3 --no-cache-dir install \
    gunicorn \
    pipenv

WORKDIR /usr/src/app
COPY Pipfile .
COPY Pipfile.lock .
RUN pipenv install --system --deploy

COPY . .

EXPOSE 8000
CMD ["/usr/local/bin/gunicorn", "-b", "0.0.0.0:8000", "--workers", "8", "--access-logfile", "-", "wsgi_server:app"]
