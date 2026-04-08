"""
Quick test script to find working HuggingFace Inference API models
"""
import os
import httpx

HF_TOKEN = os.environ.get("HF_TOKEN", "")

if not HF_TOKEN:
    print("ERROR: Set HF_TOKEN environment variable")
    exit(1)

# Models to test
models = [
    "Qwen/Qwen2.5-Coder-3B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.2",
    "HuggingFaceH4/zephyr-7b-beta",
    "tiiuae/falcon-7b-instruct",
    "google/flan-t5-base",
    "bigcode/starcoder2-3b",
    "microsoft/phi-2",
]

print("Testing HuggingFace Inference API models...")
print("=" * 60)

working_models = []

for model in models:
    print(f"\nTesting: {model}")
    try:
        # Try old endpoint first
        response = httpx.post(
            f"https://api-inference.huggingface.co/models/{model}",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={
                "inputs": "Hello, respond with 'OK'",
                "parameters": {
                    "max_new_tokens": 10,
                    "temperature": 0.1,
                }
            },
            timeout=30,
        )
        
        if response.status_code == 410:
            print(f"  ⚠️  Old API deprecated, trying new router...")
            # Try new router endpoint
            response = httpx.post(
                f"https://router.huggingface.co/models/{model}",
                headers={"Authorization": f"Bearer {HF_TOKEN}"},
                json={
                    "inputs": "Hello, respond with 'OK'",
                    "parameters": {
                        "max_new_tokens": 10,
                        "temperature": 0.1,
                    }
                },
                timeout=30,
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ SUCCESS: {result}")
            working_models.append(model)
        elif response.status_code == 503:
            print(f"  ⏳ LOADING: Model is loading (try again in 20s)")
        else:
            print(f"  ❌ FAILED: HTTP {response.status_code}")
            print(f"     {response.text[:200]}")
    except Exception as e:
        print(f"  ❌ ERROR: {e}")

print("\n" + "=" * 60)
print(f"\nWorking models ({len(working_models)}):")
for model in working_models:
    print(f"  ✅ {model}")

if working_models:
    print(f"\n💡 Use this command:")
    print(f'   set MODEL_NAME={working_models[0]}')
    print(f'   python inference.py')
else:
    print("\n⚠️  No models available. Try again in 20 seconds (models may be loading)")
