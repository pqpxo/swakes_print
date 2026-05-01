FROM arm32v6/debian:bullseye

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libusb-1.0-0-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN pip3 install --no-cache-dir --upgrade pip

RUN pip3 install --no-cache-dir \
    Pillow==9.5.0 \
    brother_ql \
    flask \
    qrcode \
    requests

EXPOSE 5000

CMD ["python3", "app.py"]
