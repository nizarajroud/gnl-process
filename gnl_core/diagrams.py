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
- Illustrate the FULL SCENARIO including the CORRECT SOLUTION:
  • AWS services mentioned in the current architecture
  • Data flows between services
  • Annotate constraints: HA, scalability, cost, latency, security, DR
  • Show the correct solution components HIGHLIGHTED with fillColor="#d5e8d4" (light green) and strokeColor="#82b366"
  • All non-solution components use their standard AWS category colors
- IMPORTANT: Use EXACTLY fillColor="#d5e8d4" and strokeColor="#82b366" for solution elements — the code will detect and remove this highlight for the question side
- Include a title with the question number
- Return ONLY valid draw.io XML starting with <mxfile and ending with </mxfile>
- NO text before or after the XML. NO explanations. NO markdown fences. ONLY XML.
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
        
        correct = answers[num].get('correct', [])
        correct_text = '; '.join(correct[:2]) if correct else ''
        
        user_msg = f"""Generate a draw.io XML diagram for this exam question. Show the scenario AND highlight the correct solution in green (fillColor="#d5e8d4"). Output ONLY the <mxfile>...</mxfile> XML.

Question {num}:
{scenario[:2000]}

Correct answer: {correct_text[:500]}"""
        
        messages.append({"role": "user", "content": [{"text": user_msg}]})
        
        try:
            response = client.converse(
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=messages,
                inferenceConfig={"maxTokens": 8000}
            )
            
            xml_content = response['output']['message']['content'][0]['text']
            
            # Extract XML: find <mxfile...>...</mxfile> block
            xml_match = re.search(r'(<mxfile[\s\S]*?</mxfile>)', xml_content)
            if xml_match:
                xml_content = xml_match.group(1)
            else:
                # Fallback: strip markdown fences
                xml_content = re.sub(r'^```xml\s*', '', xml_content.strip())
                xml_content = re.sub(r'^```\s*', '', xml_content.strip())
                xml_content = re.sub(r'\s*```$', '', xml_content.strip())
            
            # Validate: must start with <mxfile
            if not xml_content.strip().startswith('<mxfile'):
                if on_progress:
                    on_progress(f"  diagram Q{num} ⚠ invalid XML (no <mxfile>)")
                messages.append({"role": "assistant", "content": [{"text": "(invalid)"}]})
                continue
            
            # Save .drawio (with solution highlighted)
            drawio_path = diagrams_dir / f"Q{num}.drawio"
            drawio_path.write_text(xml_content, encoding='utf-8')
            
            # Export BACK PNG (with green highlight = answer side)
            png_back = diagrams_dir / f"Q{num}-answer.png"
            subprocess.run(
                ['drawio', '--export', '--format', 'png', '--output', str(png_back), str(drawio_path)],
                capture_output=True, timeout=30
            )
            
            # Create FRONT version (remove green highlight → neutral)
            xml_front = xml_content.replace('fillColor=#d5e8d4', 'fillColor=#f5f5f5')
            xml_front = xml_front.replace('fillColor="#d5e8d4"', 'fillColor="#f5f5f5"')
            xml_front = xml_front.replace('strokeColor=#82b366', 'strokeColor=#666666')
            xml_front = xml_front.replace('strokeColor="#82b366"', 'strokeColor="#666666"')
            drawio_front_path = diagrams_dir / f"Q{num}-front.drawio"
            drawio_front_path.write_text(xml_front, encoding='utf-8')
            
            # Export FRONT PNG (neutral = question side)
            png_front = diagrams_dir / f"Q{num}.png"
            subprocess.run(
                ['drawio', '--export', '--format', 'png', '--output', str(png_front), str(drawio_front_path)],
                capture_output=True, timeout=30
            )
            # Clean up temp front drawio
            drawio_front_path.unlink(missing_ok=True)
            
            if png_front.exists() and png_back.exists():
                results[num] = {'drawio': str(drawio_path), 'png_front': str(png_front), 'png_back': str(png_back)}
            elif png_front.exists():
                results[num] = {'drawio': str(drawio_path), 'png_front': str(png_front), 'png_back': None}
            else:
                results[num] = {'drawio': str(drawio_path), 'png_front': None, 'png_back': None}
            
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
