#!/usr/bin/env python3
"""Reorganize Notion page to separate questions and keywords into different toggles."""
import os
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()


def reorganize_notion_page():
    """Reorganize Notion page: create two toggles - one for questions, one for keywords."""
    notion_api_key = os.getenv('NOTION_API_KEY')
    page_id = os.getenv('NOTION_PAGE_ID')
    
    if not all([notion_api_key, page_id]):
        raise ValueError("Missing environment variables. Need: NOTION_API_KEY, NOTION_PAGE_ID")
    
    notion = Client(auth=notion_api_key)
    
    print("Reading page...")
    
    # Get all blocks from page
    blocks = []
    has_more = True
    start_cursor = None
    
    while has_more:
        response = notion.blocks.children.list(
            block_id=page_id,
            start_cursor=start_cursor
        )
        blocks.extend(response['results'])
        has_more = response['has_more']
        start_cursor = response.get('next_cursor')
    
    print(f"Found {len(blocks)} top-level blocks")
    
    all_questions = []
    all_keywords = []
    
    # Process each toggle (each exam)
    for block in blocks:
        if block['type'] == 'toggle':
            exam_name = block['toggle']['rich_text'][0]['text']['content']
            print(f"\nProcessing: {exam_name}")
            
            # Get children of this toggle
            toggle_children = get_all_children(notion, block['id'])
            
            # Separate questions and keywords
            in_keywords_section = False
            
            for child in toggle_children:
                # Check if we hit the Keywords section
                if child['type'] == 'heading_2':
                    heading_text = child['heading_2']['rich_text'][0]['text']['content'] if child['heading_2']['rich_text'] else ''
                    if heading_text == 'Keywords':
                        in_keywords_section = True
                        continue
                
                if child['type'] == 'divider':
                    continue
                
                if in_keywords_section:
                    all_keywords.append(child)
                else:
                    all_questions.append(child)
    
    print(f"\nTotal Questions: {len(all_questions)}, Total Keywords: {len(all_keywords)}")
    
    # Create two toggles on the same page
    print("\nCreating toggles...")
    
    # Create Questions toggle
    if all_questions:
        create_toggle(notion, page_id, "Questions & Solutions", all_questions)
        print(f"✓ Created Questions toggle with {len(all_questions)} items")
    
    # Create Keywords toggle
    if all_keywords:
        create_toggle(notion, page_id, "Keywords", all_keywords)
        print(f"✓ Created Keywords toggle with {len(all_keywords)} items")
    
    print("\n✓ Reorganization complete!")


def get_all_children(notion: Client, block_id: str):
    """Get all children blocks recursively."""
    children = []
    has_more = True
    start_cursor = None
    
    while has_more:
        response = notion.blocks.children.list(
            block_id=block_id,
            start_cursor=start_cursor
        )
        children.extend(response['results'])
        has_more = response['has_more']
        start_cursor = response.get('next_cursor')
    
    return children


def create_toggle(notion: Client, page_id: str, title: str, blocks: list):
    """Create a toggle with blocks as children."""
    # Clean blocks (remove id and other metadata)
    clean_blocks = []
    for block in blocks[:100]:  # Notion limit: 100 children
        clean_block = {
            "object": "block",
            "type": block['type']
        }
        clean_block[block['type']] = block[block['type']]
        clean_blocks.append(clean_block)
    
    # Create toggle
    toggle_block = {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [{
                "type": "text",
                "text": {"content": title},
                "annotations": {"bold": True}
            }],
            "children": clean_blocks
        }
    }
    
    # Append toggle to page
    response = notion.blocks.children.append(block_id=page_id, children=[toggle_block])
    
    # If more than 100 blocks, append remaining to the toggle
    if len(blocks) > 100:
        toggle_id = response['results'][0]['id']
        for i in range(100, len(blocks), 100):
            batch = blocks[i:i+100]
            clean_batch = []
            for block in batch:
                clean_block = {
                    "object": "block",
                    "type": block['type']
                }
                clean_block[block['type']] = block[block['type']]
                clean_batch.append(clean_block)
            
            notion.blocks.children.append(block_id=toggle_id, children=clean_batch)


if __name__ == "__main__":
    reorganize_notion_page()
