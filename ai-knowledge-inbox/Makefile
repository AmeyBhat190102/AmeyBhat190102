.PHONY: install backend frontend test clean

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && python3 -m uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && python3 -m pytest -q

clean:
	rm -rf backend/data backend/.pytest_cache frontend/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
