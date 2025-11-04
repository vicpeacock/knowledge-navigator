#!/bin/bash

# Script to cleanup orphaned Playwright containers created by Docker MCP Gateway
# Run this periodically (e.g., via cron) or manually when needed

echo "🧹 Cleaning up orphaned Playwright containers..."

# Find all containers with docker-mcp labels (Playwright containers)
CONTAINERS=$(docker ps -a --filter "label=docker-mcp-tool-type=mcp" --filter "label=docker-mcp-name=playwright" --format "{{.ID}}")

if [ -z "$CONTAINERS" ]; then
    echo "✅ No Playwright containers found to clean up"
    exit 0
fi

COUNT=0
for CONTAINER_ID in $CONTAINERS; do
    # Check if container is still running
    STATUS=$(docker inspect --format='{{.State.Status}}' $CONTAINER_ID 2>/dev/null)
    
    if [ "$STATUS" = "running" ]; then
        # Stop the container first
        echo "🛑 Stopping container $CONTAINER_ID..."
        docker stop $CONTAINER_ID > /dev/null 2>&1
    fi
    
    # Remove the container
    echo "🗑️  Removing container $CONTAINER_ID..."
    docker rm $CONTAINER_ID > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        COUNT=$((COUNT + 1))
    fi
done

echo "✅ Cleaned up $COUNT Playwright container(s)"

# Optional: Also remove stopped containers older than 1 hour
OLD_CONTAINERS=$(docker ps -a --filter "label=docker-mcp-tool-type=mcp" --filter "label=docker-mcp-name=playwright" --filter "status=exited" --format "{{.ID}} {{.CreatedAt}}")

if [ ! -z "$OLD_CONTAINERS" ]; then
    echo ""
    echo "🧹 Cleaning up old stopped containers..."
    OLD_COUNT=0
    while IFS= read -r line; do
        CONTAINER_ID=$(echo $line | awk '{print $1}')
        # Remove stopped containers
        docker rm $CONTAINER_ID > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            OLD_COUNT=$((OLD_COUNT + 1))
        fi
    done <<< "$OLD_CONTAINERS"
    echo "✅ Cleaned up $OLD_COUNT old stopped container(s)"
fi

echo ""
echo "✨ Cleanup complete!"

