import subprocess
import sys

urls = [
    "https://docs.aws.amazon.com/pdfs/solutions/latest/clickstream-analytics-on-aws/clickstream-analytics-on-aws.pdf#solution-overview",
    "https://docs.aws.amazon.com/pdfs/solutions/latest/prebid-server-deployment-on-aws/prebid-server-deployment-on-aws.pdf#solution-overview",
    "https://docs.aws.amazon.com/pdfs/solutions/latest/video-on-demand-on-aws-foundation/video-on-demand-on-aws-foundation.pdf#solution-overview"
]

for url in urls:
    print(f"Processing: {url}")
    result = subprocess.run([sys.executable, "nllm-aws-asl-add-generate-gnl.py", url], check=False)
    print(f"Completed: {url} (exit code: {result.returncode})\n")
