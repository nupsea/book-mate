.PHONY: up down start

up:
	docker compose up -d
	@echo "Waiting for services to start..."
	@sleep 5

down:
	docker compose down

start: up
	@echo "All services started!"
