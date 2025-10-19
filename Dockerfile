Use the official Python base image

FROM python:3.11-slim

Set the working directory in the container

WORKDIR /usr/src/app

Copy the dependency file and install packages

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

Copy the rest of the application code

COPY . .

Expose the port (Cloud Run sets the PORT environment variable automatically)

We use the standard gunicorn port 8080 as a fallback

EXPOSE 8080

Run gunicorn to start the application when the container launches.

We explicitly bind to the port provided by the environment variable ($PORT)

Flask application instance is named 'app' in 'line_processor_final.py'

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 line_processor_final:app