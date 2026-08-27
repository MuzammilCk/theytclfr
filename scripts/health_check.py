"""System health check for ytclfr pipeline."""
import sys

print("=" * 60)
print("  ytclfr Pipeline Health Check")
print("=" * 60)

# 1. Config
print("\n--- Configuration ---")
from ytclfr.core.config import get_settings
s = get_settings()
print(f"  Database URL:  {s.database_url[:40]}...")
print(f"  Redis URL:     {s.redis_url}")
print(f"  Groq API Key:  {'SET' if s.groq_api_key else 'MISSING'}")
print(f"  Groq Model:    {s.groq_model}")
print(f"  JWT Secret:    {'SET' if s.jwt_secret_key else 'MISSING'}")

# 2. PostgreSQL
print("\n--- PostgreSQL ---")
try:
    from sqlalchemy import create_engine, text
    engine = create_engine(s.database_url)
    with engine.connect() as conn:
        r = conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"))
        table_count = r.scalar()
        r2 = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"))
        tables = [row[0] for row in r2]
        print(f"  Status:        CONNECTED")
        print(f"  Public tables: {table_count}")
        for t in tables:
            r3 = conn.execute(text(f"SELECT count(*) FROM \"{t}\""))
            print(f"    {t:40s} {r3.scalar()} rows")
except Exception as e:
    print(f"  Status:        FAILED - {e}")

# 3. Redis
print("\n--- Redis ---")
try:
    import redis
    r = redis.Redis.from_url(s.redis_url)
    r.ping()
    print(f"  Status:        CONNECTED")
    print(f"  Total keys:    {r.dbsize()}")
except Exception as e:
    print(f"  Status:        FAILED - {e}")

# 4. Ollama
print("\n--- Ollama ---")
try:
    import httpx
    resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
    models = resp.json().get("models", [])
    print(f"  Status:        CONNECTED")
    for m in models:
        name = m["name"]
        size_mb = m["size"] // (1024 * 1024)
        print(f"    {name:35s} {size_mb} MB")
except Exception as e:
    print(f"  Status:        FAILED - {e}")

# 5. Faster-whisper
print("\n--- faster-whisper (ASR) ---")
try:
    import faster_whisper
    print(f"  Version:       {faster_whisper.__version__}")
    print(f"  Status:        AVAILABLE")
except ImportError:
    print(f"  Status:        NOT INSTALLED")

# 6. Python
print("\n--- Python ---")
print(f"  Version:       {sys.version.split()[0]}")
print(f"  Executable:    {sys.executable}")

print("\n" + "=" * 60)
print("  Health check complete.")
print("=" * 60)
