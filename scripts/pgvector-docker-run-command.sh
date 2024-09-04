docker run -d \
  --name pgvector \
  -p 5432:5432 \
  --env-file .env \
  --expose 5432 \
  pgvector/pgvector:pg16