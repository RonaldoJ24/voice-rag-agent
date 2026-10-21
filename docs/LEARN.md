# Hands-on guide: the AWS parts worth learning

Claude builds the server, the evals and the deployment scripts. These steps are the ones worth doing yourself, because they come up in interviews: signing in safely, how Bedrock gives you models, and how a vector index works on AWS. Each takes about 5 minutes. Run the commands in your own terminal, then tell Claude what you saw.

## 0. Free plan rules (read once)

- Your account is on the **Free plan**: $100 of credits, 183 days (until Apr 20, 2027). When either runs out, AWS suspends the account instead of charging you.
- **Never click "Upgrade plan."** It can't be undone, and from then on usage is billed to your card.
- The project only uses services that credits cover: Bedrock's Amazon models (Titan embeddings), S3 Vectors, S3, Lambda and DynamoDB. Claude runs on your Anthropic key, not on Bedrock. Third-party models on Bedrock are billed through AWS Marketplace, which credits probably don't cover.

## 1. Sign the CLI in without access keys

Long-lived access keys are the most common way AWS accounts leak. `aws login` reuses your browser console session and gives the CLI short-lived credentials instead.

```bash
aws login --region us-east-1
```

A browser tab opens. Approve it, then check who the CLI thinks you are:

```bash
aws sts get-caller-identity
```

You should see your 12-digit account ID and an ARN. **Why us-east-1:** your console opened in us-east-2 (Ohio), but us-east-1 (N. Virginia) gets new Bedrock models and S3 Vectors first, and that's where this project lives. In the console, switch the region at the top right when you look at these services.

**Interview takeaway:** "I use short-lived credentials from `aws login` or IAM Identity Center, never root access keys."

## 2. Bedrock: call a model from the CLI

Bedrock is AWS's catalog of hosted models behind one API. Three ideas matter:

- **Model ID vs inference profile.** Amazon's own models are called by model ID (`amazon.titan-embed-text-v2:0`). Newer third-party models are called through an inference profile such as `us.anthropic.claude-haiku-5-5`, which routes across regions.
- **Access.** Amazon models are open by default. Third-party models subscribe you through AWS Marketplace on first use, which is a separate bill.
- **Two APIs.** `bedrock` manages things (list models, knowledge bases). `bedrock-runtime` runs inference.

List the Amazon embedding models:

```bash
aws bedrock list-foundation-models --region us-east-1 --by-provider amazon \
  --query "modelSummaries[?contains(modelId, 'embed')].modelId"
```

Turn a Spanish sentence into a 256-number vector with Titan Text Embeddings V2:

```bash
aws bedrock-runtime invoke-model --region us-east-1 \
  --model-id amazon.titan-embed-text-v2:0 \
  --cli-binary-format raw-in-base64-out \
  --body '{"inputText":"¿Cómo subo archivos en FastAPI?","dimensions":256,"normalize":true}' \
  /tmp/titan.json && python3 -c "import json; e=json.load(open('/tmp/titan.json'))['embedding']; print(len(e), e[:3])"
```

Expected: `256` and three small numbers. **If you get `ValidationException: Operation not allowed`, the Free plan is blocking Bedrock.** Tell Claude. The project then keeps the local index, and Bedrock stays off the CV.

**Interview takeaway:** an embedding turns text into a vector so that similar meanings land close together. That's how a Spanish question can find an English page.

## 3. S3 Vectors: a vector index with no servers

S3 Vectors stores embeddings in a special S3 bucket and answers "find the nearest vectors" queries. You pay per GB stored and per query, with no always-on cluster. That's why we use it instead of OpenSearch Serverless, which costs about $175 a month even when idle.

Pick a short unique suffix (your initials plus 4 digits), then:

```bash
aws s3vectors create-vector-bucket --region us-east-1 --vector-bucket-name fastapi-docs-vectors-SUFFIX

aws s3vectors create-index --region us-east-1 --vector-bucket-name fastapi-docs-vectors-SUFFIX \
  --index-name docs-titan-v2-256 --data-type float32 --dimension 256 --distance-metric cosine

aws s3vectors list-indexes --region us-east-1 --vector-bucket-name fastapi-docs-vectors-SUFFIX
```

Tell Claude the bucket name. Claude will write the script that embeds every docs chunk with Titan and uploads it, then compares that index with the local one on the same questions.

**Interview takeaway:** the dimension (256) and the distance metric (cosine) are fixed when the index is created, and they have to match the embedding model you query with.

## 4. How the Lambda deploy works (read, about 5 minutes)

Claude runs `scripts/deploy.sh` once your CLI is signed in. These are the pieces of `infra/template.yaml` worth being able to explain:

- **Lambda Web Adapter.** A layer that runs `run.sh`, which starts uvicorn, and forwards each Lambda request to it as normal HTTP. The FastAPI app runs unchanged, with no Mangum handler and no code written for Lambda.
- **Function URL with `InvokeMode: RESPONSE_STREAM`.** A public HTTPS endpoint without API Gateway. Streaming matters here: ElevenLabs starts speaking on the first tokens, and API Gateway REST APIs buffer the whole response.
- **DynamoDB for state.** Each request can land on a different Lambda instance, so trace events and the spend total can't stay in memory. One table with 5 read and 5 write units stays inside the always-free tier.
- **SSM Parameter Store for secrets.** `scripts/push_secrets.py` stores the API keys as SecureStrings, and the function reads them at cold start. They never appear in the template, CloudFormation outputs, or the Lambda console's environment tab.
- **Least-privilege IAM.** The function role can read only its own parameters, write only its table, call only the Titan embedding model, and query only S3 Vectors.
- **A fallback that doesn't depend on Bedrock.** `Retriever=bm25` (the default) needs nothing beyond the bundle and scored recall@5 0.92 against 0.94 for the hybrid. `Retriever=aws` switches to Titan and S3 Vectors after step 2 works.
- **Spend guard.** The deployed demo stops calling Claude after $5 (`SpendPauseUsd`), and visitors need the demo code that `push_secrets.py` writes to `.env`.

To look at it yourself after a deploy:

```bash
aws cloudformation describe-stacks --stack-name voice-rag-agent --region us-east-1 --query "Stacks[0].Outputs"
```

```bash
aws logs tail /voice-rag-agent/proxy --region us-east-1 --since 10m
```

**Interview takeaway:** "Stateless compute, state in DynamoDB, secrets in Parameter Store, streaming through a Function URL, and a cost ceiling enforced in code" is the whole architecture in one sentence.

## 5. What Claude handles (skim, no action)

- `src/voice_rag_agent/`: the FastAPI proxy ElevenLabs calls, the agent loop, retrievers and trace events.
- `scripts/`: corpus build, index build, ElevenLabs agent setup, Lambda packaging and deploy.
- `infra/`: the SAM template described in section 4.
