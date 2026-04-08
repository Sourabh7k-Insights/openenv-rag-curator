# Pre-Submission Deployment Checklist

## CRITICAL - Must Complete Before Submission

### 1. Deploy to Hugging Face Spaces
- [ ] Create a new Space on HuggingFace
- [ ] Name it: `openenv-rag-curator` (or your preferred name)
- [ ] Tag it with: `openenv`
- [ ] Push your code to the Space
- [ ] Verify the Space is running (green status)

### 2. Test the Deployment
```bash
# Replace with your actual Space URL
export SPACE_URL="https://YOUR_USERNAME-openenv-rag-curator.hf.space"

# Test health endpoint
curl $SPACE_URL/health

# Test reset endpoint (REQUIRED by pre-validation)
curl -X POST $SPACE_URL/reset/task_0
```

### 3. Update openenv.yaml
- [ ] Open `openenv.yaml`
- [ ] Replace `repository: "https://huggingface.co/spaces/YOUR_HF_USERNAME/openenv-rag-curator"`
- [ ] With your actual Space URL: `repository: "https://huggingface.co/spaces/YOUR_USERNAME/openenv-rag-curator"`

### 4. Run Pre-Validation Script
The hackathon provides a pre-validation script. Run it:
```bash
# Set your Space URL
export PING_URL="https://YOUR_USERNAME-openenv-rag-curator.hf.space"

# Run the validation script (provided by hackathon organizers)
./validate.sh
```

Expected checks:
- ✓ HF Space /reset returns HTTP 200
- ✓ Docker build succeeds
- ✓ openenv validate passes

### 5. Test Inference Script End-to-End
```bash
# Set environment variables
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="your_hf_token"
export ENV_BASE_URL="https://YOUR_USERNAME-openenv-rag-curator.hf.space"

# Run inference
python inference.py
```

Verify:
- [ ] [START] logs appear for each task
- [ ] [STEP] logs show actions and rewards
- [ ] [END] logs show final scores
- [ ] All 3 tasks complete without errors
- [ ] Runtime < 20 minutes

### 6. Document Baseline Scores
After running inference.py successfully, record the actual scores in README.md:
- [ ] Task 0 score: _____
- [ ] Task 1 score: _____
- [ ] Task 2 score: _____
- [ ] Average score: _____

### 7. Final Checks
- [ ] All code committed and pushed to HF Space
- [ ] README.md has complete documentation
- [ ] openenv.yaml has correct repository URL
- [ ] Dockerfile builds successfully
- [ ] inference.py runs without errors
- [ ] Space is publicly accessible
- [ ] No placeholder values remain in code

## Common Issues

### Space won't start
- Check Dockerfile syntax
- Verify port 7860 is exposed
- Check requirements.txt for version conflicts
- Look at Space logs for errors

### /reset returns 404
- Verify server.py is running
- Check FastAPI routes are registered
- Test locally first: `uvicorn server:app --port 7860`

### inference.py fails
- Verify API_BASE_URL, MODEL_NAME, HF_TOKEN are set
- Check ENV_BASE_URL points to your Space
- Test with local server first

### Docker build fails
- Check Python version compatibility
- Verify all dependencies in requirements.txt
- Test build locally: `docker build -t test .`

## Resources
- OpenEnv Docs: https://openenv.dev
- HF Spaces Docs: https://huggingface.co/docs/hub/spaces
- Hackathon Discord: [link from organizers]
