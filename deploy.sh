#!/bin/bash

# Configuration
DROPLET_USER="aidan"
DROPLET_IP="204.48.30.46"
DROPLET_PATH="/var/www/pickem-sweats"
LOCAL_PATH="."

# Upload files with rsync
echo "Uploading files to $DROPLET_USER@$DROPLET_IP:$DROPLET_PATH..."
rsync -avz \
    --exclude '.git' \
    --exclude '.DS_Store' \
    --exclude 'node_modules' \
    --exclude 'venv' \
    --exclude 'data' \
    --exclude 'logs' \
    --exclude 'uploads' \
    --exclude 'deploy.sh' \
    --exclude 'fix_permissions.sh' \
    "$LOCAL_PATH/" \
    "$DROPLET_USER@$DROPLET_IP:$DROPLET_PATH/"

# Check if everything worked
if [ $? -eq 0 ]; then
    echo "Deployment successful!"
else
    echo "Deployment failed."
    exit 1
fi 