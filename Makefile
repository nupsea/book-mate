.PHONY: up down start build logs

# Include .env file
include .env
export

up:
	docker compose up -d
	@echo "Waiting for Gradio UI to be ready..."
	@timeout=60; \
	while [ $$timeout -gt 0 ]; do \
		if curl -s http://localhost:7860 > /dev/null 2>&1; then \
			echo "All services started! Access UI at http://localhost:7860"; \
			exit 0; \
		fi; \
		sleep 1; \
		timeout=$$((timeout - 1)); \
	done; \
	echo "Warning: UI did not start within 60 seconds. Check logs with: make logs"

build:
	docker compose build

down:
	docker compose down

logs:
	docker compose logs -f app

start: up
	@echo "Book Mate is running at http://localhost:7860"
