import time
import requests
from jose import jwt

API_URL = "http://localhost:8000/api/v1"
JWT_SECRET_KEY = "ytclfr-local-dev-secret-key-change-me-in-production"
JWT_ALGORITHM = "HS256"

def get_auth_headers():
    payload = {
        "sub": "test_user",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "jti": "test-jti",
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}

def submit_job(url: str):
    response = requests.post(f"{API_URL}/jobs", json={"youtube_url": url}, headers=get_auth_headers())
    response.raise_for_status()
    data = response.json()
    return data["job_id"]

def check_status(job_id: str):
    response = requests.get(f"{API_URL}/jobs/{job_id}", headers=get_auth_headers())
    response.raise_for_status()
    return response.json()

def get_results(job_id: str):
    response = requests.get(f"{API_URL}/jobs/{job_id}/result", headers=get_auth_headers())
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

def run_test():
    # A short video for quick testing
    test_video = "https://www.youtube.com/watch?v=jNQXAC9IVRw" # Me at the zoo
    
    print(f"Submitting job for {test_video}...")
    try:
        job_id = submit_job(test_video)
        print(f"Job ID: {job_id}")
    except Exception as e:
        print(f"Failed to submit: {e}")
        return

    while True:
        try:
            status = check_status(job_id)
            state = status.get("status")
            print(f"Current state: {state}")
            
            if state in ["completed", "failed", "dead_letter"]:
                break
        except Exception as e:
            print(f"Error checking status: {e}")
        time.sleep(5)
        
    print(f"Final status: {status}")
    if state == "completed":
        print("Fetching results...")
        try:
            results = get_results(job_id)
            print("Results retrieved successfully.")
            import json
            print(json.dumps(results, indent=2))
        except Exception as e:
            print(f"Failed to fetch results: {e}")

if __name__ == "__main__":
    run_test()
