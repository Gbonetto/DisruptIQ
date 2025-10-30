.PHONY: help install start stop restart logs clean test

help:
	@echo "DisruptIQ - Makefile Commands"
	@echo ""
	@echo "  make install    - Install dependencies and setup"
	@echo "  make start      - Start all services with Docker Compose"
	@echo "  make stop       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs from all services"
	@echo "  make clean      - Clean up containers and volumes"
	@echo "  make test       - Run tests"
	@echo "  make backend    - Start only backend services"
	@echo "  make frontend   - Start only frontend"

install:
	@echo "Installing DisruptIQ..."
	@cp .env.example .env
	@echo "✓ Created .env file (please configure your API keys)"
	@cd backend && pip install -r requirements.txt
	@cd frontend && npm install
	@echo "✓ Dependencies installed"
	@echo ""
	@echo "Next steps:"
	@echo "1. Edit .env and add your API keys"
	@echo "2. Run 'make start' to launch the application"

start:
	@echo "Starting DisruptIQ..."
	docker-compose up -d
	@echo "✓ DisruptIQ is running!"
	@echo ""
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend API: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/api/docs"

stop:
	@echo "Stopping DisruptIQ..."
	docker-compose down
	@echo "✓ DisruptIQ stopped"

restart:
	@echo "Restarting DisruptIQ..."
	docker-compose restart
	@echo "✓ DisruptIQ restarted"

logs:
	docker-compose logs -f

backend:
	docker-compose up -d postgres redis qdrant backend
	@echo "✓ Backend services started"

frontend:
	cd frontend && npm run dev

clean:
	@echo "Cleaning up..."
	docker-compose down -v
	@echo "✓ Containers and volumes removed"

test:
	@echo "Running tests..."
	cd backend && pytest
	@echo "✓ Tests completed"

db-migrate:
	docker-compose exec backend alembic upgrade head

db-reset:
	docker-compose down -v postgres
	docker-compose up -d postgres
	@echo "✓ Database reset"
