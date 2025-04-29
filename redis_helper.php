<?php

class RedisHelper {
    private static $instance = null;
    private $redis;

    private function __construct() {
        if (!class_exists('Redis')) {
            throw new Exception('Redis extension is not installed');
        }
        
        $this->redis = new Redis();
        try {
            $this->redis->connect('127.0.0.1', 6379);
        } catch (Exception $e) {
            throw new Exception('Could not connect to Redis server: ' . $e->getMessage());
        }
        
        if (REDIS_PASSWORD) {
            $this->redis->auth(REDIS_PASSWORD);
        }
        
        $this->redis->select(REDIS_DB);
        
        // Enable igbinary serialization
        $this->redis->setOption(Redis::OPT_SERIALIZER, Redis::SERIALIZER_IGBINARY);
    }

    public static function getInstance() {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance->redis;
    }

    private function __clone() {}

    public function set($key, $value, $ttl = null) {
        // Only add prefix if key doesn't already start with it
        if (strpos($key, REDIS_PREFIX) !== 0) {
            $key = REDIS_PREFIX . $key;
        }
        if ($ttl === null) {
            $ttl = REDIS_TTL;
        }
        return $this->redis->setex($key, $ttl, $value);
    }

    public function get($key) {
        // Only add prefix if key doesn't already start with it
        if (strpos($key, REDIS_PREFIX) !== 0) {
            $key = REDIS_PREFIX . $key;
        }
        return $this->redis->get($key);
    }

    public function delete($key) {
        // Only add prefix if key doesn't already start with it
        if (strpos($key, REDIS_PREFIX) !== 0) {
            $key = REDIS_PREFIX . $key;
        }
        return $this->redis->del($key);
    }

    public function exists($key) {
        // Only add prefix if key doesn't already start with it
        if (strpos($key, REDIS_PREFIX) !== 0) {
            $key = REDIS_PREFIX . $key;
        }
        return $this->redis->exists($key);
    }

    public function keys($pattern) {
        // Handle prefix for pattern
        if (strpos($pattern, REDIS_PREFIX) !== 0) {
            $prefixed_pattern = REDIS_PREFIX . $pattern;
        } else {
            $prefixed_pattern = $pattern;
        }
        $keys = $this->redis->keys($prefixed_pattern);
        if ($keys) {
            return array_map(function($key) {
                return substr($key, strlen(REDIS_PREFIX));
            }, $keys);
        }
        return [];
    }
} 