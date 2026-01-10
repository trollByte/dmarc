# Bulk DMARC Report Import

This directory is used for bulk importing large batches of DMARC reports (1000-5000+).

## Quick Start

### 1. Copy Your Report Files Here

```bash
# Copy all DMARC reports to this directory
cp /path/to/your/reports/*.xml ./import_reports/
cp /path/to/your/reports/*.gz ./import_reports/
```

### 2. Run the Bulk Import Script

**Option A: Async Import with Celery (Recommended for 1000+ files)**
```bash
docker compose exec backend python scripts/bulk_import.py
```

**Option B: Synchronous Import (Better for <100 files)**
```bash
docker compose exec backend python scripts/bulk_import.py --sync
```

**Option C: Import from Custom Directory**
```bash
docker compose exec backend python scripts/bulk_import.py /app/import_reports --batch-size 50
```

### 3. Monitor Progress

- **Async Mode:** Visit Flower dashboard at http://localhost:5555
- **Sync Mode:** Progress updates shown in terminal

## Supported File Formats

- `*.xml` - Raw XML DMARC reports
- `*.gz` - Gzipped XML reports (auto-decompressed)
- `*.gzip` - Gzipped XML reports
- `*.zip` - Zipped reports (future support)

## Performance

| Files | Method | Expected Time |
|-------|--------|---------------|
| <100 | Sync | 5-10 minutes |
| 100-1000 | Async | 10-20 minutes |
| 1000-5000 | Async | 20-60 minutes |
| 5000+ | Async | 1-3 hours |

**Note:** Performance depends on:
- Report complexity (number of records per report)
- System resources (CPU, RAM)
- Celery worker concurrency (default: 4)

## Script Options

```bash
python scripts/bulk_import.py --help

Options:
  directory           Directory with reports (default: /app/import_reports)
  --sync              Use synchronous mode (no Celery)
  --batch-size N      Progress update frequency (default: 100)
```

## Troubleshooting

### "Directory not found"
Make sure Docker volume is mounted:
```bash
docker compose down
docker compose up -d
```

### Slow Import Speed
Increase Celery worker concurrency in `docker-compose.yml`:
```yaml
celery-worker:
  command: celery -A celery_worker worker --loglevel=info --concurrency=8
```

### Out of Memory
Reduce concurrency or use sync mode with smaller batches.

### Duplicate Reports
The system automatically detects and skips duplicate reports based on `report_id`.

## After Import

### Check Import Status
```bash
# View recent imports
docker compose exec backend python -c "
from app.database import SessionLocal
from app.models import DmarcReport
db = SessionLocal()
print(f'Total reports: {db.query(DmarcReport).count()}')
"
```

### Clean Up
```bash
# Remove imported files (optional)
rm -rf ./import_reports/*.xml
rm -rf ./import_reports/*.gz
```

## Example Workflow

```bash
# 1. Copy 5000 DMARC reports
cp ~/dmarc_archive/*.xml.gz ./import_reports/

# 2. Start bulk import
docker compose exec backend python scripts/bulk_import.py

# Output:
# Found 5000 report files in /app/import_reports
# Import 5000 files? This may take a while. [y/N]: y
#
# ============================================================
# Starting ASYNC import of 5000 files
# ============================================================
#
# ⏳ Queued [100/5000] report_2024_01_15.xml.gz (50.2 files/sec)
# ⏳ Queued [200/5000] report_2024_01_16.xml.gz (51.8 files/sec)
# ...
#
# ============================================================
# Queueing Complete!
# ============================================================
# Total files:      5000
# ⏳ Queued:         5000
# ✗ Queue errors:   0
# Time elapsed:     96.5 seconds
# ============================================================
#
# 📊 Monitor processing at: http://localhost:5555

# 3. Monitor in Flower dashboard
open http://localhost:5555

# 4. Check dashboard
open http://localhost
```

## Notes

- Files are **not** automatically deleted after import
- Duplicate reports are automatically detected and skipped
- Import can be interrupted with `Ctrl+C` (queued tasks will continue)
- For very large imports (10,000+), consider splitting into batches
