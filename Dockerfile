FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p worlds logs
EXPOSE 8080
ENV SONDER_OPEN_BROWSER=false
CMD ["python", "main.py"]
