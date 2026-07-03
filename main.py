print(8)

import os

api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    print("GEMINI_API_KEY 로드됨")
    print("길이:", len(api_key))
else:
    print("GEMINI_API_KEY 없음 (None)")
