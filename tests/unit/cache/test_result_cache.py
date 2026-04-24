import uuid
import json
from ytclfr.cache.result_cache import get_cached_result, cache_result, invalidate_result

def test_cache_operations(mocker):
    mock_redis = mocker.patch("ytclfr.cache.result_cache._get_redis")
    client = mock_redis.return_value
    
    job_id = uuid.uuid4()
    result = {"test": "data"}
    
    # test get (miss)
    client.get.return_value = None
    assert get_cached_result(job_id) is None
    
    # test cache
    cache_result(job_id, result, 3600)
    client.set.assert_called_once()
    
    # test get (hit)
    client.get.return_value = json.dumps(result)
    assert get_cached_result(job_id) == result
    
    # test invalidate
    invalidate_result(job_id)
    client.delete.assert_called_once()
