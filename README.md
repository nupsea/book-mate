# book-mate
Upload the contents of a book and seek answers. 



### Setup
Install UV
```
git clone <repository-url>
cd book-mate

cp .env_template .env
# Update .env with your OpenAI API key, PG_USER and PG_PASS


uv pip install -e .

docker compose up -d
# check for running containers
docker ps

```

### Debug
```
psql -h localhost -U bookuser -d booksdb
```

### Initialize DB




