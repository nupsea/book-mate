.PHONY: up down start build logs

up:
	docker compose up -d
	@echo "All services started! Access UI at http://localhost:7860"

build:
	docker compose build

down:
	docker compose down

logs:
	docker compose logs -f app

start: up
	@echo "Book Mate is running at http://localhost:7860"
