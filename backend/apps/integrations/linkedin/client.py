import httpx 
from decouple import config

class LinkedinClient:
    base_url = config('LINKEDIN_BASE_URL', default="https://api.linkedin.com/v2")

    def __init__(self, access_token:str):
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }

    def post_text_sync(self, author_urn: str, text: str) -> str:
        """
        Synchronous method to post text to LinkedIn.
        Used by Celery tasks.
        
        Args:
            author_urn: The URN of the author (e.g., urn:li:person:XXXX)
            text: The text content to post
            
        Returns:
            The external post ID from LinkedIn
        """
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent":{
                    "shareCommentary":{"text":text},
                    "shareMediaCategory":"NONE",
                }
            },
            "visibility":{
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }    

        with httpx.Client(timeout=10) as client:
            res = client.post(
                f"{self.base_url}/ugcPosts",
                json=payload,
                headers=self.headers,   
            )    
            res.raise_for_status()
            return res.headers.get("x-restli-id")

    async def post_text(self, author_urn:str, text:str) -> str:
        """
        Asynchronous method to post text to LinkedIn.
        Used by async views and services.
        
        Args:
            author_urn: The URN of the author
            text: The text content to post
            
        Returns:
            The external post ID from LinkedIn
        """
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent":{
                    "shareCommentary":{"text":text},
                    "shareMediaCategory":"NONE",
                }
            },
            "visibility":{
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }    

        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                f"{self.base_url}/ugcPosts",
                json=payload,
                headers=self.headers,   
            )    
            res.raise_for_status()
            return res.headers.get("x-restli-id")
