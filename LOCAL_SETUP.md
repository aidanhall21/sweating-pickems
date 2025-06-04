# Local Development Setup

## 🚀 Quick Start

Your application is now running! Here's how to set it up and access it:

### 1. Application URL
**Your app is running at: http://localhost:8000**

### 2. Required Services Status
✅ **PHP 8.4.6** - Running on localhost:8000  
✅ **Redis Server** - Running (required for caching)  
✅ **Python 3.11.3** - Available for simulations  
✅ **Composer Dependencies** - Installed (Stripe, JWT)  

### 3. Important Notes

#### Firebase Authentication
- Your Google login should work as-is since it's configured for your domain
- If you get authentication errors, you may need to add `localhost:8000` to your Firebase allowed origins

#### Stripe Configuration
- Currently using **test mode** keys
- Webhook endpoint will need to be updated for local testing (use ngrok - see below)

#### File Uploads
- Upload directory: `/uploads/` (created with proper permissions)
- Log directory: `/logs/` (created for error logging)

### 4. Testing Stripe Locally (Optional)

If you want to test Stripe subscriptions locally:

```bash
# Install ngrok (if not installed)
brew install ngrok

# In a new terminal, expose your local server
ngrok http 8000

# Copy the https URL (e.g., https://abc123.ngrok.io)
# Update your Stripe webhook endpoint to: https://abc123.ngrok.io/stripe_webhook.php
```

### 5. Common Commands

#### Start/Stop Services
```bash
# Start Redis (if not running)
redis-server --daemonize yes

# Check Redis is running
redis-cli ping

# Stop Redis
redis-cli shutdown

# Start PHP server (if you need to restart)
php -S localhost:8000
```

#### View Logs
```bash
# PHP error logs
tail -f logs/error.log

# Python simulation logs  
tail -f python_simulation.log
```

#### File Permissions (if needed)
```bash
chmod 755 uploads logs
chmod 644 *.php
```

### 6. Development Workflow

1. **Access the app**: http://localhost:8000
2. **Sign in with Google** (should work with your existing Firebase config)
3. **Test file uploads** with the template CSV files
4. **Test simulations** (they'll run via Python scripts)
5. **Test Stripe** (use test cards from Stripe docs)

### 7. Project Structure

```
pickem-sweats/
├── index.php              # Home page
├── upload.php             # File upload & simulation
├── subscription.php       # Stripe subscription page
├── props.php              # View props
├── header.php             # Navigation
├── config.php             # Configuration
├── subscription_helper.php # Stripe integration
├── stripe_webhook.php     # Webhook handler
├── check_subscription.php # Subscription status API
├── python/                # Simulation scripts
├── uploads/               # User uploaded files
├── logs/                  # Error logs
├── css/                   # Stylesheets
└── vendor/                # Composer dependencies
```

### 8. Environment URLs

- **Local Development**: http://localhost:8000
- **Firebase Project**: sweating-pickems.firebaseapp.com
- **Stripe Dashboard**: https://dashboard.stripe.com/test (test mode)

### 9. Troubleshooting

#### Can't access the site?
- Make sure PHP server is running: `php -S localhost:8000`
- Check if port 8000 is available

#### Redis errors?
- Start Redis: `redis-server --daemonize yes`
- Check connection: `redis-cli ping`

#### Upload errors?
- Check file permissions: `ls -la uploads logs`
- Check error logs: `tail logs/error.log`

#### Python simulation errors?
- Check Python packages: `pip3 list | grep -E "(pandas|numpy|redis)"`
- Check Python logs: `tail python_simulation.log`

#### Stripe errors?
- Verify your test keys in `config.php`
- Use Stripe test cards: `4242424242424242`

### 10. Production Deployment

When ready to deploy:
1. Update `config.php` with production Redis credentials
2. Set up proper web server (Apache/Nginx)
3. Configure SSL certificates
4. Update Stripe to live mode
5. Set up proper domain for Firebase auth
6. Configure production webhook endpoints

---

## 🎉 You're Ready to Go!

Open http://localhost:8000 in your browser and start testing your application! 