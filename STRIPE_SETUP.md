# Stripe Subscription Setup Guide

This guide will help you set up Stripe subscription payments for your Sweating Pickems application.

## 1. Create Stripe Account

1. Go to [https://stripe.com](https://stripe.com) and create an account
2. Complete your account verification
3. Switch to **Test mode** for development

## 2. Get API Keys

1. In your Stripe Dashboard, go to **Developers** > **API keys**
2. Copy your **Publishable key** and **Secret key**
3. Update `config.php` with your keys:

```php
// Stripe configuration
define('STRIPE_SECRET_KEY', 'sk_test_your_secret_key_here');
define('STRIPE_PUBLISHABLE_KEY', 'pk_test_your_publishable_key_here');
```

## 3. Create Product and Price

### Weekly Subscription
1. Go to **Products** in your Stripe Dashboard
2. Click **Create product**
3. Set:
   - **Name**: "Premium Weekly"
   - **Description**: "Weekly premium subscription for unlimited simulations"
   - **Price**: $2.97 USD
   - **Billing period**: Weekly
   - **Recurring**: Yes
4. Copy the **Price ID** (starts with `price_`)

## 4. Update Price ID

In `subscription.php`, replace the placeholder price ID:

```php
// Line ~27
'price_1RWJVWQSCNdWM7EjvBVl9o7U', // Replace with your weekly price ID
```

## 5. Set Up Webhooks

1. Go to **Developers** > **Webhooks** in Stripe Dashboard
2. Click **Add endpoint**
3. Set:
   - **Endpoint URL**: `https://yourdomain.com/stripe_webhook.php`
   - **Events to send**:
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_succeeded`
     - `invoice.payment_failed`
4. Copy the **Signing secret** (starts with `whsec_`)
5. Update `config.php`:

```php
define('STRIPE_WEBHOOK_SECRET', 'whsec_your_webhook_secret_here');
```

## 6. Configure Customer Portal

1. Go to **Settings** > **Billing** > **Customer portal**
2. Enable the customer portal
3. Configure:
   - **Allow customers to**: Update payment methods, View billing history, Download invoices
   - **Business information**: Add your business details
   - **Cancellation**: Allow customers to cancel subscriptions

## 7. Test the Integration

### Test Cards
Use these test card numbers in development:

- **Successful payment**: `4242424242424242`
- **Payment requires authentication**: `4000002500003155`
- **Payment is declined**: `4000000000000002`

### Test Flow
1. Sign in with Google
2. Go to the Subscription page
3. Try subscribing with a test card
4. Verify the subscription appears in your Stripe Dashboard
5. Test the customer portal functionality
6. Test webhooks by viewing the webhook logs in Stripe

## 8. Go Live

When ready for production:

1. Switch your Stripe account to **Live mode**
2. Get your live API keys
3. Update `config.php` with live keys
4. Update webhook endpoint to point to your live domain
5. Test with real payment methods

## 9. Security Considerations

- Keep your secret keys secure and never commit them to version control
- Use environment variables or a secure config file for production
- Regularly rotate your API keys
- Monitor webhook deliveries for failures
- Set up proper logging for payment events

## 10. Monitoring

- Monitor your Stripe Dashboard for failed payments
- Set up email notifications for important events
- Consider implementing retry logic for failed webhook deliveries
- Monitor subscription metrics and churn rates

## Support

If you encounter issues:
- Check Stripe Dashboard logs
- Review webhook delivery attempts
- Use Stripe's test mode for debugging
- Contact Stripe support if needed

Remember to update the price constant in `config.php` if you change your pricing:

```php
define('PREMIUM_PRICE_WEEKLY', 297); // $2.97 in cents per week
```

## Why Weekly Billing?

Weekly billing offers several advantages:
- **Lower commitment barrier** - Users can try premium features without a large upfront cost
- **Flexible for seasonal users** - Perfect for users who only need premium during active betting periods
- **Higher conversion rates** - Lower psychological barrier to entry
- **Better cash flow** - More frequent payments vs. monthly billing
- **Easy to scale pricing** - Can adjust weekly rates more dynamically than monthly/yearly plans 