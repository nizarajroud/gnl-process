#!/usr/bin/env python3
"""Extract main topic and keywords from markdown questions using Bedrock."""
import fire
import re
import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
from notion_client import Client

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
Main Idea Problem: [brief generic description of the problem/requirement]
Main Idea Solution: [brief generic description of the solution approach]
Main Topic: [single concise topic]
Keywords:
[keyword 1]
[keyword 2]
...

Rules:
- Main idea problem should be a brief, generic statement of what needs to be achieved or the challenge
- Main idea solution should be a brief, generic statement of the approach or solution
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
    
    # Upload to Notion
    notion_api_key = os.getenv('NOTION_API_KEY')
    notion_page_id = os.getenv('NOTION_PAGE_ID')
    
    if notion_api_key and notion_page_id:
        print(f"\nUploading to Notion...")
        upload_to_notion(all_results, notion_api_key, notion_page_id, filename)
        print(f"✓ Content uploaded to Notion page")
    else:
        print(f"\n⚠ Skipping Notion upload (NOTION_API_KEY or NOTION_PAGE_ID not set)")


def upload_to_notion(results: list, api_key: str, page_id: str, filename: str):
    """Upload extracted keywords to Notion page."""
    notion = Client(auth=api_key)
    
    blocks = []
    
    # Parse each batch result and collect content blocks
    content_blocks = []
    for batch_result in results:
        # Split by question blocks
        question_sections = re.split(r'(\*\*Question\s+\d+:\*\*)', batch_result)
        
        for i in range(1, len(question_sections), 2):
            if i + 1 >= len(question_sections):
                break
            
            question_header = question_sections[i]
            question_content = question_sections[i + 1]
            
            # Extract question number
            q_match = re.match(r'\*\*Question\s+(\d+):\*\*', question_header)
            if not q_match:
                continue
            
            question_num = q_match.group(1)
            
            # Parse content
            lines = [l.strip() for l in question_content.strip().split('\n') if l.strip()]
            
            main_idea_problem = ""
            main_idea_solution = ""
            main_topic = ""
            keywords = []
            
            in_keywords = False
            for line in lines:
                if line.startswith('Main Idea Problem:'):
                    main_idea_problem = line.replace('Main Idea Problem:', '').strip()
                elif line.startswith('Main Idea Solution:'):
                    main_idea_solution = line.replace('Main Idea Solution:', '').strip()
                elif line.startswith('Main Topic:'):
                    main_topic = line.replace('Main Topic:', '').strip()
                elif line == 'Keywords:':
                    in_keywords = True
                elif in_keywords and line:
                    keywords.append(line)
            
            # Add question with main topic (bold)
            content_blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"Question {question_num}: {main_topic}"},
                        "annotations": {"bold": True}
                    }]
                }
            })
            
            # Add main idea problem as bulleted list item (italic)
            if main_idea_problem:
                content_blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": main_idea_problem},
                            "annotations": {"italic": True}
                        }]
                    }
                })
            
            # Add main idea solution as bulleted list item (italic with arrow)
            if main_idea_solution:
                content_blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": f"⇒ {main_idea_solution}"},
                            "annotations": {"italic": True}
                        }]
                    }
                })
            
            # Add keywords as to-do list
            if keywords:
                for keyword in keywords:
                    content_blocks.append({
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [{
                                "type": "text",
                                "text": {"content": keyword}
                            }],
                            "checked": False
                        }
                    })
    
    # Create toggle with filename containing all content
    toggle_block = {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{
                "type": "text",
                "text": {"content": filename},
                "annotations": {"bold": True}
            }],
            "children": content_blocks[:100]  # Notion limit: 100 children per block
        }
    }
    
    # Append toggle to page
    response = notion.blocks.children.append(block_id=page_id, children=[toggle_block])
    
    # If more than 100 content blocks, append remaining to the toggle
    if len(content_blocks) > 100:
        toggle_id = response['results'][0]['id']
        for i in range(100, len(content_blocks), 100):
            batch = content_blocks[i:i+100]
            notion.blocks.children.append(block_id=toggle_id, children=batch)


if __name__ == "__main__":
    fire.Fire(extract_keywords)
