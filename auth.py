import time, os
from jose import jwt
from dotenv import load_dotenv

load_dotenv()
secret = os.getenv('JWT_SECRET_KEY')

payload = {
    'sub': 'admin',
    'iat': int(time.time()),
    'exp': int(time.time()) + 86400  # valid for 24 hours
}

if secret:
    token = jwt.encode(payload, secret, algorithm='HS256')
    print('\nYOUR ADMIN TOKEN:\n' + token + '\n')
else:
    print("\nERROR: JWT_SECRET_KEY not found in .env file!\n")
