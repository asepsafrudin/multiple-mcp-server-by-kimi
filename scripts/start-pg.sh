#!/bin/bash
mkdir -p ~/mcp-data/pg
docker run -d --name mcp-pg -e POSTGRES_DB=mcp -e POSTGRES_USER=aseps -e POSTGRES_PASSWORD=secure123 -v ~/mcp-data/pg:/var/lib/postgresql/data -p 5432:5432 ankane/pgvector
