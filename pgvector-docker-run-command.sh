docker run -d \
  --name pgvector \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_HOST=localhost \
  -e POSTGRES_DB=vectors \
  -e POSTGRES_USER=loremaster \
  -e POSTGRES_EXTENSIONS=pgvector \
  pgvector/pgvector:pg16