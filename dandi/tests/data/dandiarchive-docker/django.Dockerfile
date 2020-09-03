FROM python:3.8
# Install system librarires for Python packages:
# * psycopg2
RUN apt-get update && \
    apt-get install --no-install-recommends --yes \
        libpq-dev gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*

#ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN git clone https://github.com/dandi/dandi-publish /opt/django && \
    pip install -e /opt/django

WORKDIR /opt/django
