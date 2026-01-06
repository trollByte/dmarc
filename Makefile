.PHONY: help up down build logs test clean

help:
	@echo "DMARC Report Processor - Available Commands:"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make build    - Rebuild containers"
	@echo "  make logs     - View logs"
	@echo "  make test     - Run tests"
	@echo "  make clean    - Remove containers and volumes"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose up --build -d

logs:
	docker compose logs -f

test:
	docker compose exec backend pytest -v

clean:
	docker compose down -v
