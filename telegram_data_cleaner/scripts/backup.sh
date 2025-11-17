#!/bin/bash

# ==============================================
# Automatic Backup Script
# Telegram Data Cleaner
# ==============================================

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/telegram_data_cleaner}"
CONTAINER_NAME="${CONTAINER_NAME:-telegram_postgres}"
DB_USER="${DB_USER:-telegram_user}"
DB_NAME="${DB_NAME:-telegram_data}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="db_${DATE}.sql.gz"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}Starting backup...${NC}"
echo "Date: $(date)"
echo "Backup directory: $BACKUP_DIR"
echo "Container: $CONTAINER_NAME"
echo "Database: $DB_NAME"
echo ""

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo -e "${RED}Error: Container $CONTAINER_NAME is not running!${NC}"
    exit 1
fi

# Perform backup
echo -e "${YELLOW}Dumping database...${NC}"
if docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/$BACKUP_FILE"; then
    echo -e "${GREEN}✓ Database backup created: $BACKUP_FILE${NC}"

    # Get file size
    SIZE=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    echo "  Size: $SIZE"
else
    echo -e "${RED}✗ Backup failed!${NC}"
    exit 1
fi

# Remove old backups
echo ""
echo -e "${YELLOW}Cleaning old backups (older than $RETENTION_DAYS days)...${NC}"
DELETED=$(find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo -e "${GREEN}✓ Removed $DELETED old backup(s)${NC}"

# List current backups
echo ""
echo -e "${YELLOW}Current backups:${NC}"
ls -lh "$BACKUP_DIR"/db_*.sql.gz | tail -5

# Summary
echo ""
echo -e "${GREEN}==============================================
Backup completed successfully!
==============================================
File: $BACKUP_DIR/$BACKUP_FILE
Size: $SIZE
Total backups: $(ls -1 "$BACKUP_DIR"/db_*.sql.gz 2>/dev/null | wc -l)
==============================================
${NC}"

exit 0
