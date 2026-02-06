.PHONY: help up down build logs test test-frontend lint format migrate backup status clean seed

help:
	@echo "DMARC Report Processor - Available Commands:"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make build          - Rebuild containers"
	@echo "  make logs           - View logs"
	@echo "  make test           - Run backend tests"
	@echo "  make test-frontend  - Run frontend tests"
	@echo "  make lint           - Run linters (flake8)"
	@echo "  make format         - Format code (black + isort)"
	@echo "  make migrate        - Run database migrations"
	@echo "  make backup         - Backup database"
	@echo "  make status         - Check service health"
	@echo "  make seed           - Seed database with sample data"
	@echo "  make clean          - Remove containers and volumes"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose up --build -d

logs:
	docker compose logs -f

test:
	docker compose exec backend pytest -v --cov=app

test-frontend:
	docker compose exec nginx sh -c "cd /usr/share/nginx/html && npm test" 2>/dev/null || echo "Run frontend tests locally: cd frontend && npm test"

lint:
	docker compose exec backend flake8 app/ --max-line-length=120 --extend-ignore=E203,W503

format:
	docker compose exec backend black app/ --line-length=120
	docker compose exec backend isort app/ --profile=black --line-length=120

migrate:
	docker compose exec backend alembic upgrade head

backup:
	@mkdir -p backups
	docker compose exec -T db pg_dump -U $${POSTGRES_USER:-dmarc} $${POSTGRES_DB:-dmarc} | gzip > backups/dmarc_$$(date +%Y%m%d_%H%M%S).sql.gz
	@echo "Backup saved to backups/"

status:
	@echo "=== Service Status ==="
	@docker compose ps
	@echo ""
	@echo "=== Health Check ==="
	@curl -sf http://localhost:8000/health && echo " - Backend: OK" || echo " - Backend: UNREACHABLE"
	@curl -sf http://localhost/health && echo " - Nginx:   OK" || echo " - Nginx:   UNREACHABLE"

seed:
	docker compose exec backend python scripts/seed_data.py

clean:
	docker compose down -v
