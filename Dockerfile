FROM python:3.12-slim

# Bibliotecas que WeasyPrint necesita para generar el PDF (HU-21).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 \
       libharfbuzz0b libfontconfig1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# La base SQLite se arma en la imagen con los datos de demostración:
# cada despliegue o reinicio vuelve a dejar los mismos datos de prueba.
RUN python manage.py collectstatic --noinput \
    && python manage.py migrate --noinput \
    && python manage.py seed_demo

ENV DJANGO_DEBUG=0
CMD ["sh", "-c", "gunicorn qa_admin.wsgi --bind 0.0.0.0:${PORT:-8000}"]
