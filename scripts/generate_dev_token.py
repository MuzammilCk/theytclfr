import os
import sys
from datetime import datetime, timedelta, timezone

# Add the src directory to path so we can import ytclfr config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from ytclfr.core.config import get_settings
from jose import jwt

def generate_dev_token():
    settings = get_settings()
    
    # Payload similar to what Supabase would provide
    payload = {
        "sub": "dev-user-id-123",
        "role": "authenticated",
        "email": "dev@example.com",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes),
        "iat": datetime.now(timezone.utc),
    }
    
    token = jwt.encode(
        payload, 
        settings.jwt_secret_key, 
        algorithm=settings.jwt_algorithm
    )
    
    print("\n" + "="*50)
    print("YOUR LOCAL DEV BEARER TOKEN:")
    print("="*50)
    print(token)
    print("="*50 + "\n")
    print("Copy the token above and paste it into the Swagger UI Authorize modal.")

if __name__ == "__main__":
    generate_dev_token()
