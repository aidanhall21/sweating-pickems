#!/bin/bash

# Configuration
DROPLET_USER="aidan"
DROPLET_IP="204.48.30.46"
DROPLET_PATH="/var/www/pickem-sweats"

echo "This script needs sudo access on the server."
read -s -p "Enter your password: " PASSWORD
echo

echo "Connecting to server to fix permissions..."
ssh "$DROPLET_USER@$DROPLET_IP" "echo '$PASSWORD' | sudo -S bash -c '
    # Add your user to the www-data group
    usermod -a -G www-data aidan
    
    # Set the correct ownership and permissions
    chown -R www-data:www-data /var/www/pickem-sweats
    chmod -R 775 /var/www/pickem-sweats
    
    echo \"Permissions fixed! You may need to log out and back in for group changes to take effect.\"
'" 