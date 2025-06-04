# Production Deployment Guide for Digital Ocean

## 📋 Pre-Deployment Checklist

### 1. Server Requirements
- ✅ PHP 8.0+
- ✅ Redis server
- ✅ Composer (for PHP dependencies)
- ✅ Python 3.8+ (for simulations)
- ✅ SSL certificate (for HTTPS - required by Stripe)

### 2. Dependencies to Install on Server

```bash
# PHP extensions required
sudo apt-get install php-redis php-curl php-json php-mbstring

# Install Composer dependencies
cd /var/www/pickem-sweats
composer install --no-dev --optimize-autoloader

# Install Python dependencies
pip3 install -r python/requirements.txt
```

### 3. Configuration Updates Needed

#### A. Update Stripe Webhook Endpoint
In your Stripe dashboard, update the webhook endpoint from:
- `http://localhost:8000/stripe_webhook.php`
To:
- `https://yourdomain.com/stripe_webhook.php`

#### B. Update Google OAuth Settings
In your Firebase/Google Console, add your production domain to:
- Authorized JavaScript origins: `https://yourdomain.com`
- Authorized redirect URIs: `https://yourdomain.com`

#### C. Redis Configuration
Ensure Redis is running and accessible:
```bash
# Check Redis status
sudo systemctl status redis

# If not running, start it
sudo systemctl start redis
sudo systemctl enable redis
```

#### D. File Permissions
```bash
# Run the permissions script after deployment
chmod +x fix_permissions.sh
./fix_permissions.sh
```

### 4. Environment-Specific Settings

The code is already configured to:
- ✅ Use HTTPS in production automatically
- ✅ Use secure cookies in production
- ✅ Handle Redis authentication properly
- ✅ Log errors to files instead of displaying them

### 5. Directory Structure Check
Ensure these directories exist with proper permissions:
```
/var/www/pickem-sweats/
├── uploads/ (777)
├── logs/ (777)
├── data/ (755)
└── vendor/ (755)
```

## 🚀 Deployment Steps

### 1. Deploy Code
```bash
# From your local machine
./deploy.sh
```

### 2. SSH into your droplet and run setup
```bash
ssh aidan@204.48.30.46
cd /var/www/pickem-sweats

# Install PHP dependencies
composer install --no-dev --optimize-autoloader

# Set permissions
chmod +x fix_permissions.sh
./fix_permissions.sh

# Create required directories
mkdir -p logs uploads data
chmod 777 logs uploads
chmod 755 data

# Test Redis connection
redis-cli ping
```

### 3. Update Webhook URLs in Stripe Dashboard

1. Log into Stripe Dashboard
2. Go to Developers > Webhooks
3. Update endpoint URL to: `https://yourdomain.com/stripe_webhook.php`
4. Ensure these events are selected:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`

### 4. Test Critical Functions

```bash
# Test file upload permissions
curl -X POST https://yourdomain.com/upload.php

# Test authentication
curl https://yourdomain.com/verify_login.php

# Test subscription page
curl https://yourdomain.com/subscription.php

# Test webhook (will return 405 Method Not Allowed, which is expected)
curl https://yourdomain.com/stripe_webhook.php
```

## 🔧 Configuration Notes

### Current Settings:
- **Stripe**: Test mode (keys start with `sk_test_` and `pk_test_`)
- **Weekly Price**: $9.97/week
- **Free Limit**: 250 simulations
- **Premium Limit**: 10,000 simulations
- **Redis Password**: Set in config.php

### For Production (Live Stripe):
1. Replace test keys with live keys in `config.php`
2. Update webhook secret with live webhook secret
3. Test with real payment methods

## 🐛 Troubleshooting

### Common Issues:

1. **Blank subscription page**: Check session persistence and HTTPS
2. **Redis connection errors**: Verify Redis is running and password is correct
3. **Stripe webhook failures**: Check webhook URL and secret
4. **Permission errors**: Run `./fix_permissions.sh`
5. **Authentication issues**: Verify Google OAuth settings for production domain

### Log Files:
- **PHP Errors**: `/var/www/pickem-sweats/logs/error.log`
- **Stripe Webhooks**: Check webhook attempts in Stripe dashboard
- **Redis**: `redis-cli monitor` to see Redis operations

## 📞 Support

If you encounter issues:
1. Check the log files first
2. Verify all dependencies are installed
3. Ensure SSL certificate is working
4. Test each component individually

The system is now ready for production deployment! 🎉 