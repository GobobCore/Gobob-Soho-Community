FROM python:3.12-slim
WORKDIR /srv
# app/ 是纯静态 + serve.py 反代，无构建步骤
COPY app/ ./
EXPOSE 19003
ENV SOHO_BACKEND=http://backend:19001
CMD ["python3", "serve.py"]
