# Admin Tooling Guide

Comprehensive guide to BookWyrm admin tooling for system health monitoring, database analytics, performance profiling, and data management.

## Table of Contents

1. [System Health Checks](#system-health-checks)
2. [Database Analytics](#database-analytics)
3. [Performance Profiling](#performance-profiling)
4. [Data Integrity Tools](#data-integrity-tools)
5. [Backup and Recovery](#backup-and-recovery)
6. [Best Practices](#best-practices)

---

## System Health Checks

Monitor the health of your BookWyrm instance components.

### Health Check Command

```bash
python manage.py health_check
```

#### Options

- `--format [text|json]` - Output format (default: text)
- `--check [name]` - Run only a specific check
- `--fail-on-unhealthy` - Exit with error code if any component is unhealthy
- `--fail-on-degraded` - Exit with error code if any component is degraded

#### Available Checks

- **database** - PostgreSQL connectivity and performance
- **redis_broker** - Redis broker (Celery) health and queue depth
- **redis_activity** - Redis activity stream health and memory usage
- **celery** - Celery worker status and task count
- **cache** - Django cache functionality
- **storage** - Storage backend accessibility
- **email_config** - Email configuration validity
- **federation** - Federation service status

### Example Usage

```bash
# Run all health checks
python manage.py health_check

# Run specific check
python manage.py health_check --check database

# Get JSON output
python manage.py health_check --format json

# Use in monitoring (exit code)
python manage.py health_check --fail-on-unhealthy
if [ $? -ne 0 ]; then
    echo "Health check failed!"
    # Send alert
fi
```

### Health Check Output

```
======================================================================
BookWyrm System Health Check
Time: 2026-02-19 10:30:00
======================================================================

✓ DATABASE: healthy
  Message: Database is responsive
  Duration: 45.23ms
  Details:
    connections: 3
    database_size: 1.2 GB
    response_time_ms: 45.23

✓ REDIS_BROKER: healthy
  Message: Redis broker operational
  Duration: 12.45ms
  Details:
    total_pending_tasks: 42
    queues:
      high: 2
      medium: 15
      low: 25

======================================================================
Summary
----------------------------------------------------------------------
Overall Status: HEALTHY
Message: All components healthy
Healthy: 8/8
Degraded: 0/8
Unhealthy: 0/8
======================================================================
```

### Integration with Monitoring

#### Prometheus Integration

Create a custom exporter using the JSON output:

```python
import subprocess
import json
from prometheus_client import Gauge

health_status = Gauge('bookwyrm_health_status', 'Health check status', ['component'])

def collect_health():
    result = subprocess.run(
        ['python', 'manage.py', 'health_check', '--format', 'json'],
        capture_output=True,
        text=True
    )
    data = json.loads(result.stdout)
    
    for check in data['checks']:
        status_value = {'healthy': 1, 'degraded': 0.5, 'unhealthy': 0}[check['status']]
        health_status.labels(component=check['name']).set(status_value)
```

#### Cron Job for Periodic Checks

```bash
# Check health every 5 minutes and log results
*/5 * * * * /path/to/venv/bin/python /path/to/bookwyrm/manage.py health_check >> /var/log/bookwyrm/health.log 2>&1
```

---

## Database Analytics

Comprehensive database performance analysis and optimization tools.

### Analyze Database Performance

```bash
python manage.py analyze_db_performance
```

#### Options

- `--format [text|json]` - Output format
- `--analysis [type]` - Analysis types to perform (can specify multiple)
- `--limit N` - Limit number of results for table/index statistics
- `--min-duration N` - Minimum duration (seconds) for long-running queries
- `--min-index-size N` - Minimum size (MB) for unused index detection

#### Analysis Types

- **connections** - Connection pool statistics and usage
- **size** - Database and table size information
- **tables** - Comprehensive table statistics (rows, bloat, scans)
- **indexes** - Index usage and efficiency statistics
- **queries** - Query performance analysis (requires pg_stat_statements)
- **bloat** - Table and index bloat detection
- **cache** - Cache hit ratio analysis
- **blocking** - Detect blocking queries
- **long-running** - Find long-running queries
- **unused-indexes** - Identify unused or rarely-used indexes
- **recommendations** - Optimization recommendations

### Example Usage

```bash
# Full analysis
python manage.py analyze_db_performance

# Specific analyses
python manage.py analyze_db_performance --analysis connections size cache

# Find unused indexes larger than 10MB
python manage.py analyze_db_performance --analysis unused-indexes --min-index-size 10

# Find queries running longer than 120 seconds
python manage.py analyze_db_performance --analysis long-running --min-duration 120
```

### Understanding Output

#### Connection Statistics

```
Connection Statistics:
--------------------------------------------------------------------------------
Total Connections: 15
Active Connections: 3
Idle Connections: 12
Idle in Transaction: 0
Max Connections: 100
Connection Usage: 15%
```

**What to watch for:**
- Connection usage > 80%: Consider connection pooling or increasing max_connections
- High idle in transaction: Indicates transactions not being committed

#### Cache Hit Ratio

```
Cache Hit Ratio:
--------------------------------------------------------------------------------
Table Cache Hit Ratio: 98.5%
Index Cache Hit Ratio: 99.2%
Heap Blocks Read: 1,250
Heap Blocks Hit: 75,000
```

**What to watch for:**
- Cache hit ratio < 90%: Consider increasing `shared_buffers` in PostgreSQL
- Goal: > 95% cache hit ratio for optimal performance

#### Table Bloat

```
Table Bloat Detection:
--------------------------------------------------------------------------------
Found 3 table(s) with significant bloat:

1. public.bookwyrm_status:
  Size: 450 MB
  Live Tuples: 120,000
  Dead Tuples: 35,000
  Bloat: 29.2%
  Last Vacuum: 2026-02-15 03:00:00
  Last Autovacuum: 2026-02-18 14:22:10
```

**Action:** Run `VACUUM ANALYZE bookwyrm_status;`

#### Unused Indexes

```
Unused/Rarely Used Indexes:
--------------------------------------------------------------------------------
Found 5 unused or rarely-used index(es):

1. public.bookwyrm_notification.bookwyrm_notification_user_id_idx:
  Size: 15 MB
  Scans: 2
  Consider: DROP INDEX public.bookwyrm_notification_user_id_idx;
```

**Action:** Review query patterns and consider dropping if truly unused.

### Optimization Workflow

1. **Run full analysis monthly**
   ```bash
   python manage.py analyze_db_performance > /var/log/bookwyrm/db_analysis_$(date +%Y%m%d).txt
   ```

2. **Act on recommendations**
   - Address bloated tables with VACUUM
   - Drop unused indexes
   - Adjust PostgreSQL configuration based on cache hit ratios

3. **Monitor long-running queries**
   ```bash
   # Check for queries running > 60 seconds
   python manage.py analyze_db_performance --analysis long-running --min-duration 60
   ```

---

## Performance Profiling

Identify and resolve performance bottlenecks in your BookWyrm instance.

### Query Profiler Middleware

Enable query profiling in development to detect N+1 queries and slow requests.

#### Configuration

Add to `settings.py`:

```python
# Enable query profiling
ENABLE_QUERY_PROFILING = True  # Default: DEBUG

# Thresholds for logging warnings
QUERY_PROFILE_THRESHOLD_MS = 1000  # Log requests slower than 1 second
QUERY_COUNT_THRESHOLD = 50  # Log requests with > 50 queries

# Add middleware
MIDDLEWARE = [
    ...
    'bookwyrm.middleware.query_profiler.QueryProfilingMiddleware',
    'bookwyrm.middleware.query_profiler.PerformanceLoggingMiddleware',
    ...
]
```

#### Middleware Output

The middleware adds performance headers to responses (in DEBUG mode):

```
X-Query-Count: 45
X-Query-Time-Ms: 234.56
X-Total-Time-Ms: 456.78
```

### Profile Queries Command

```bash
python manage.py profile_queries
```

Analyzes queries from the last request in DEBUG mode.

#### Options

- `--min-duration N` - Minimum query duration in milliseconds (default: 100)

### Performance Profiling Decorators

Use the `@profile_view` decorator to track view performance:

```python
from bookwyrm.utils.performance import profile_view

@profile_view
def book_detail(request, book_id):
    # Your view code
    pass
```

### Contextual Query Profiling

```python
from bookwyrm.utils.performance import profile_queries

with profile_queries() as profiler:
    # Code to profile
    books = Book.objects.all()[:100]
    for book in books:
        _ = book.authors.all()  # Potential N+1

summary = profiler.get_summary()
print(f"Queries: {summary['query_count']}")
print(f"Time: {summary['total_time_ms']}ms")
print(f"N+1 detected: {len(summary['n_plus_one_detected'])}")
```

### Detecting N+1 Queries

#### What is an N+1 Query Problem?

```python
# BAD: N+1 query pattern
books = Book.objects.all()[:10]  # 1 query
for book in books:
    authors = book.authors.all()  # 10 queries (N queries)
# Total: 11 queries (1 + N)

# GOOD: Use select_related/prefetch_related
books = Book.objects.prefetch_related('authors').all()[:10]  # 2 queries
for book in books:
    authors = book.authors.all()  # No additional queries
# Total: 2 queries
```

#### Detecting N+1 in Logs

The profiler will log warnings like:

```
WARNING: Possible N+1 query detected in /book/123: 
Query executed 15 times, total time: 0.456s
Pattern: SELECT * FROM bookwyrm_author WHERE id = ?
```

### Performance Best Practices

1. **Use select_related() for ForeignKey relationships**
   ```python
   # Instead of:
   statuses = Status.objects.all()
   
   # Do:
   statuses = Status.objects.select_related('user', 'reply_parent').all()
   ```

2. **Use prefetch_related() for Many-to-Many relationships**
   ```python
   # Instead of:
   books = Book.objects.all()
   
   # Do:
   books = Book.objects.prefetch_related('authors', 'subjects').all()
   ```

3. **Use only() to fetch specific fields**
   ```python
   # Fetch only needed fields
   users = User.objects.only('id', 'username', 'email').all()
   ```

4. **Use defer() to exclude heavy fields**
   ```python
   # Exclude large text fields
   books = Book.objects.defer('description', 'cover_image').all()
   ```

5. **Monitor query count per request**
   - Aim for < 50 queries per page
   - Use `select_related()` and `prefetch_related()` aggressively

---

## Data Integrity Tools

Maintain data consistency and detect orphaned records.

### Check Data Integrity

```bash
python manage.py check_data_integrity
```

#### Options

- `--format [text|json]` - Output format
- `--check [type]` - Check types to perform

#### Check Types

- **orphaned** - Detect orphaned records from deleted users/books
- **relationships** - Validate user and book relationships
- **federation** - Check ActivityPub data integrity
- **duplicates** - Find duplicate records
- **foreign-keys** - Validate foreign key constraints

### Example Usage

```bash
# Full integrity check
python manage.py check_data_integrity

# Check specific issues
python manage.py check_data_integrity --check orphaned relationships

# Get JSON output for automation
python manage.py check_data_integrity --format json
```

### Cleanup Orphaned Data

```bash
python manage.py cleanup_orphaned_data
```

#### Options

- `--dry-run` - Show what would be deleted without deleting
- `--cleanup [type]` - Cleanup types to perform
- `--batch-size N` - Batch size for deletions (default: 1000)

#### Cleanup Types

- **statuses** - Remove statuses from deleted users
- **reviews** - Remove orphaned reviews
- **shelf-books** - Remove orphaned shelf entries
- **list-items** - Remove orphaned list items
- **notifications** - Remove orphaned notifications
- **relationships** - Remove invalid user relationships

### Safe Cleanup Workflow

1. **Always run with --dry-run first**
   ```bash
   python manage.py cleanup_orphaned_data --dry-run
   ```

2. **Review the output carefully**
   - Check the count of records to be deleted
   - Verify the types of data being removed

3. **Run actual cleanup**
   ```bash
   python manage.py cleanup_orphaned_data
   ```

4. **Verify integrity after cleanup**
   ```bash
   python manage.py check_data_integrity
   ```

### Automated Integrity Checks

Add to cron for regular integrity monitoring:

```bash
# Weekly integrity check
0 2 * * 0 /path/to/venv/bin/python /path/to/bookwyrm/manage.py check_data_integrity --format json >> /var/log/bookwyrm/integrity.log 2>&1
```

---

## Backup and Recovery

Comprehensive backup and recovery tools for database, media files, and configuration.

### Database Backup

```bash
python manage.py backup_database
```

#### Options

- `--backup-dir PATH` - Directory to store backups
- `--no-compress` - Don't compress the backup
- `--format [custom|plain|directory|tar]` - Backup format (default: custom)
- `--verify` - Verify backup after creation

#### Backup Formats

- **custom** - PostgreSQL custom format (recommended, compact, flexible)
- **plain** - Plain SQL dump (human-readable, larger)
- **directory** - Directory format (parallel dump/restore)
- **tar** - TAR archive format

### Media Backup

```bash
python manage.py backup_media
```

#### Options

- `--backup-dir PATH` - Directory to store backups
- `--no-compress` - Don't compress the backup
- `--verify` - Verify backup after creation

### Verify Backup

```bash
python manage.py verify_backup /path/to/backup.dump
```

#### Options

- `--backup-type [database|media|auto]` - Backup type (default: auto-detect)

### Backup Examples

```bash
# Quick database backup
python manage.py backup_database

# Uncompressed plain SQL backup
python manage.py backup_database --format plain --no-compress

# Database backup with verification
python manage.py backup_database --verify

# Media backup to custom location
python manage.py backup_media --backup-dir /mnt/backups

# Verify existing backup
python manage.py verify_backup /backups/bookwyrm_db_20260219_103000.dump
```

### Automated Backup Strategy

#### Daily Database Backups

```bash
#!/bin/bash
# /usr/local/bin/bookwyrm-backup-db.sh

cd /path/to/bookwyrm
source venv/bin/activate

python manage.py backup_database --verify

# Clean up old backups (keep last 30 days)
find /path/to/bookwyrm/backups -name "bookwyrm_db_*.dump" -mtime +30 -delete
```

Add to cron:
```bash
0 2 * * * /usr/local/bin/bookwyrm-backup-db.sh >> /var/log/bookwyrm/backup.log 2>&1
```

#### Weekly Media Backups

```bash
#!/bin/bash
# /usr/local/bin/bookwyrm-backup-media.sh

cd /path/to/bookwyrm
source venv/bin/activate

python manage.py backup_media --verify

# Keep last 4 weekly backups
find /path/to/bookwyrm/backups -name "bookwyrm_media_*.tar.gz" -mtime +28 -delete
```

Add to cron:
```bash
0 3 * * 0 /usr/local/bin/bookwyrm-backup-media.sh >> /var/log/bookwyrm/backup.log 2>&1
```

### Recovery Process

#### Database Recovery

```bash
# 1. Stop BookWyrm services
sudo systemctl stop bookwyrm

# 2. Restore database
pg_restore -h localhost -U bookwyrm -d bookwyrm_new /backups/bookwyrm_db_20260219.dump

# 3. Verify restoration
python manage.py check_data_integrity

# 4. Start services
sudo systemctl start bookwyrm
```

#### Media Recovery

```bash
# 1. Stop BookWyrm services
sudo systemctl stop bookwyrm

# 2. Extract media backup
cd /path/to/bookwyrm
tar -xzf /backups/bookwyrm_media_20260219.tar.gz

# 3. Set correct permissions
chown -R www-data:www-data images/

# 4. Start services
sudo systemctl start bookwyrm
```

### Backup Best Practices

1. **3-2-1 Backup Rule**
   - 3 copies of data
   - 2 different media types
   - 1 offsite copy

2. **Regular Testing**
   - Test restores monthly
   - Verify backups automatically
   - Document recovery procedures

3. **Retention Policy**
   - Daily backups: Keep 7 days
   - Weekly backups: Keep 4 weeks
   - Monthly backups: Keep 12 months

4. **Monitoring**
   - Alert on backup failures
   - Track backup size trends
   - Monitor backup duration

---

## Best Practices

### Regular Maintenance Schedule

#### Daily
- [ ] Monitor health checks
- [ ] Review error logs
- [ ] Check Celery queue depth

#### Weekly
- [ ] Run full health check with reports
- [ ] Review slow queries
- [ ] Check for data integrity issues

#### Monthly
- [ ] Full database performance analysis
- [ ] Review and optimize indexes
- [ ] Clean up orphaned data
- [ ] Test backup restoration
- [ ] Review disk space usage

#### Quarterly
- [ ] Performance audit
- [ ] Capacity planning review
- [ ] Update documentation
- [ ] Review and update monitoring thresholds

### Monitoring Integration

Set up alerts for:
- Health check failures
- Database connection pool > 80%
- Cache hit ratio < 90%
- Long-running queries > 300s
- Backup failures
- Data integrity issues

### Documentation

Maintain runbooks for:
- Incident response procedures
- Database recovery procedures
- Performance troubleshooting
- Common issues and solutions

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/bookwyrm-social/bookwyrm/issues
- Documentation: https://docs.joinbookwyrm.com/
- Matrix Chat: #bookwyrm:matrix.org
