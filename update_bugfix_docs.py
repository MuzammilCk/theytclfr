import datetime
import os

date_str = datetime.datetime.now().strftime('%Y-%m-%d')
diff_entry = f"""

### {date_str}: Post-Wave Alembic Migration Fix
Files changed: alembic/versions/0013_add_pipeline_version.py, alembic/versions/3019f6d173fb_restore_search_indexes.py

Summary:
  - Reparented migration `0013` to point to `3019f6d173fb` to fix an Alembic "multiple heads" conflict caused by parallel feature development.
  - Fixed a `psycopg2.errors.UndefinedColumn` SQL bug in `3019f6d173fb_restore_search_indexes.py` by correcting the GIN index target column from `segment_text` to the actual column name `text`.
  - Successfully executed `alembic upgrade head` to apply both the Wave 1 search index restoration and the Wave 3/4 pipeline versioning columns.
"""

build_entry = f"""
### {date_str}: Fixed Alembic Migration Divergence and SQL Bug
- Resolved multiple heads conflict between Wave 1 (`3019f6d173fb`) and Wave 3/4 (`0013`) migrations by reparenting `0013`'s `down_revision`.
- Fixed a silent SQL `ProgrammingError` in `3019f6d173fb_restore_search_indexes.py` where `segment_text` was incorrectly referenced instead of the correct `text` column in `aligned_segments`.
- Database is now successfully upgraded to `0013` head.
"""

def append_safe(file, text):
    if os.path.exists(file):
        with open(file, 'ab') as f:
            f.write(text.encode('utf-8'))
    else:
        print(f"Warning: {file} not found.")

append_safe('diff.md', diff_entry)
append_safe('build.md', build_entry)

print("Bugfix documentation successfully appended to diff.md and build.md.")
