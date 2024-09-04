docker network create test
docker run -d --name pgvector --network test -p 5432:5432 --env-file .env --expose 5432 pgvector/pgvector:pg16
docker run -d --name loremaster --network test --env-file .env mantidau/the-loremaster:latest