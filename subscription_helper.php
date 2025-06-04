<?php
require_once 'config.php';
require_once 'redis_helper.php';
require_once 'vendor/autoload.php';

use Stripe\Stripe;
use Stripe\Customer;
use Stripe\Subscription;
use Stripe\PaymentMethod;
use Stripe\Price;

class SubscriptionHelper {
    private $redis;
    
    public function __construct() {
        $this->redis = RedisHelper::getInstance();
        Stripe::setApiKey(STRIPE_SECRET_KEY);
    }
    
    /**
     * Get user subscription status from cache or Stripe
     */
    public function getUserSubscription($userId) {
        // Try to get from cache first
        $cacheKey = "user_subscription_{$userId}";
        $cached = $this->redis->get($cacheKey);
        
        if ($cached !== false) {
            return json_decode($cached, true);
        }
        
        // Get from Stripe
        $subscription = $this->fetchUserSubscriptionFromStripe($userId);
        
        // Cache for 5 minutes
        if ($subscription) {
            $this->redis->setex($cacheKey, 300, json_encode($subscription));
        }
        
        return $subscription;
    }
    
    /**
     * Fetch subscription data from Stripe
     */
    private function fetchUserSubscriptionFromStripe($userId) {
        try {
            // Find customer by metadata
            $customers = Customer::all([
                'limit' => 1,
                'email' => $this->getUserEmail($userId)
            ]);
            
            if (empty($customers->data)) {
                return null;
            }
            
            $customer = $customers->data[0];
            
            // Get active subscriptions
            $subscriptions = Subscription::all([
                'customer' => $customer->id,
                'status' => 'active',
                'limit' => 1
            ]);
            
            if (empty($subscriptions->data)) {
                return null;
            }
            
            $subscription = $subscriptions->data[0];
            
            return [
                'id' => $subscription->id,
                'customer_id' => $customer->id,
                'status' => $subscription->status,
                'current_period_end' => $subscription->current_period_end,
                'cancel_at_period_end' => $subscription->cancel_at_period_end,
                'plan_id' => $subscription->items->data[0]->price->id,
                'is_active' => $subscription->status === 'active'
            ];
            
        } catch (Exception $e) {
            error_log("Error fetching subscription: " . $e->getMessage());
            return null;
        }
    }
    
    /**
     * Check if user has active subscription
     */
    public function hasActiveSubscription($userId) {
        $subscription = $this->getUserSubscription($userId);
        return $subscription && $subscription['is_active'] && $subscription['current_period_end'] > time();
    }
    
    /**
     * Get simulation limit for user
     */
    public function getSimulationLimit($userId) {
        if ($this->hasActiveSubscription($userId)) {
            return PREMIUM_SIMULATION_LIMIT;
        }
        return FREE_SIMULATION_LIMIT;
    }
    
    /**
     * Create Stripe customer for user
     */
    public function createCustomer($userId, $email, $name) {
        try {
            $customer = Customer::create([
                'email' => $email,
                'name' => $name,
                'metadata' => [
                    'user_id' => $userId
                ]
            ]);
            
            return $customer;
        } catch (Exception $e) {
            error_log("Error creating customer: " . $e->getMessage());
            throw $e;
        }
    }
    
    /**
     * Create subscription checkout session
     */
    public function createCheckoutSession($userId, $priceId, $successUrl, $cancelUrl) {
        try {
            // Get or create customer
            $email = $this->getUserEmail($userId);
            $name = $this->getUserName($userId);
            
            $customers = Customer::all([
                'limit' => 1,
                'email' => $email
            ]);
            
            if (empty($customers->data)) {
                $customer = $this->createCustomer($userId, $email, $name);
            } else {
                $customer = $customers->data[0];
            }
            
            // Create checkout session
            $session = \Stripe\Checkout\Session::create([
                'customer' => $customer->id,
                'payment_method_types' => ['card'],
                'line_items' => [[
                    'price' => $priceId,
                    'quantity' => 1,
                ]],
                'mode' => 'subscription',
                'success_url' => $successUrl,
                'cancel_url' => $cancelUrl,
                'metadata' => [
                    'user_id' => $userId
                ]
            ]);
            
            return $session;
        } catch (Exception $e) {
            error_log("Error creating checkout session: " . $e->getMessage());
            throw $e;
        }
    }
    
    /**
     * Create customer portal session
     */
    public function createPortalSession($userId, $returnUrl) {
        try {
            $subscription = $this->getUserSubscription($userId);
            if (!$subscription) {
                throw new Exception("No subscription found");
            }
            
            $session = \Stripe\BillingPortal\Session::create([
                'customer' => $subscription['customer_id'],
                'return_url' => $returnUrl,
            ]);
            
            return $session;
        } catch (Exception $e) {
            error_log("Error creating portal session: " . $e->getMessage());
            throw $e;
        }
    }
    
    /**
     * Handle Stripe webhook
     */
    public function handleWebhook($payload, $signature) {
        try {
            $event = \Stripe\Webhook::constructEvent(
                $payload,
                $signature,
                STRIPE_WEBHOOK_SECRET
            );
            
            switch ($event->type) {
                case 'customer.subscription.created':
                case 'customer.subscription.updated':
                case 'customer.subscription.deleted':
                    $subscription = $event->data->object;
                    $this->updateSubscriptionCache($subscription);
                    break;
                    
                case 'invoice.payment_succeeded':
                    $invoice = $event->data->object;
                    if ($invoice->subscription) {
                        $this->clearSubscriptionCache($invoice->customer);
                    }
                    break;
                    
                case 'invoice.payment_failed':
                    $invoice = $event->data->object;
                    if ($invoice->subscription) {
                        $this->clearSubscriptionCache($invoice->customer);
                    }
                    break;
            }
            
            return true;
        } catch (Exception $e) {
            error_log("Webhook error: " . $e->getMessage());
            return false;
        }
    }
    
    /**
     * Update subscription cache
     */
    private function updateSubscriptionCache($subscription) {
        try {
            $customer = Customer::retrieve($subscription->customer);
            $userId = $this->getUserIdFromEmail($customer->email);
            
            if ($userId) {
                $cacheKey = "user_subscription_{$userId}";
                $this->redis->delete($cacheKey);
            }
        } catch (Exception $e) {
            error_log("Error updating subscription cache: " . $e->getMessage());
        }
    }
    
    /**
     * Clear subscription cache
     */
    private function clearSubscriptionCache($customerId) {
        try {
            $customer = Customer::retrieve($customerId);
            $userId = $this->getUserIdFromEmail($customer->email);
            
            if ($userId) {
                $cacheKey = "user_subscription_{$userId}";
                $this->redis->delete($cacheKey);
            }
        } catch (Exception $e) {
            error_log("Error clearing subscription cache: " . $e->getMessage());
        }
    }
    
    /**
     * Helper methods to get user data from session
     */
    private function getUserEmail($userId) {
        // In a real app, you'd get this from database
        // For now, we'll get it from session if available
        session_start();
        return $_SESSION['email'] ?? null;
    }
    
    private function getUserName($userId) {
        session_start();
        return $_SESSION['name'] ?? 'User';
    }
    
    private function getUserIdFromEmail($email) {
        // In a real app, you'd query database
        // For now, we'll try to match from current session
        session_start();
        if (isset($_SESSION['email']) && $_SESSION['email'] === $email) {
            return $_SESSION['user_id'] ?? null;
        }
        return null;
    }
} 