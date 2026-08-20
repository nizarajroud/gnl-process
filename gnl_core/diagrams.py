"""Exam diagram generation — create draw.io diagrams for each question using Bedrock Converse multi-turn."""

import os
import re
import json
import subprocess
import boto3
from pathlib import Path
from .config import get_config


def generate_exam_diagrams(source_path, answers, theme, subtheme, on_progress=None):
    """Generate draw.io architecture diagrams for exam questions.
    
    Uses Bedrock Converse with the draw.io skill as system prompt (loaded once).
    Each question is sent as a user message in the same conversation.
    
    Args:
        source_path: Path to the full markdown (.md)
        answers: Dict from step3_highlight {num: {type, options, correct}}
        theme, subtheme: For output path
        on_progress: Callback
    Returns:
        Dict {num: {'drawio': path, 'png': path}} for generated diagrams
    """
    config = get_config()
    model_id = config.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-20250514-v1:0')
    
    # Load skill as system prompt (sent once)
    skill_path = Path(__file__).parent.parent / 'prompts' / 'drawio-skill.md'
    if not skill_path.exists():
        raise FileNotFoundError(f"Draw.io skill not found: {skill_path}")
    skill_content = skill_path.read_text(encoding='utf-8')
    
    # Read full markdown to get question texts
    md_content = Path(source_path).read_text(encoding='utf-8')
    parts = re.split(r'## Question\s+\d+:', md_content)
    q_headers = re.findall(r'## Question\s+(\d+):', md_content)
    
    question_texts = {}
    for idx, num in enumerate(q_headers):
        if idx + 1 < len(parts):
            question_texts[num] = parts[idx + 1].strip()
    
    # Output directory
    from .exams import get_exam_base
    base = get_exam_base(theme, subtheme)
    diagrams_dir = base / 'diagrams'
    diagrams_dir.mkdir(parents=True, exist_ok=True)
    
    # Bedrock client
    client = boto3.client('bedrock-runtime', region_name='us-east-1')
    
    # System prompt: skill + instructions for SCENARIO ONLY (not solution)
    system_prompt = f"""{skill_content}

---
ADDITIONAL INSTRUCTIONS:
- For each question I send you, generate a COMPLETE draw.io XML file (.drawio format)
- Illustrate ONLY the SCENARIO and CONTEXT of the question:
  • AWS services mentioned in the current architecture
  • Data flows between services
  • Annotate constraints: HA, scalability, cost, latency, security, DR
  • Show the PROBLEM or requirement that needs to be solved
- Do NOT illustrate the solution or correct answer
- Do NOT show which option is correct
- Include a title with the question number
- Return ONLY the XML content, no explanation, no markdown fences
"""
    
    # Multi-turn conversation
    messages = []
    results = {}
    
    for num in sorted(answers.keys(), key=lambda x: int(x)):
        q_text = question_texts.get(num, '')
        if not q_text:
            continue
        
        # Only send the scenario part (before options)
        lines = q_text.split('\n')
        scenario_lines = []
        for line in lines:
            if line.strip().startswith('- '):
                break
            scenario_lines.append(line)
        scenario = '\n'.join(scenario_lines).strip()
        
        user_msg = f"""Generate a draw.io diagram for the SCENARIO of this exam question (do NOT include the solution):

Question {num}:
{scenario[:2000]}"""
        
        messages.append({"role": "user", "content": [{"text": user_msg}]})
        
        try:
            response = client.converse(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={"maxTokens": 8000}
            )
            
            xml_content = response['output']['message']['content'][0]['text']
            
            # Clean up: remove markdown fences if present
            xml_content = re.sub(r'^```xml\s*', '', xml_content.strip())
            xml_content = re.sub(r'^```\s*', '', xml_content.strip())
            xml_content = re.sub(r'\s*```$', '', xml_content.strip())
            
            # Save .drawio
            drawio_path = diagrams_dir / f"Q{num}.drawio"
            drawio_path.write_text(xml_content, encoding='utf-8')
            
            # Export to PNG
            png_path = diagrams_dir / f"Q{num}.png"
            export_result = subprocess.run(
                ['drawio', '--export', '--format', 'png', '--output', str(png_path), str(drawio_path)],
                capture_output=True, timeout=30
            )
            
            if export_result.returncode == 0 and png_path.exists():
                results[num] = {'drawio': str(drawio_path), 'png': str(png_path)}
            else:
                results[num] = {'drawio': str(drawio_path), 'png': None}
            
            # Add assistant response to conversation
            messages.append({"role": "assistant", "content": [{"text": xml_content}]})
            
            if on_progress:
                on_progress(f"  diagram Q{num} ✓")
                
        except Exception as e:
            if on_progress:
                on_progress(f"  diagram Q{num} ⚠ {str(e)[:60]}")
            messages.append({"role": "assistant", "content": [{"text": "(error)"}]})
        
        # Trim conversation if too long (keep last 10 exchanges)
        if len(messages) > 20:
            messages = messages[-10:]
    
    if on_progress:
        on_progress(f"diagrams → {len(results)} générés")
    
    return results
