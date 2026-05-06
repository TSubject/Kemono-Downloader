import requests
import json

def fetch_nhentai_gallery(gallery_id, logger=print, proxies=None):
    """
    Fetches the metadata for a single nhentai gallery using the v2 API.
    """
    # Updated to the new v2 endpoint
    api_url = f"https://nhentai.net/api/v2/galleries/{gallery_id}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*' # Updated to accept JSON primarily
        # IMPORTANT: If this endpoint requires the API key you generated earlier, 
        # add it here like: 'Authorization': 'Bearer YOUR_API_KEY' or 'x-api-key': 'YOUR_KEY'
    }
    
    logger(f"   Fetching nhentai gallery metadata from: {api_url}")

    req_timeout = (30, 120) if proxies else 20

    try:
        # Note: If cookies are still required, you must pass them here using your network_utils
        response = requests.get(api_url, headers=headers, timeout=req_timeout, proxies=proxies, verify=False)
        
        if response.status_code == 404:
            logger(f"   ❌ Gallery not found (404): ID {gallery_id}")
            return None
        elif response.status_code == 403:
            logger(f"   ❌ Access Denied (403): Cloudflare or API Key blocked the request.")
            return None
            
        response.raise_for_status()

        gallery_data = response.json()
        
        # Validating against the new v2 structure (id, media_id, and pages)
        if "id" in gallery_data and "media_id" in gallery_data and "pages" in gallery_data:
            logger(f"   ✅ Successfully fetched metadata for '{gallery_data['title']['english']}'")
            # We no longer need to pop 'images', 'pages' is already at the root
            return gallery_data
        else:
            logger("   ❌ API response is missing essential keys (id, media_id, pages).")
            return None

    except Exception as e:
        logger(f"   ❌ Error fetching nhentai metadata: {e}")
        return None