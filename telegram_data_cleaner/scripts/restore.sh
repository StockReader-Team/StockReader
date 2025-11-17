#!/bin/bash

# ==============================================
# Database Restore Script
# Telegram Data Cleaner
# ==============================================

set -e

# Configuration
CONTAINER_NAME="${CONTAINER_NAME:-telegram_postgres}"
DB_USER="${DB_USER:-telegram_user}"
DB_NAME="${DB_NAME:-telegram_data}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No backup file specified${NC}"
    echo ""
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Example:"
    echo "  $0 /opt/backups/telegram_data_cleaner/db_20251117_120000.sql.gz"
    echo ""
    exit 1
fi

BACKUP_FILE="$1"

# Validate backup file
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

# Confirmation
echo -e "${YELLOW}==============================================
⚠️  WARNING: DATABASE RESTORE
==============================================${NC}"
echo "This will:"
echo "  1. Drop the existing database"
echo "  2. Create a new database"
echo "  3. Restore from: $BACKUP_FILE"
echo ""
echo "Container: $CONTAINER_NAME"
echo "Database: $DB_NAME"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Restore cancelled.${NC}"
    exit 0
fi

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo -e "${RED}Error: Container $CONTAINER_NAME is not running!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Starting restore...${NC}"

# Drop existing database
echo -e "${YELLOW}Dropping existing database...${NC}"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;"

# Create new database
echo -e "${YELLOW}Creating new database...${NC}"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;"

# Restore from backup
echo -e "${YELLOW}Restoring from backup...${NC}"
if gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"; then
    echo -e "${GREEN}✓ Database restored successfully!${NC}"
else
    echo -e "${RED}✗ Restore failed!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}==============================================
Restore completed successfully!
==============================================
Database: $DB_NAME
Restored from: $BACKUP_FILE
==============================================
${NC}"

exit 0
