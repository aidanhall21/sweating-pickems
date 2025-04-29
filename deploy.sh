#!/bin/bash

# Update system packages
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y \
    apache2 \
    php \
    php-redis \
    php-igbinary \
    python3 \
    python3-pip \
    redis-server \
    git \
    composer

# Install Python dependencies
pip3 install requests beautifulsoup4 pandas numpy

# Configure Redis
sudo sed -i 's/supervised no/supervised systemd/' /etc/redis/redis.conf
sudo systemctl restart redis

# Configure Apache
sudo a2enmod rewrite
sudo a2enmod php

# Create application directory
sudo mkdir -p /var/www/pickem-sweats
sudo chown -R $USER:$USER /var/www/pickem-sweats

# Clone the repository
cd /var/www/pickem-sweats
git clone https://github.com/aidanhall21/sweating-pickems.git .

# Set up Apache virtual host
sudo tee /etc/apache2/sites-available/pickem-sweats.conf << EOF
<VirtualHost *:80>
    ServerName pickem-sweats.com
    ServerAdmin webmaster@localhost
    DocumentRoot /var/www/pickem-sweats

    <Directory /var/www/pickem-sweats>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog \${APACHE_LOG_DIR}/error.log
    CustomLog \${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
EOF

# Enable the site and restart Apache
sudo a2ensite pickem-sweats.conf
sudo systemctl restart apache2

# Set up uploads directory
mkdir -p uploads
chmod 755 uploads

# Set up data directory
mkdir -p data
chmod 755 data

# Create config.php from template if it doesn't exist
if [ ! -f config.php ]; then
    cp config.php.example config.php
fi

echo "Deployment completed! Please configure your config.php file with the appropriate settings." 