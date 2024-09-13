docker network create test
docker run -d --name pgvector --network test -p 5432:5432 --env-file .env --expose 5432 pgvector/pgvector:pg16
docker run -d --name loremaster --network test --env-file .env mantidau/the-loremaster:latest

python notion-extractor/load.py notion pgvector -v -i

curl -X POST 'https://api.notion.com/v1/databases/90181605ef4643da927ff2fca3298baa/query' \
  -H 'Authorization: Bearer '"$NOTION_API_KEY"'' \
  -H 'Notion-Version: 2022-06-28' \
  -H "Content-Type: application/json" \
--data '{
  "filter": {
    "property": "Tags",
    "multi_select": {
        "contains": "TestTag"
    }
  }
}'