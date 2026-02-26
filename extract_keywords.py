#!/usr/bin/env python3
"""Extract main topic and keywords from markdown questions using Bedrock."""
import fire
import re
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def extract_keywords(filename: str, batch_size: int = 15):
    """Extract main topic and keywords for each question in markdown file.
    
    Args:
        filename: Name of the file (e.g., 'Vladimir-Raykov-udemy-4')
        batch_size: Number of questions to process per API call (default: 15)
    """
    # Get GNL_PROCESSING_PATH from environment
    gnl_processing_path = os.getenv('GNL_PROCESSING_PATH')
    if not gnl_processing_path:
        raise ValueError("GNL_PROCESSING_PATH not found in .env file")
    
    base_path = Path(gnl_processing_path).parent
    
    # Build path to markdown file
    markdown_file = base_path / "Anki-generation" / "markdown" / f"{filename}.md"
    
    if not markdown_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_file}")
    
    print(f"Processing: {markdown_file}")
    
    # Read markdown
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Get Bedrock config
    model_id = os.getenv('MOEDL_INFERENCE_ID', 'global.anthropic.claude-opus-4-5-20251101-v1:0')
    api_key = os.getenv('AWS_BEARER_TOKEN_BEDROCK', '')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    if not api_key:
        raise Exception("AWS_BEARER_TOKEN_BEDROCK not found in .env file")
    
    # Split by questions
    question_blocks = re.split(r'(\*\*Question\s+\d+:\*\*)', content)
    
    questions = []
    for i in range(1, len(question_blocks), 2):
        if i + 1 >= len(question_blocks):
            break
        
        question_header = question_blocks[i]
        question_content = question_blocks[i + 1]
        question_block = question_header + question_content
        
        if question_block.strip():
            questions.append(question_block)
    
    print(f"Found {len(questions)} questions. Processing in batches of {batch_size}...")
    
    all_results = []
    
    # Process in batches
    for batch_start in range(0, len(questions), batch_size):
        batch_end = min(batch_start + batch_size, len(questions))
        batch = questions[batch_start:batch_end]
        
        print(f"Processing questions {batch_start + 1}-{batch_end}...")
        
        # Combine batch into single prompt
        batch_text = "\n\n---\n\n".join(batch)
        
        prompt = f"""Extract the main topic and keywords for EACH question below.

{batch_text}

For EACH question, output in this exact format:
**Question N:**
Main Topic: [single concise topic]
Keywords:
[keyword 1]
[keyword 2]
...

Rules:
- Main topic should be 2-5 words describing the primary subject
- Keywords should be specific technical terms, services, or concepts
- List 5-10 keywords, one per line
- Process ALL questions in the batch"""
        
        # Call Bedrock API
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": {
                "maxTokens": 16000,
                "temperature": 0.1
            }
        }
        
        url = f"https://bedrock-runtime.{aws_region}.amazonaws.com/model/{model_id}/converse"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            extracted = result['output']['message']['content'][0]['text']
            all_results.append(extracted)
        else:
            print(f"  Error: {response.status_code} - {response.text}")
            all_results.append(f"Error processing batch {batch_start + 1}-{batch_end}")
    
    # Save results
    output_dir = base_path / "KeyWords-extraction"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"keywords_{filename}.md"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(all_results))
    
    print(f"\n✓ Keywords extracted and saved to: {output_file}")


if __name__ == "__main__":
    fire.Fire(extract_keywords)
