import httpx 
from decouple import config

class OpenAIClient:
    base_url = config('OPENAI_BASE_URL')
    def __init__(self):
        self.headers = {
            "Authorization":f"Bearer {config('OPENAI_API_KEY')}",
            "Content-Type": "application/json",
        }

    async def generate_post(self, prompt:str) -> str:
        payload = {
            "model":"gpt-4o-mini",
            "messages":[
                {
                    "role":"system", "content":"You write professional human like LinkedIn posts"
                },
                {
                    "role": "user", "content":prompt
                }               
            ] ,
            "temperature":0.7,
        }   

        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(self.base_url, json=payload, headers=self.headers)
            res.raise_for_status()

            return res.json()["choices"][0]["message"]["content"]    
        
        ###############################################
        ##                  USAGE                    ##

        # from apps.integrations.openai.client import OpenAIClient

        # openai_client = OpenAIClient()
        # content = await openai_client.generate_post(
        #     "Write a short LinkedIn post about building scalable Django apps."
        # )