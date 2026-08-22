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
    # Fallback: strip markdown fences
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
    
    Generates TWO diagrams per question:
    - Front: scenario architecture + FR/NFR/Constraints (no solution)
    - Back: full architecture with correct solution highlighted in green
    
    Uses Bedrock Converse with the draw.io skill as system prompt (loaded once).
    
    Args:
        source_path: Path to the full markdown (.md)
        answers: Dict from step3_highlight {num: {type, options, correct}}
        theme, subtheme: For output path
        on_progress: Callback
    Returns:
        Dict {num: {'png_front': path, 'png_back': path}} for generated diagrams
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
    
    # === SYSTEM PROMPTS ===
    system_front = f"""{skill_content}

---
ADDITIONAL INSTRUCTIONS FOR FRONT (QUESTION SIDE):
- Generate a draw.io XML diagram that shows ONLY the SCENARIO described in the question
- Show the existing architecture: AWS services, data flows, integrations
- Do NOT include ANY solution or answer options
- Do NOT highlight anything in green
- BELOW the architecture diagram, add THREE text boxes side by side (as a row):
  1. "Functional Requirements" — bullet points of what the system must DO
  2. "Non-Functional Requirements" — bullet points (HA, scalability, performance, cost, security, DR)
  3. "Constraints" — bullet points of explicit constraints mentioned
- Use style for these boxes: rounded=1;fillColor=#f5f5f5;strokeColor=#666666;align=left;verticalAlign=top;spacing=8;fontSize=11;
- Return ONLY valid draw.io XML starting with <mxfile and ending with </mxfile>
- NO text before or after the XML. ONLY XML.
"""

    system_back = f"""{skill_content}

---
ADDITIONAL INSTRUCTIONS FOR BACK (ANSWER SIDE):
- Generate a draw.io XML diagram showing the COMPLETE architecture WITH the correct solution
- Show the correct solution components HIGHLIGHTED with fillColor="#d5e8d4" (light green) and strokeColor="#82b366"
- All non-solution components use their standard AWS category colors
- Include arrows and labels showing how the solution resolves the problem
- Include a title with the question number
- Return ONLY valid draw.io XML starting with <mxfile and ending with </mxfile>
- NO text before or after the XML. ONLY XML.
"""

    # Multi-turn conversations (separate for front and back)
    messages_front = []
    messages_back = []
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
        
        correct = answers[num].get('correct', [])
        correct_text = '; '.join(correct[:2]) if correct else ''
        
        # === FRONT DIAGRAM (scenario + requirements) ===
        front_msg = f"""Generate a draw.io XML for Question {num} FRONT side (scenario only, NO solution).
Show the architecture described, then add 3 boxes below: Functional Requirements, Non-Functional Requirements, Constraints.
Output ONLY <mxfile>...</mxfile> XML.

Question {num}:
{scenario[:2000]}"""
        
        messages_front.append({"role": "user", "content": [{"text": front_msg}]})
        
        png_front_path = None
        try:
            resp_front = client.converse(
                modelId=model_id,
                system=[{"text": system_front}],
                messages=messages_front,
                inferenceConfig={"maxTokens": 8000}
            )
            xml_front = _extract_xml(resp_front['output']['message']['content'][0]['text'])
            
            if xml_front.strip().startswith('<mxfile'):
                front_drawio = diagrams_dir / f"Q{num}-front.drawio"
                front_drawio.write_text(xml_front, encoding='utf-8')
                png_front_path = diagrams_dir / f"Q{num}.png"
                if _export_png(front_drawio, png_front_path):
                    png_front_path = str(png_front_path)
                else:
                    png_front_path = None
                messages_front.append({"role": "assistant", "content": [{"text": xml_front}]})
            else:
                messages_front.append({"role": "assistant", "content": [{"text": "(invalid)"}]})
        except Exception as e:
            if on_progress:
                on_progress(f"  diagram Q{num} front ⚠ {str(e)[:50]}")
            messages_front.append({"role": "assistant", "content": [{"text": "(error)"}]})

        # === BACK DIAGRAM (with solution highlighted) ===
        back_msg = f"""Generate a draw.io XML for Question {num} BACK side (with correct solution highlighted in green).
Output ONLY <mxfile>...</mxfile> XML.

Question {num}:
{scenario[:2000]}

Correct answer: {correct_text[:500]}"""
        
        messages_back.append({"role": "user", "content": [{"text": back_msg}]})
        
        png_back_path = None
        try:
            resp_back = client.converse(
                modelId=model_id,
                system=[{"text": system_back}],
                messages=messages_back,
                inferenceConfig={"maxTokens": 8000}
            )
            xml_back = _extract_xml(resp_back['output']['message']['content'][0]['text'])
            
            if xml_back.strip().startswith('<mxfile'):
                back_drawio = diagrams_dir / f"Q{num}.drawio"
                back_drawio.write_text(xml_back, encoding='utf-8')
                png_back_path = diagrams_dir / f"Q{num}-answer.png"
                if _export_png(back_drawio, png_back_path):
                    png_back_path = str(png_back_path)
                else:
                    png_back_path = None
                messages_back.append({"role": "assistant", "content": [{"text": xml_back}]})
            else:
                messages_back.append({"role": "assistant", "content": [{"text": "(invalid)"}]})
        except Exception as e:
            if on_progress:
                on_progress(f"  diagram Q{num} back ⚠ {str(e)[:50]}")
            messages_back.append({"role": "assistant", "content": [{"text": "(error)"}]})

        # Store results
        if png_front_path or png_back_path:
            results[num] = {'png_front': png_front_path, 'png_back': png_back_path}
            if on_progress:
                on_progress(f"  diagram Q{num} ✓")
        else:
            if on_progress:
                on_progress(f"  diagram Q{num} ⚠ no valid output")
        
        # Trim conversations if too long
        if len(messages_front) > 20:
            messages_front = messages_front[-10:]
        if len(messages_back) > 20:
            messages_back = messages_back[-10:]
    
    if on_progress:
        on_progress(f"diagrams → {len(results)} générés")
    
    return results
