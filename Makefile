.PHONY: help up down build logs test test-frontend lint format migrate backup restore health seed init-db rotate-secrets clean

help:
	@echo "DMARC Report Processor - Available Commands:"
	@echo ""
	@echo "Service Management:"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make build          - Rebuild containers"
	@echo "  make logs           - View logs"
	@echo "  make status         - Check service health"
	@echo "  make health         - Check API health endpoints"
	@echo "  make clean          - Remove containers and volumes"
	@echo ""
	@echo "Development:"
	@echo "  make test           - Run backend tests"
	@echo "  make test-frontend  - Run frontend tests"
	@echo "  make lint           - Run linters (black, isort, flake8)"
	@echo "  make format         - Format code (black + isort)"
	@echo ""
	@echo "Database:"
	@echo "  make migrate        - Run database migrations"
	@echo "  make backup         - Backup database"
	@echo "  make restore        - Restore database from backup"
	@echo "  make seed           - Seed database with sample data"
	@echo "  make init-db        - Initialize database (migrations + admin user)"
	@echo ""
	@echo "Security:"
	@echo "  make rotate-secrets - Rotate JWT and Redis secrets"

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
	@echo "Running black check..."
	@docker compose exec backend black --check app/ --line-length=120 || true
	@echo ""
	@echo "Running isort check..."
	@docker compose exec backend isort --check app/ --profile=black --line-length=120 || true
	@echo ""
	@echo "Running flake8..."
	@docker compose exec backend flake8 app/ --max-line-length=120 --extend-ignore=E203,W503

format:
	@echo "Formatting with black..."
	docker compose exec backend black app/ --line-length=120
	@echo ""
	@echo "Sorting imports with isort..."
	docker compose exec backend isort app/ --profile=black --line-length=120

migrate:
	docker compose exec backend alembic upgrade head

backup:
	@echo "Creating database backup..."
	@bash scripts/backup/backup.sh

restore:
	@echo "Restoring database from backup..."
	@bash scripts/restore.sh

status:
	@echo "=== Service Status ==="
	@docker compose ps
	@echo ""
	@echo "=== Health Check ==="
	@curl -sf http://localhost:8000/health && echo " - Backend: OK" || echo " - Backend: UNREACHABLE"
	@curl -sf http://localhost/health && echo " - Nginx:   OK" || echo " - Nginx:   UNREACHABLE"

health:
	@echo "Checking API health endpoints..."
	@echo ""
	@echo "Backend health:"
	@curl -sf http://localhost:8000/health | python3 -m json.tool || echo "Backend unreachable"
	@echo ""
	@echo "Database connectivity:"
	@curl -sf http://localhost:8000/health | grep -q "healthy" && echo "  Database: OK" || echo "  Database: ERROR"

seed:
	@echo "Seeding database with sample data..."
	docker compose exec backend python scripts/seed_data.py

init-db:
	@echo "Initializing database..."
	@bash scripts/init-db.sh

rotate-secrets:
	@echo "Rotating secrets..."
	@bash scripts/rotate-secrets.sh

clean:
	@echo "Removing containers and volumes..."
	docker compose down -v
	@echo "Cleanup complete"
