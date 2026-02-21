"""Database analytics and performance monitoring utilities.

Provides tools for analyzing database performance, detecting slow queries,
analyzing table statistics, and monitoring connection pools.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.db import connection, connections
from django.core.cache import cache

logger = logging.getLogger(__name__)


class DatabaseAnalyzer:
    """Analyzes database performance and provides optimization recommendations."""

    def __init__(self, database="default"):
        """Initialize database analyzer.

        Args:
            database: Database alias to analyze (default: 'default')
        """
        self.database = database
        self.connection = connections[database]

    def get_connection_stats(self) -> Dict:
        """Get database connection statistics.

        Returns:
            Dictionary with connection statistics
        """
        with self.connection.cursor() as cursor:
            # Get current connections
            cursor.execute("""
                SELECT 
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections,
                    count(*) FILTER (WHERE state = 'idle') as idle_connections,
                    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            result = cursor.fetchone()

            # Get connection limits
            cursor.execute("SHOW max_connections")
            max_connections = int(cursor.fetchone()[0])

            return {
                "total_connections": result[0],
                "active_connections": result[1],
                "idle_connections": result[2],
                "idle_in_transaction": result[3],
                "max_connections": max_connections,
                "connection_usage_percent": round(
                    (result[0] / max_connections) * 100, 2
                ),
            }

    def get_database_size_stats(self) -> Dict:
        """Get database size and growth statistics.

        Returns:
            Dictionary with size statistics
        """
        with self.connection.cursor() as cursor:
            # Get database size
            cursor.execute("""
                SELECT 
                    pg_size_pretty(pg_database_size(current_database())) as size,
                    pg_database_size(current_database()) as size_bytes
            """)
            db_size, db_size_bytes = cursor.fetchone()

            # Get largest tables
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY size_bytes DESC
                LIMIT 10
            """)
            largest_tables = [
                {
                    "schema": row[0],
                    "table": row[1],
                    "size": row[2],
                    "size_bytes": row[3],
                }
                for row in cursor.fetchall()
            ]

            return {
                "database_size": db_size,
                "database_size_bytes": db_size_bytes,
                "largest_tables": largest_tables,
            }

    def get_table_statistics(self, limit: int = 20) -> List[Dict]:
        """Get comprehensive table statistics.

        Args:
            limit: Maximum number of tables to return

        Returns:
            List of table statistics dictionaries
        """
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                                   pg_relation_size(schemaname||'.'||tablename)) as index_size,
                    n_live_tup as row_count,
                    n_dead_tup as dead_rows,
                    CASE 
                        WHEN n_live_tup > 0 
                        THEN round((n_dead_tup::float / n_live_tup::float) * 100, 2)
                        ELSE 0 
                    END as dead_row_percent,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze,
                    seq_scan,
                    idx_scan,
                    CASE 
                        WHEN (seq_scan + idx_scan) > 0
                        THEN round((idx_scan::float / (seq_scan + idx_scan)::float) * 100, 2)
                        ELSE 0
                    END as index_usage_percent
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT %s
            """, [limit])

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_index_statistics(self, limit: int = 20) -> List[Dict]:
        """Get index usage statistics.

        Args:
            limit: Maximum number of indexes to return

        Returns:
            List of index statistics dictionaries
        """
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched,
                    CASE 
                        WHEN idx_scan = 0 THEN 'UNUSED'
                        WHEN idx_scan < 50 THEN 'RARELY USED'
                        ELSE 'USED'
                    END as usage_status
                FROM pg_stat_user_indexes
                ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
                LIMIT %s
            """, [limit])

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def find_unused_indexes(self, min_size_mb: int = 1) -> List[Dict]:
        """Find indexes that are never or rarely used.

        Args:
            min_size_mb: Minimum size in MB to consider (default: 1)

        Returns:
            List of unused index dictionaries
        """
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                    pg_relation_size(indexrelid) as size_bytes,
                    idx_scan as index_scans
                FROM pg_stat_user_indexes
                WHERE idx_scan < 50
                    AND pg_relation_size(indexrelid) > %s * 1024 * 1024
                    AND indexname NOT LIKE '%%_pkey'
                ORDER BY pg_relation_size(indexrelid) DESC
            """, [min_size_mb])

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_query_performance_stats(self) -> Dict:
        """Get query performance statistics (requires pg_stat_statements extension).

        Returns:
            Dictionary with query performance statistics
        """
        with self.connection.cursor() as cursor:
            # Check if pg_stat_statements is available
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                )
            """)
            has_pg_stat_statements = cursor.fetchone()[0]

            if not has_pg_stat_statements:
                return {
                    "available": False,
                    "message": "pg_stat_statements extension not installed",
                }

            # Get top slow queries
            cursor.execute("""
                SELECT
                    LEFT(query, 100) as query_preview,
                    calls,
                    ROUND(total_exec_time::numeric, 2) as total_time_ms,
                    ROUND(mean_exec_time::numeric, 2) as mean_time_ms,
                    ROUND(max_exec_time::numeric, 2) as max_time_ms,
                    ROUND(stddev_exec_time::numeric, 2) as stddev_time_ms,
                    rows as total_rows
                FROM pg_stat_statements
                WHERE query NOT LIKE '%pg_stat_statements%'
                ORDER BY mean_exec_time DESC
                LIMIT 10
            """)

            slow_queries = []
            for row in cursor.fetchall():
                slow_queries.append({
                    "query_preview": row[0],
                    "calls": row[1],
                    "total_time_ms": float(row[2]) if row[2] else 0,
                    "mean_time_ms": float(row[3]) if row[3] else 0,
                    "max_time_ms": float(row[4]) if row[4] else 0,
                    "stddev_time_ms": float(row[5]) if row[5] else 0,
                    "total_rows": row[6],
                })

            # Get most called queries
            cursor.execute("""
                SELECT
                    LEFT(query, 100) as query_preview,
                    calls,
                    ROUND(total_exec_time::numeric, 2) as total_time_ms,
                    ROUND(mean_exec_time::numeric, 2) as mean_time_ms
                FROM pg_stat_statements
                WHERE query NOT LIKE '%pg_stat_statements%'
                ORDER BY calls DESC
                LIMIT 10
            """)

            most_called = []
            for row in cursor.fetchall():
                most_called.append({
                    "query_preview": row[0],
                    "calls": row[1],
                    "total_time_ms": float(row[2]) if row[2] else 0,
                    "mean_time_ms": float(row[3]) if row[3] else 0,
                })

            return {
                "available": True,
                "slow_queries": slow_queries,
                "most_called_queries": most_called,
            }

    def detect_bloat(self) -> List[Dict]:
        """Detect table and index bloat.

        Returns:
            List of tables with significant bloat
        """
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    n_dead_tup as dead_tuples,
                    n_live_tup as live_tuples,
                    CASE 
                        WHEN n_live_tup > 0 
                        THEN round((n_dead_tup::float / n_live_tup::float) * 100, 2)
                        ELSE 0 
                    END as bloat_percent,
                    last_vacuum,
                    last_autovacuum
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                    AND n_live_tup > 0
                    AND (n_dead_tup::float / n_live_tup::float) > 0.2
                ORDER BY (n_dead_tup::float / n_live_tup::float) DESC
            """)

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_cache_hit_ratio(self) -> Dict:
        """Get database cache hit ratio.

        Returns:
            Dictionary with cache statistics
        """
        with self.connection.cursor() as cursor:
            # Table cache hit ratio
            cursor.execute("""
                SELECT 
                    sum(heap_blks_read) as heap_read,
                    sum(heap_blks_hit) as heap_hit,
                    CASE 
                        WHEN sum(heap_blks_hit) + sum(heap_blks_read) > 0
                        THEN round(
                            (sum(heap_blks_hit)::float / 
                             (sum(heap_blks_hit) + sum(heap_blks_read))::float) * 100, 
                            2
                        )
                        ELSE 0
                    END as cache_hit_ratio
                FROM pg_statio_user_tables
            """)
            heap_read, heap_hit, cache_ratio = cursor.fetchone()

            # Index cache hit ratio
            cursor.execute("""
                SELECT 
                    sum(idx_blks_read) as idx_read,
                    sum(idx_blks_hit) as idx_hit,
                    CASE 
                        WHEN sum(idx_blks_hit) + sum(idx_blks_read) > 0
                        THEN round(
                            (sum(idx_blks_hit)::float / 
                             (sum(idx_blks_hit) + sum(idx_blks_read))::float) * 100, 
                            2
                        )
                        ELSE 0
                    END as index_cache_hit_ratio
                FROM pg_statio_user_indexes
            """)
            idx_read, idx_hit, idx_cache_ratio = cursor.fetchone()

            return {
                "table_cache_hit_ratio": float(cache_ratio) if cache_ratio else 0,
                "index_cache_hit_ratio": float(idx_cache_ratio) if idx_cache_ratio else 0,
                "heap_blocks_read": heap_read or 0,
                "heap_blocks_hit": heap_hit or 0,
                "index_blocks_read": idx_read or 0,
                "index_blocks_hit": idx_hit or 0,
            }

    def get_blocking_queries(self) -> List[Dict]:
        """Get queries that are blocking other queries.

        Returns:
            List of blocking query information
        """
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    blocked_locks.pid AS blocked_pid,
                    blocked_activity.usename AS blocked_user,
                    blocking_locks.pid AS blocking_pid,
                    blocking_activity.usename AS blocking_user,
                    blocked_activity.query AS blocked_query,
                    blocking_activity.query AS blocking_query,
                    blocked_activity.state AS blocked_state,
                    blocking_activity.state AS blocking_state
                FROM pg_catalog.pg_locks blocked_locks
                JOIN pg_catalog.pg_stat_activity blocked_activity 
                    ON blocked_activity.pid = blocked_locks.pid
                JOIN pg_catalog.pg_locks blocking_locks 
                    ON blocking_locks.locktype = blocked_locks.locktype
                    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
                    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                    AND blocking_locks.pid != blocked_locks.pid
                JOIN pg_catalog.pg_stat_activity blocking_activity 
                    ON blocking_activity.pid = blocking_locks.pid
                WHERE NOT blocked_locks.granted
            """)

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_long_running_queries(self, min_duration_seconds: int = 60) -> List[Dict]:
        """Get queries that have been running for a long time.

        Args:
            min_duration_seconds: Minimum duration in seconds (default: 60)

        Returns:
            List of long-running query information
        """
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    pid,
                    usename,
                    application_name,
                    client_addr,
                    state,
                    query,
                    EXTRACT(EPOCH FROM (now() - query_start))::int AS duration_seconds,
                    query_start
                FROM pg_stat_activity
                WHERE state != 'idle'
                    AND query NOT LIKE '%pg_stat_activity%'
                    AND (now() - query_start) > interval '%s seconds'
                ORDER BY query_start
            """, [min_duration_seconds])

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on analysis.

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Check connection usage
        conn_stats = self.get_connection_stats()
        if conn_stats["connection_usage_percent"] > 80:
            recommendations.append(
                f"⚠ High connection usage ({conn_stats['connection_usage_percent']}%). "
                "Consider implementing connection pooling or increasing max_connections."
            )

        # Check cache hit ratio
        cache_stats = self.get_cache_hit_ratio()
        if cache_stats["table_cache_hit_ratio"] < 90:
            recommendations.append(
                f"⚠ Low table cache hit ratio ({cache_stats['table_cache_hit_ratio']}%). "
                "Consider increasing shared_buffers in PostgreSQL configuration."
            )

        if cache_stats["index_cache_hit_ratio"] < 90:
            recommendations.append(
                f"⚠ Low index cache hit ratio ({cache_stats['index_cache_hit_ratio']}%). "
                "Consider increasing shared_buffers and effective_cache_size."
            )

        # Check for bloat
        bloat = self.detect_bloat()
        if bloat:
            recommendations.append(
                f"⚠ Found {len(bloat)} table(s) with significant bloat. "
                "Run VACUUM ANALYZE on these tables."
            )

        # Check for unused indexes
        unused = self.find_unused_indexes()
        if unused:
            recommendations.append(
                f"⚠ Found {len(unused)} unused or rarely-used index(es). "
                "Consider dropping them to save space and improve write performance."
            )

        # Check for blocking queries
        blocking = self.get_blocking_queries()
        if blocking:
            recommendations.append(
                f"⚠ Found {len(blocking)} blocking query situation(s). "
                "Investigate and resolve query locks."
            )

        # Check table statistics
        tables = self.get_table_statistics(limit=10)
        for table in tables:
            if table["dead_row_percent"] > 20:
                recommendations.append(
                    f"⚠ Table {table['tablename']} has {table['dead_row_percent']}% dead rows. "
                    "Run VACUUM ANALYZE."
                )
            if table["index_usage_percent"] < 50 and table["idx_scan"] + table["seq_scan"] > 1000:
                recommendations.append(
                    f"⚠ Table {table['tablename']} has low index usage ({table['index_usage_percent']}%). "
                    "Consider adding indexes on frequently queried columns."
                )

        if not recommendations:
            recommendations.append("✓ No critical issues detected. Database appears healthy.")

        return recommendations
