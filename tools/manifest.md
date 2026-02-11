# Tools Manifest

Master list of all deterministic tools available in the EmergentCTI platform.

| Tool | Path | Description |
|------|------|-------------|
| Docker Deploy | tools/deploy/docker_deploy.sh | Build and start all Docker Compose services |
| Health Check | tools/deploy/health_check.sh | Verify all 6 services are healthy and responding |
| Run Migrations | tools/db/run_migrations.sh | Execute alembic database migrations |
| Backup DB | tools/db/backup_db.sh | Create PostgreSQL dump backup |
| Run Tests | tools/test/run_tests.sh | Execute full backend + frontend test suite |
| Lint Check | tools/test/lint_check.sh | Run all linters and type checkers |
| Security Scan | tools/security/scan.sh | Run SAST, dependency audit, and container scanning |
| Memory Read | tools/memory/memory_read.py | Load persistent memory at session start |
| Memory Write | tools/memory/memory_write.py | Write to daily logs and memory database |
| Memory DB | tools/memory/memory_db.py | SQLite CRUD for memory entries |
| Memory Search | tools/memory/hybrid_search.py | Search memory with keyword + semantic matching |
| Embed Memory | tools/memory/embed_memory.py | Generate embeddings for memory entries |
| Semantic Search | tools/memory/semantic_search.py | Vector similarity search on memory |
