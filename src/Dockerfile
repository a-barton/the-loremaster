# Inherit Huggingface transformers-pytorch-gpu image which includes CUDA support
#FROM huggingface/transformers-pytorch-gpu

FROM python:3.10-slim

RUN pip install --upgrade pip
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/

WORKDIR /app/

ENTRYPOINT ["python3", "discord-bot/bot.py"]