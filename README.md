# Pickem Sweats

A web application for analyzing and simulating sports betting picks.

## Requirements

- PHP 7.4+
- Python 3.x
- Redis Server
- Apache/Nginx
- Composer
- 1GB+ RAM (for simulations)

## Deployment Instructions

### 1. Create a Digital Ocean Droplet

1. Create a new Ubuntu 22.04 LTS droplet
2. Recommended specs:
   - 2GB RAM
   - 2 vCPUs
   - 50GB SSD

### 2. Initial Server Setup

1. SSH into your droplet
2. Run the deployment script:
   ```bash
   wget https://raw.githubusercontent.com/aidanhall21/sweating-pickems/main/deploy.sh
   chmod +x deploy.sh
   ./deploy.sh
   ```

### 3. Configure the Application

1. Copy the example configuration:
   ```bash
   cp config.php.example config.php
   ```

2. Edit `config.php` with your settings:
   - Set Redis password if needed
   - Adjust memory limits if required
   - Configure other settings as needed

### 4. Set Up Domain (Optional)

1. Point your domain to the droplet's IP address
2. Update the Apache virtual host configuration with your domain
3. Restart Apache:
   ```bash
   sudo systemctl restart apache2
   ```

## Development

### Local Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   composer install
   pip3 install -r requirements.txt
   ```
3. Set up Redis
4. Copy and configure `config.php`

### Running Tests

```bash
php tests/run_tests.php
```

## Security Considerations

1. Set up SSL/TLS for secure connections
2. Configure Redis with a strong password
3. Set appropriate file permissions
4. Regularly update system packages

## Monitoring

- Check Apache logs: `/var/log/apache2/`
- Check application logs: `error.log`
- Monitor Redis: `redis-cli monitor`

## Support

For issues and feature requests, please open an issue on GitHub. 