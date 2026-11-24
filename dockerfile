FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends apache2 apache2-dev gcc make curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web_service.py app.wsgi ./
COPY apache.conf /etc/apache2/sites-available/video_service.conf

RUN mod_wsgi-express module-config > /etc/apache2/mods-available/wsgi.load \
    && a2enmod wsgi \
    && a2dissite 000-default \
    && a2ensite video_service \
    && ln -sf /dev/stdout /var/log/apache2/access.log \
    && ln -sf /dev/stderr /var/log/apache2/error.log \
    && mkdir -p /app/uploads /var/run/apache2 /var/lock/apache2 \
    && chown -R www-data:www-data /app/uploads

EXPOSE 80

CMD ["/bin/bash", "-c", "source /etc/apache2/envvars && rm -f \"$APACHE_PID_FILE\" && exec apache2 -D FOREGROUND"]