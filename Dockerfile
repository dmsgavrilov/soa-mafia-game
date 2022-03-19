FROM python:3.8

COPY ./requirements.txt .
COPY ./server.py .
COPY ./commands.py .
COPY ./proto ./proto

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "server.py"]
