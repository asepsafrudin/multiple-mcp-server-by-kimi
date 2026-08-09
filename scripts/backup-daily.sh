#!/bin/bash
mkdir -p ~/mcp-data/backups
DATE=$(date +%Y%m%d_%H%M)
docker exec mcp-pg pg_dump -U aseps mcp > ~/mcp-data/backups/mcp_${DATE}.sql
find ~/mcp-data/backups -name "*.sql" -mtime +7 -delete
