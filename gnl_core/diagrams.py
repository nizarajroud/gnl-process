"""Exam diagram generation — create draw.io diagrams for each question using Bedrock Converse multi-turn."""

import os
import re
import json
import subprocess
import boto3
from pathlib import Path
from .config import get_config


def _extract_xml(response_text):
    """Extract <mxfile>...</mxfile> XML from Bedrock response."""
    xml_match = re.search(r'(<mxfile[\s\S]*?</mxfile>)', response_text)
    if xml_match:
        return xml_match.group(1)
    text = re.sub(r'^```xml\s*', '', response_text.strip())
    text = re.sub(r'^```\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    return text


def _export_png(drawio_path, png_path):
    """Export .drawio to PNG via CLI. Returns True if success."""
    try:
        result = subprocess.run(
            ['drawio', '--export', '--format', 'png', '--output', str(png_path), str(drawio_path)],
            capture_output=True, timeout=30
        )
        return result.returncode == 0 and Path(png_path).exists()
    except Exception:
        return False


def generate_exam_diagrams(source_path, answers, theme, subtheme, on_progress=None):
    """Generate draw.io architecture diagrams for exam questions.
    
    One diagram per question: scenario architecture + FR/NFR/Constraints.
    No solution, no highlighting. Same image used on front and/or back.
    
    Args:
        source_path: Path to the full markdown (.md)
        answers: Dict from step3_highlight {num: {type, options, correct}}
        theme, subtheme: For output path
        on_progress: Callback
    Returns:
        Dict {num: {'png': path}} for generated diagrams
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
    
    # System prompt
    system_prompt = f"""{skill_content}

---
ADDITIONAL INSTRUCTIONS:
- For each question, generate a COMPLETE draw.io XML file (.drawio format)
- Show ONLY the SCENARIO architecture described in the question:
  • AWS services mentioned
  • Data flows between services
  • Integrations and connections
- Do NOT include any solution or answer
- Do NOT highlight anything in green
- BELOW the architecture, add THREE text boxes side by side in a row:
  1. Title "Functional Requirements" — with bullet points of what the system must DO
  2. Title "Non-Functional Requirements" — with bullet points (HA, scalability, performance, cost, security, DR as applicable)
  3. Title "Constraints" — with bullet points of explicit constraints from the question
- Style for these boxes: rounded=1;fillColor=#f5f5f5;strokeColor=#666666;align=left;verticalAlign=top;spacing=8;fontSize=11;whiteSpace=wrap;html=1;
- Position them at y=600 or below the architecture, spaced horizontally (x=100, x=450, x=800), width=300, height=200
- Include a title with the question number
- Return ONLY valid draw.io XML starting with <mxfile and ending with </mxfile>
- NO text before or after the XML. ONLY XML.
"""

    # Multi-turn conversation
    messages = []
    results = {}
    
    for num in sorted(answers.keys(), key=lambda x: int(x)):
        q_text = question_texts.get(num, '')
        if not q_text:
            continue
        
        # Extract scenario (before options)
        lines = q_text.split('\n')
        scenario_lines = []
        for line in lines:
            if line.strip().startswith('- '):
                break
            scenario_lines.append(line)
        scenario = '\n'.join(scenario_lines).strip()
        
        user_msg = f"""Generate a draw.io XML for Question {num}: scenario architecture + FR/NFR/Constraints boxes below. NO solution. Output ONLY <mxfile>...</mxfile> XML.

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
            
            xml_content = _extract_xml(response['output']['message']['content'][0]['text'])
            
            if not xml_content.strip().startswith('<mxfile'):
                if on_progress:
                    on_progress(f"  diagram Q{num} ⚠ invalid XML")
                messages.append({"role": "assistant", "content": [{"text": "(invalid)"}]})
                continue
            
            # Save .drawio
            drawio_path = diagrams_dir / f"Q{num}.drawio"
            drawio_path.write_text(xml_content, encoding='utf-8')
            
            # Export PNG
            png_path = diagrams_dir / f"Q{num}.png"
            if _export_png(drawio_path, png_path):
                results[num] = {'png': str(png_path)}
            else:
                results[num] = {'png': None}
            
            messages.append({"role": "assistant", "content": [{"text": xml_content}]})
            
            if on_progress:
                on_progress(f"  diagram Q{num} ✓")
                
        except Exception as e:
            if on_progress:
                on_progress(f"  diagram Q{num} ⚠ {str(e)[:60]}")
            messages.append({"role": "assistant", "content": [{"text": "(error)"}]})
        
        # Trim conversation if too long
        if len(messages) > 20:
            messages = messages[-10:]
    
    if on_progress:
        on_progress(f"diagrams → {len(results)} générés")
    
    return results
