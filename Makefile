.PHONY: up down start

up:
	docker compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	uv run python -m src.ui.app

down:
	docker compose down

start: up
	@echo "All services started!"
