docker run -d \
  --name pgvector \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_HOST=localhost \
  -e POSTGRES_DB=pgvector \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_EXTENSIONS=pgvector \
  pgvector/pgvector:pg16