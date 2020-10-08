FROM python:3.8

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y \
        bluez && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/detector

COPY requirements.txt ./
RUN python3 -m pip install -r requirements.txt

COPY ./ ./

CMD ["python3", "./bt.py"]
