# Performance Optimization Guide

Comprehensive guide to optimizing BookWyrm performance through database tuning, query optimization, caching strategies, and application-level improvements.

## Table of Contents

1. [Database Optimization](#database-optimization)
2. [Query Optimization](#query-optimization)
3. [Caching Strategies](#caching-strategies)
4. [Application Performance](#application-performance)
5. [Infrastructure Tuning](#infrastructure-tuning)
6. [Monitoring and Profiling](#monitoring-and-profiling)

---

## Database Optimization

### PostgreSQL Configuration

#### Essential Settings

Edit `/etc/postgresql/<version>/main/postgresql.conf`:

```ini
# Memory Settings
shared_buffers = 256MB              # 25% of RAM for dedicated server
effective_cache_size = 1GB          # 50-75% of RAM
work_mem = 16MB                      # Per operation memory
maintenance_work_mem = 128MB        # For VACUUM, CREATE INDEX

# Query Planning
random_page_cost = 1.1              # Adjust for SSD (default 4.0)
effective_io_concurrency = 200      # For SSD (default 1)

# Write-Ahead Log
wal_buffers = 16MB
checkpoint_completion_target = 0.9
max_wal_size = 1GB
min_wal_size = 80MB

# Connection Settings
max_connections = 100               # Adjust based on needs
```

#### For Small Instances (< 2GB RAM)
```ini
shared_buffers = 256MB
effective_cache_size = 768MB
work_mem = 4MB
maintenance_work_mem = 64MB
```

#### For Medium Instances (4-8GB RAM)
```ini
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 16MB
maintenance_work_mem = 256MB
```

#### For Large Instances (> 8GB RAM)
```ini
shared_buffers = 2GB
effective_cache_size = 6GB
work_mem = 32MB
maintenance_work_mem = 512MB
```

### Indexes

#### Analyze Index Usage

```bash
python manage.py analyze_db_performance --analysis indexes
```

#### Creating Effective Indexes

```sql
-- Index for foreign key lookups
CREATE INDEX idx_status_user ON bookwyrm_status(user_id) WHERE NOT deleted;

-- Partial index for active users
CREATE INDEX idx_users_active ON bookwyrm_user(username) WHERE is_active AND NOT deleted;

-- Composite index for common queries
CREATE INDEX idx_status_user_published ON bookwyrm_status(user_id, published_date DESC);

-- GIN index for full-text search
CREATE INDEX idx_book_title_search ON bookwyrm_edition USING gin(to_tsvector('english', title));
```

#### Index Maintenance

```bash
# Identify unused indexes
python manage.py analyze_db_performance --analysis unused-indexes

# Rebuild fragmented indexes
psql -d bookwyrm -c "REINDEX INDEX CONCURRENTLY idx_name;"

# Analyze tables after index changes
psql -d bookwyrm -c "ANALYZE bookwyrm_status;"
```

### VACUUM and ANALYZE

#### Auto-vacuum Tuning

```ini
# In postgresql.conf
autovacuum = on
autovacuum_max_workers = 3
autovacuum_naptime = 10s              # Check more frequently
autovacuum_vacuum_threshold = 50
autovacuum_analyze_threshold = 50
autovacuum_vacuum_scale_factor = 0.1  # VACUUM at 10% dead tuples
autovacuum_analyze_scale_factor = 0.05
```

#### Manual Maintenance

```bash
# Full VACUUM (requires downtime)
python manage.py dbshell
VACUUM FULL ANALYZE bookwyrm_status;

# Regular VACUUM (no downtime)
VACUUM ANALYZE bookwyrm_status;

# For all tables
VACUUM ANALYZE;
```

#### Monitoring Bloat

```bash
# Detect bloated tables
python manage.py analyze_db_performance --analysis bloat

# Address bloat
VACUUM (FULL, ANALYZE) bookwyrm_tablename;
```

### Connection Pooling

#### PgBouncer Configuration

Install PgBouncer:
```bash
sudo apt-get install pgbouncer
```

Edit `/etc/pgbouncer/pgbouncer.ini`:
```ini
[databases]
bookwyrm = host=localhost dbname=bookwyrm port=5432

[pgbouncer]
pool_mode = transaction
max_client_conn = 100
default_pool_size = 20
reserve_pool_size = 5
reserve_pool_timeout = 5
```

Update BookWyrm settings:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'bookwyrm',
        'USER': 'bookwyrm',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '6432',  # PgBouncer port
    }
}
```

---

## Query Optimization

### Identify Slow Queries

#### Enable pg_stat_statements

```sql
-- Add to postgresql.conf
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
pg_stat_statements.max = 10000

-- Restart PostgreSQL
sudo systemctl restart postgresql

-- Create extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

#### Find Slow Queries

```bash
# Using Django management command
python manage.py analyze_db_performance --analysis queries

# Direct SQL
psql -d bookwyrm -c "
SELECT
    LEFT(query, 100) as query_preview,
    calls,
    ROUND(total_exec_time::numeric, 2) as total_time_ms,
    ROUND(mean_exec_time::numeric, 2) as mean_time_ms,
    ROUND(max_exec_time::numeric, 2) as max_time_ms
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_exec_time DESC
LIMIT 20;
"
```

### Optimize N+1 Queries

#### Problem Example

```python
# BAD: 1 + N queries
def book_list(request):
    books = Book.objects.all()[:100]  # 1 query
    for book in books:
        authors = book.authors.all()   # 100 queries!
```

#### Solution: Use select_related

```python
# GOOD: 1 query with JOIN
def book_list(request):
    books = Book.objects.select_related('parent_work').all()[:100]
```

#### Solution: Use prefetch_related

```python
# GOOD: 2 queries
def book_list(request):
    books = Book.objects.prefetch_related('authors', 'subjects').all()[:100]
```

#### Complex Prefetching

```python
from django.db.models import Prefetch

# Optimize nested relationships
books = Book.objects.prefetch_related(
    Prefetch('reviews',
        queryset=Review.objects.select_related('user').filter(is_active=True)
    ),
    'authors',
    'subjects'
)
```

### Query Optimization Patterns

#### Use only() and defer()

```python
# Fetch only needed fields
users = User.objects.only('id', 'username', 'avatar').all()

# Exclude large fields
books = Book.objects.defer('description', 'bio').all()
```

#### Use select_for_update() for Concurrency

```python
# Prevent race conditions
with transaction.atomic():
    book = Book.objects.select_for_update().get(id=book_id)
    book.rating_count += 1
    book.save()
```

#### Use Raw Queries When Needed

```python
from django.db import connection

def get_popular_books():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT b.id, b.title, COUNT(r.id) as review_count
            FROM bookwyrm_edition b
            LEFT JOIN bookwyrm_review r ON r.book_id = b.id
            GROUP BY b.id
            ORDER BY review_count DESC
            LIMIT 100
        """)
        return cursor.fetchall()
```

### Query Optimization Checklist

- [ ] Use select_related() for ForeignKey lookups
- [ ] Use prefetch_related() for Many-to-Many lookups
- [ ] Avoid queries in loops
- [ ] Use only() to fetch specific fields
- [ ] Use defer() to exclude heavy fields
- [ ] Add indexes for frequently filtered fields
- [ ] Use bulk operations (bulk_create, bulk_update)
- [ ] Use exists() instead of count() for existence checks
- [ ] Use iterator() for large querysets

---

## Caching Strategies

### Redis Configuration

#### Memory Management

Edit `redis.conf`:
```ini
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistence (for activity streams)
save 900 1
save 300 10
save 60 10000
```

#### Django Cache Configuration

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/0',
        'OPTIONS': {
            'parser_class': 'redis.connection.HiredisParser',
            'pool_class': 'redis.BlockingConnectionPool',
            'pool_class_kwargs': {
                'max_connections': 50,
                'timeout': 20,
            }
        }
    }
}
```

### Caching Patterns

#### View Caching

```python
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # 15 minutes
def book_detail(request, book_id):
    # View code
    pass
```

#### Template Fragment Caching

```django
{% load cache %}

{% cache 900 book_sidebar book.id %}
    <div class="sidebar">
        {# Expensive sidebar rendering #}
    </div>
{% endcache %}
```

#### Low-Level Caching

```python
from django.core.cache import cache

def get_popular_books():
    cache_key = 'popular_books'
    books = cache.get(cache_key)
    
    if books is None:
        books = Book.objects.annotate(
            review_count=Count('reviews')
        ).order_by('-review_count')[:100]
        cache.set(cache_key, books, 60 * 30)  # 30 minutes
    
    return books
```

#### Cache Invalidation

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Review)
def invalidate_book_cache(sender, instance, **kwargs):
    cache_key = f'book_reviews_{instance.book_id}'
    cache.delete(cache_key)
    
    # Invalidate related caches
    cache.delete('popular_books')
```

### Activity Streams Optimization

BookWyrm uses Redis for activity streams. Optimize with:

```python
# Settings
STREAMS = [
    {
        "key": "home",
        "name": "Home",
        "shortname": "home",
        "descending": True,
        "max_length": 200,  # Limit stream size
    },
    # ...
]

# Trim streams periodically
from bookwyrm.activitystreams import HomeStream

stream = HomeStream()
stream.trim()  # Removes old items beyond max_length
```

---

## Application Performance

### Celery Optimization

#### Queue Configuration

```python
# Use multiple queues for priority
CELERY_TASK_ROUTES = {
    'bookwyrm.tasks.high_priority_task': {'queue': 'high'},
    'bookwyrm.tasks.low_priority_task': {'queue': 'low'},
}

# Configure queue priorities
CELERY_TASK_QUEUES = (
    Queue('high', routing_key='high', priority=10),
    Queue('medium', routing_key='medium', priority=5),
    Queue('low', routing_key='low', priority=1),
)
```

#### Worker Configuration

```bash
# Start multiple workers with different concurrency
celery -A celerywyrm worker --queue=high --concurrency=4 --pool=prefork
celery -A celerywyrm worker --queue=medium --concurrency=2 --pool=prefork
celery -A celerywyrm worker --queue=low --concurrency=1 --pool=prefork
```

#### Task Optimization

```python
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit='100/m'  # Rate limiting
)
def process_inbox_activity(self, activity):
    try:
        # Task code
        pass
    except Exception as exc:
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

### Static File Optimization

#### Compression

```python
# settings.py
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.rCSSMinFilter',
]
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.JSMinFilter',
]
```

#### Content Delivery Network (CDN)

```python
# Use CDN for static files
STATIC_URL = 'https://cdn.example.com/static/'
MEDIA_URL = 'https://cdn.example.com/media/'

# S3/CloudFront configuration
AWS_STORAGE_BUCKET_NAME = 'bookwyrm-static'
AWS_S3_CUSTOM_DOMAIN = 'd111111abcdef8.cloudfront.net'
```

### Image Optimization

```python
from PIL import Image
from django.core.files.base import ContentFile
from io import BytesIO

def optimize_image(image_file, max_size=(800, 800), quality=85):
    img = Image.open(image_file)
    
    # Convert RGBA to RGB
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    # Resize if needed
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Save with optimization
    output = BytesIO()
    img.save(output, format='JPEG', quality=quality, optimize=True)
    
    return ContentFile(output.getvalue())
```

---

## Infrastructure Tuning

### Gunicorn Configuration

```python
# gunicorn.conf.py
import multiprocessing

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'gthread'
threads = 4
worker_connections = 1000

# Performance tuning
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5

# Preload app for faster worker spawning
preload_app = True
```

### Nginx Configuration

```nginx
# /etc/nginx/sites-available/bookwyrm

# Caching
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=bookwyrm_cache:10m max_size=1g inactive=60m;

server {
    listen 80;
    server_name example.com;

    # Compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss;

    # Static files with long cache
    location /static/ {
        alias /path/to/bookwyrm/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Media files with moderate cache
    location /media/ {
        alias /path/to/bookwyrm/images/;
        expires 30d;
        add_header Cache-Control "public";
    }

    # Proxy to Gunicorn with caching
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Cache GET requests
        proxy_cache bookwyrm_cache;
        proxy_cache_valid 200 10m;
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503 http_504;
        proxy_cache_lock on;
        
        add_header X-Cache-Status $upstream_cache_status;
    }
}
```

### Load Balancing

For multiple application servers:

```nginx
upstream bookwyrm_backend {
    least_conn;
    server app1.example.com:8000 weight=1;
    server app2.example.com:8000 weight=1;
    server app3.example.com:8000 weight=1;
    
    keepalive 32;
}

server {
    # ...
    location / {
        proxy_pass http://bookwyrm_backend;
        # ...
    }
}
```

---

## Monitoring and Profiling

### Enable Query Profiling

```python
# settings.py
if DEBUG:
    ENABLE_QUERY_PROFILING = True
    QUERY_PROFILE_THRESHOLD_MS = 1000
    QUERY_COUNT_THRESHOLD = 50
    
    MIDDLEWARE += [
        'bookwyrm.middleware.query_profiler.QueryProfilingMiddleware',
    ]
```

### Performance Logging

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'performance': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/bookwyrm/performance.log',
        },
    },
    'loggers': {
        'bookwyrm.middleware.query_profiler': {
            'handlers': ['performance'],
            'level': 'INFO',
            'propagate': False,
        },
        'bookwyrm.utils.performance': {
            'handlers': ['performance'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Regular Performance Audits

```bash
# Monthly performance audit script
#!/bin/bash

DATE=$(date +%Y%m%d)
REPORT_DIR="/var/log/bookwyrm/performance_reports"
mkdir -p $REPORT_DIR

# Database performance analysis
python manage.py analyze_db_performance > "$REPORT_DIR/db_analysis_$DATE.txt"

# Health check
python manage.py health_check > "$REPORT_DIR/health_check_$DATE.txt"

# Data integrity check
python manage.py check_data_integrity > "$REPORT_DIR/integrity_check_$DATE.txt"

# Query profiling
python manage.py profile_queries --min-duration 100 > "$REPORT_DIR/slow_queries_$DATE.txt"
```

### Key Performance Metrics

Track these metrics:

1. **Response Time**
   - Target: p95 < 500ms, p99 < 1000ms
   - Monitor: Nginx access logs, application logs

2. **Database Performance**
   - Target: < 100 active connections
   - Target: > 95% cache hit ratio
   - Monitor: `analyze_db_performance` command

3. **Cache Effectiveness**
   - Target: > 80% cache hit rate
   - Monitor: Redis INFO stats

4. **Celery Queue Depth**
   - Target: < 1000 pending tasks
   - Monitor: `health_check` command

5. **Error Rate**
   - Target: < 1% 5xx errors
   - Monitor: Nginx error logs

---

## Performance Checklist

### Daily
- [ ] Monitor slow query log
- [ ] Check Celery queue depths
- [ ] Review error rates

### Weekly
- [ ] Run database performance analysis
- [ ] Review cache hit ratios
- [ ] Check for N+1 queries in logs
- [ ] Monitor disk space usage

### Monthly
- [ ] Full performance audit
- [ ] Review and optimize slow queries
- [ ] Analyze index usage
- [ ] VACUUM and ANALYZE database
- [ ] Review and update caching strategy

### Quarterly
- [ ] Load testing
- [ ] Capacity planning review
- [ ] Infrastructure scaling assessment
- [ ] Review and update performance targets

---

## Common Performance Issues

### Issue: Slow Page Loads

**Symptoms:** High response times (> 1s)

**Diagnosis:**
```bash
python manage.py analyze_db_performance --analysis queries long-running
```

**Solutions:**
1. Add select_related/prefetch_related
2. Implement caching
3. Optimize queries
4. Add indexes

### Issue: High Database CPU

**Symptoms:** Database CPU > 80%

**Diagnosis:**
```bash
python manage.py analyze_db_performance --analysis queries blocking
```

**Solutions:**
1. Identify and optimize slow queries
2. Add missing indexes
3. Increase connection pool
4. Consider read replicas

### Issue: Memory Leaks

**Symptoms:** Growing memory usage over time

**Diagnosis:**
```bash
# Monitor with htop or similar
python manage.py health_check
```

**Solutions:**
1. Restart Gunicorn workers periodically (max_requests)
2. Use iterator() for large querysets
3. Clear caches regularly
4. Profile memory usage with memory_profiler

### Issue: High Redis Memory

**Symptoms:** Redis memory > 80% of maxmemory

**Diagnosis:**
```bash
redis-cli INFO memory
python manage.py health_check --check redis_activity
```

**Solutions:**
1. Reduce stream max_length
2. Adjust maxmemory-policy
3. Trim activity streams
4. Increase Redis memory allocation

---

## Resources

- [PostgreSQL Performance Wiki](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Django Database Optimization](https://docs.djangoproject.com/en/stable/topics/db/optimization/)
- [Redis Best Practices](https://redis.io/docs/manual/optimization/)
- [Celery Performance](https://docs.celeryproject.org/en/stable/userguide/optimizing.html)
