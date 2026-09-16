FROM python:3.12-slim
WORKDIR /srv
# R-Refactor 2026-09-16: app 路径变成 community/app (Vue3 静态 + serve.py 反代)
COPY community/app/ ./
EXPOSE 19013
ENV SOHO_BACKEND=http://backend:19011
CMD ["python3", "serve.py"]
