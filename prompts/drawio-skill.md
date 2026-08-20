---
name: aws-architecture-diagram
description: Generate AWS architecture diagrams in draw.io format. Activates when the user asks to create, generate, or build an architecture diagram, system diagram, or draw.io diagram for AWS services.
---

## Instructions

Generate a draw.io (.drawio) XML file representing an AWS architecture diagram.

### Layout
- **Left-to-right flow** for data/request path
- **UI/Frontend on the LEFT** (users access from left side)
- **Data sources / external systems on the RIGHT**
- Use horizontal lanes for parallel paths (top lane, bottom lane)
- **Minimum 220px horizontal spacing** between icons (to leave room for edge labels)
- **Minimum 250px vertical spacing** between lanes (so vertical edges don't crowd)
- Secondary/auxiliary services (monitoring, DLQ, error paths) go BELOW the main flow with 280px+ vertical gap

### Canvas
- Large canvas: `pageWidth="2400" pageHeight="1400"` minimum
- Set `dx="2800" dy="1600"` for proper viewport
- Always include a title block as the first element after the background:
```xml
<mxCell value="&lt;b&gt;Diagram Title&lt;/b&gt;&lt;br&gt;Author | Date | Version" style="text;html=1;align=left;verticalAlign=top;whiteSpace=wrap;rounded=0;fontSize=14;spacing=8;" vertex="1" parent="1">
  <mxGeometry x="40" y="30" width="420" height="60" as="geometry" />
</mxCell>
```

### Icon Style
- Icons are from draw.io's built-in `mxgraph.aws4` stencil library — the **official AWS Architecture Icons** (https://aws.amazon.com/architecture/icons/, updated quarterly)
- Icon size: **78x78px** for main services, **65x65px** for secondary
- Use `sketch=0;outlineConnect=0;` on all icons
- Use `strokeColor=#ffffff` on all AWS service icons
- **MUST include `fillColor`** — without it, icons render as invisible/white in PNG export
- Font size: **12px** for labels
- Always include: `fontColor=#232F3E;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;aspect=fixed;`

**fillColor by AWS service category:**
| Category | fillColor | Services |
|----------|-----------|----------|
| Compute | `#ED7100` | Lambda, EC2, ECS, EKS, Fargate |
| Networking | `#8C4FFF` | VPC, ELB, CloudFront, Route 53, API Gateway |
| Database | `#C925D1` | RDS, DynamoDB, Aurora, ElastiCache |
| Storage | `#3F8624` | S3, EFS, EBS |
| Security | `#DD344C` | IAM, Cognito, KMS, WAF |
| Integration | `#E7157B` | SQS, SNS, EventBridge, Step Functions |
| Analytics | `#8C4FFF` | Kinesis, Athena, Redshift |
| Management | `#E7157B` | CloudWatch, CloudTrail |
| AI/ML | `#01A88D` | Bedrock, SageMaker |

### Edge Style — CRITICAL FOR CLEAN DIAGRAMS

**Base edge style (all edges):**
```
edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;
```

**Rules for edge labels:**
- Keep labels SHORT (1-2 words max). Use icon labels for detail, not edge labels.
- On horizontal edges: position label ABOVE the line using `verticalAlign=bottom;` in the edge style
- On vertical edges: position label to the LEFT using `align=right;` in the edge style
- Always add `labelBackgroundColor=#F5F5F5;` so labels don't overlap lines
- For edges WITHOUT labels: omit the `value` attribute entirely (don't use `value=""`)

**Edge label positioning (prevents overlap with icons):**
```xml
<mxCell value="Label" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;strokeWidth=2;labelBackgroundColor=#F5F5F5;fontSize=11;" edge="1" source="a" target="b" parent="1">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

**For edges that go to services ABOVE or BELOW the main flow:**
- Use explicit exit/entry points to control routing:
  - Exit bottom: `exitX=0.5;exitY=1;exitDx=0;exitDy=0;`
  - Enter top: `entryX=0.5;entryY=0;entryDx=0;entryDy=0;`
  - Exit top: `exitX=0.5;exitY=0;exitDx=0;exitDy=0;`
  - Enter bottom: `entryX=0.5;entryY=1;entryDx=0;entryDy=0;`
- This prevents draw.io from routing lines through other icons

**Edge types:**
- Solid black (`strokeWidth=2`): primary data flow
- Dashed black (`strokeWidth=2;dashed=1;`): optional/async path
- Dashed red (`strokeWidth=2;dashed=1;strokeColor=#DD344C;`): error path

**Edge attachment (CRITICAL — fixes "green cross" problem):**
- Every edge MUST have both `source="<cell-id>"` and `target="<cell-id>"` attributes referencing valid cell IDs
- NEVER create floating/unattached edges — all edges must be bound to shapes at both ends
- Always include `exitX/exitY` and `entryX/entryY` to define exact connection points on the shape perimeter
- In draw.io, properly attached edges show a "blue dot" anchor; unattached edges show a "green cross"
- If an edge connects to a child inside a container, reference the child's ID directly (not the container)
- **Cross-container edges:** When source and target are in different containers, set the edge's `parent="1"` (root layer) so draw.io can route it across boundaries

**When NOT to label edges:**
- If the flow is obvious from context (e.g., Lambda → DynamoDB doesn't need "Write")
- If the icon labels already explain the relationship
- Prefer fewer, more meaningful labels over labeling every edge

### Two Icon Patterns — CRITICAL

**Pattern 1: Service-level (resourceIcon frame)**
- Style: `sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor=<CATEGORY_COLOR>;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.<name>`
- **MUST use `strokeColor=#ffffff`** — without it, the white glyph disappears
- **MUST use `fillColor=<color>`** — without it, icon renders as white/invisible square in PNG export
- Size: 78x78

**Pattern 2: Resource-level (standalone shape)**
- Style: `sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor=<CATEGORY_COLOR>;strokeColor=none;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.<name>`
- **MUST use `strokeColor=none`** — using #ffffff breaks these
- **MUST use `fillColor=<color>`** — same reason as above
- Size: 78x78 or 48x48

**Confusing these patterns guarantees broken icons.**

### Icon Reference Files (load by category as needed)
- `references/aws-icons-compute.md` — Lambda, EC2, ECS, EKS, Fargate
- `references/aws-icons-database.md` — DynamoDB, RDS, Aurora, ElastiCache
- `references/aws-icons-integration.md` — API Gateway, SQS, SNS, EventBridge, Step Functions
- `references/aws-icons-networking.md` — CloudFront, Route 53, VPC, ELB
- `references/aws-icons-storage.md` — S3, EFS, EBS, Glacier, Backup
- `references/aws-icons-security.md` — IAM, Cognito, KMS, WAF, Shield
- `references/aws-icons-analytics-ml.md` — Kinesis, Athena, Bedrock, SageMaker
- `references/aws-icons-common.md` — Groups, general resources, edge styles, base template

**Always look up icons from reference files. Never guess icon names.**

**Fallback for unmapped services:** If a service is NOT found in any reference file, use this generic AWS cloud icon with the service name as label:
```
sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor=#232F3E;strokeColor=#ffffff;dashed=0;verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.general_AWScloud
```
Never render an unknown service as a plain colored rectangle with no label.

### Group Boundaries
- **AWS Cloud:** `shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_aws_cloud_alt;strokeColor=#232F3E;fillColor=none;container=1;dropTarget=1;`
- **Account:** `shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_account;strokeColor=#CD2264;fillColor=none;container=1;dropTarget=1;`
- **On-premise:** `shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_on_premise;strokeColor=#5A6C86;fillColor=none;container=1;dropTarget=1;`
- **VPC:** `shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=none;container=1;dropTarget=1;`
- **Subnet (public):** `shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_security_group;strokeColor=#7AA116;fillColor=none;container=1;dropTarget=1;`
- **Subnet (private):** `shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_security_group;strokeColor=#147EBA;fillColor=none;container=1;dropTarget=1;`
- **Logical groups:** Simple dashed boxes: `whiteSpace=wrap;html=1;fillColor=none;dashed=1;dashPattern=8 8;container=1;dropTarget=1;`
- **NO colored backgrounds** on group boxes — always `fillColor=none`

**Container nesting (CRITICAL for grouping):**
- ALL boundary/group shapes MUST include `container=1;dropTarget=1;` in their style
- Child cells inside a boundary MUST set `parent="<boundary-cell-id>"` instead of `parent="1"`
- This ensures moving a boundary moves all its children together
- Example:
```xml
<mxCell id="vpc1" value="VPC" style="shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_vpc2;strokeColor=#8C4FFF;fillColor=none;container=1;dropTarget=1;" vertex="1" parent="1">
  <mxGeometry x="100" y="100" width="800" height="500" as="geometry" />
</mxCell>
<mxCell id="lambda1" value="Lambda" style="shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.lambda;strokeColor=#ffffff;" vertex="1" parent="vpc1">
  <mxGeometry x="50" y="50" width="78" height="78" as="geometry" />
</mxCell>
```
Note: child geometry coordinates are **relative to the parent container**, not the canvas.

### PNG Export Background Fix
Place a full-canvas rectangle as the FIRST element (lowest z-order):
```xml
<mxCell value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor=#F5F5F5;strokeColor=none;" vertex="1" parent="1">
  <mxGeometry x="0" y="0" width="2400" height="1400" as="geometry" />
</mxCell>
```
This prevents black background on PNG export. Use `strokeColor=none` (not E0E0E0).

### Multi-page Diagrams
For complex architectures, use multiple pages (tabs) in one .drawio file:
```xml
<mxfile>
  <diagram id="overview" name="Overview">...</diagram>
  <diagram id="networking" name="Networking Detail">...</diagram>
  <diagram id="data-flow" name="Data Flow">...</diagram>
</mxfile>
```
- Page 1: High-level overview (service-level icons only)
- Page 2+: Detail views (resource-level icons, subnet layouts, etc.)

### Edge Legend (optional, for complex diagrams)
Place below the title block if the diagram has multiple edge types:
- Solid line: primary data flow
- Dashed line: optional/async
- Red dashed: error path

### File Splitting
Since draw.io XML can be large, split creation across multiple tool calls:
1. Header + left side (frontend, delivery layer)
2. Middle (processing lambdas, database)
3. Right side (ingest, messaging, data sources)
4. Bottom (optional/outbound flows) + close XML

### Audience Mode
Before generating, assess the target audience:
- **Technical**: Use service names, protocol labels (HTTPS, gRPC), CIDR blocks, instance types
- **Non-technical**: Use action labels ("Store Data", "Send Notification"), hide implementation details, use numbered flow (① ② ③)

If unclear, ask: "Technical audience or executive/non-technical?"

### Numbered Flow Edges (for non-technical mode)
Instead of technical labels, show flow order with circled numbers:
- Flow A: ① → ② → ③ → ④ (white circled numbers)
- Flow B: ❶ → ❷ → ❸ → ❹ (black circled numbers for second flow)

Use edge labels: `value="①"` with `fontSize=14;fontStyle=1;labelBackgroundColor=#ffffff;`

### Companion Guide
After generating the .drawio file, also generate a markdown guide:
- Same filename with `.md` extension (e.g., `serverless-api.drawio` + `serverless-api.md`)
- Contents: diagram title, flow description (numbered steps matching edge labels), service list with purpose, key design decisions

### Two-Step Edit Approach (OPTIONAL — only if user requests PNG)
After generating the initial .drawio file, IF the user asks for a PNG export:
1. **Export to PNG** using the draw.io CLI (see Output section)
2. **Review the PNG** visually — check for empty/broken icons, overlapping edges, misaligned labels
3. **Fix issues** in the .drawio XML and re-export

Do NOT export to PNG automatically. The .drawio file is the primary deliverable.

### Icon Name Gotchas — CRITICAL
draw.io stencil names do NOT always match current AWS service names. Services that were renamed keep their legacy stencil names:

| AWS Service Name | draw.io resIcon name | Why |
|---|---|---|
| Amazon OpenSearch Service | `elasticsearch_service` | Renamed from Elasticsearch in 2021; `opensearch_service` also works |
| Amazon EventBridge | `eventbridge` | Was CloudWatch Events |
| AWS Fargate | `fargate` | Correct |
| VPC Peering | `peering` | Resource-level: `shape=mxgraph.aws4.peering;strokeColor=none` — NOT `vpc_peering` or `peering_connection` (those render as blank squares) |
| Amazon MSK | `managed_streaming_for_kafka` | NOT `msk` (renders as blank square) |
| IAM Identity Center | `single_sign_on` | NOT `iam_identity_center` (renders as blank square) |

**Rule:** Always verify icon names from the reference files. If a service icon renders as an empty box, the stencil name is wrong. Check the draw.io source at `src/main/webapp/js/diagramly/sidebar/Sidebar-AWS4.js` for the canonical name.

### Validation Step
After generating XML, mentally verify:
1. Every `resIcon=` value exists in the reference files
2. Service-level icons have `strokeColor=#ffffff`
3. Resource-level icons have `strokeColor=none`
4. No XML comments present
5. All cell IDs are unique
6. Every edge has `<mxGeometry relative="1" as="geometry" />`
7. No icon uses a guessed stencil name — all verified against reference files
8. Every edge has both `source` and `target` attributes referencing valid cell IDs (no floating edges)
9. All group/boundary shapes include `container=1;dropTarget=1;` in their style
10. Children inside boundaries use `parent="<boundary-id>"` (not `parent="1"`)

### Output
- Save with descriptive filename ending in `.drawio`
- Open with `open` command (macOS) or `xdg-open` (Linux) after creation
- For PNG/SVG/PDF export, use draw.io CLI:
  - macOS: `/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -e -b 10 -o output.drawio.png input.drawio`
  - Linux: `drawio -x -f png -e -b 10 -o output.drawio.png input.drawio`
  Flags: `-x` export, `-f` format, `-e` embed diagram XML, `-b 10` border
- Exported files use double extension: `name.drawio.png` (signals embedded XML, re-editable in draw.io)

### XML Well-formedness (CRITICAL)
- **NEVER include XML comments (`<!-- -->`)** — they cause parse errors
- Escape special characters in values: `&amp;` `&lt;` `&gt;` `&quot;`
- Always use unique `id` values for each mxCell
- Every edge MUST have `<mxGeometry relative="1" as="geometry" />` as child element
- Basic structure must include root cells `id="0"` and `id="1"` (parent="0")

### Official Reference
- Full XML/style reference: https://raw.githubusercontent.com/jgraph/drawio-mcp/main/shared/xml-reference.md
- Style properties: https://raw.githubusercontent.com/jgraph/drawio-mcp/main/shared/style-reference.md

### ANTI-OVERLAP RULES — MANDATORY (NON-NEGOTIABLE)

These rules OVERRIDE any conflicting guidance above. They are the result of repeated failures and MUST be applied on every diagram generation.

#### RÈGLE 0 — Dimensionnement A4 obligatoire

The total diagram bounding box (all nodes + labels + margins) MUST fit within:
- MAXIMUM: A4 Landscape = 1122px wide x 794px tall (at 96dpi)
- MINIMUM: Half A4 Portrait = 794px wide x 561px tall (at 96dpi)

Target the middle ground by default:
- Diagram canvas: 1050px wide x 680px tall
- Outer margin (no content): 40px on all sides
- Usable area: 970px wide x 600px tall

After placing all nodes, verify:
  max(x + width) ≤ 1010px
  max(y + height) ≤ 640px
If any node exceeds these bounds → recompute the grid with smaller cell sizes or tighter gaps.

#### RÈGLE 1 — Layout en grille stricte avant tout

BEFORE generating any XML, define a strict grid layout:
- Assign every node a CELL position (col, row) on a virtual grid
- Minimum cell size: 220px wide x 160px tall
- Minimum gap between cells: 80px horizontal, 100px vertical
- Calculate absolute (x,y) from grid position: x = col * (cellW + gapX), y = row * (cellH + gapY)
- NO two nodes may share overlapping bounding boxes (x, y, width, height)
- Document the grid plan as a comment BEFORE writing XML

#### RÈGLE 2 — Edge routing explicite, jamais automatique

NEVER use default edge routing. For every edge:
- Specify exitX, exitY, entryX, entryY explicitly
- Horizontal connections: exitX=1,exitY=0.5 → entryX=0,entryY=0.5
- Vertical connections: exitX=0.5,exitY=1 → entryX=0.5,entryY=0
- If two edges leave the same node in the same direction, offset their exitY by at least 0.25 (e.g. 0.3 and 0.7)
- NEVER let two edges share the same exit/entry point on a node

#### RÈGLE 3 — Edge labels : toujours un offset explicite

For every edge label:
- ALWAYS set geometry relative="1" with x and y offsets
- Place labels at x=0 (midpoint) with y offset of -20 (above the edge)
- For vertical edges: use x=20 (to the right) and y=0
- For long edges crossing the diagram: use y=-30 to clear all nodes
- NEVER leave label geometry as x=0,y=0 on a non-horizontal edge

#### RÈGLE 4 — Edges parallèles : séparation obligatoire

When multiple edges connect to/from the same source OR target node:
- Use waypoints (Array of mxPoint) to manually route each edge on a different path
- Minimum lateral separation between parallel edges: 30px
- For dashed/dotted monitoring edges going to an external node on the right: route them with different exitY values (e.g. 0.3 and 0.6) and add a waypoint to fan them out before converging

#### RÈGLE 5 — Edges verticaux longs : style neutre obligatoire

For any edge that spans more than 2 grid rows vertically:
- ALWAYS explicitly set strokeColor=#666666 (or the diagram's default color)
- NEVER rely on inherited/default red or accent colors
- Add endArrow=block and endFill=0 for neutral appearance
- Add the label with x=20,y=0 offset (beside, not on top)

#### RÈGLE 6 — Validation checklist avant output

Before outputting the final XML, run this checklist mentally:
- □ Every node has unique non-overlapping (x, y, width, height)
- □ Every edge has explicit exitX/Y and entryX/Y
- □ No two edges share the same exit point on a node
- □ Every edge label has a non-zero geometry offset
- □ No label bounding box (estimated at 100px wide) overlaps a node bounding box
- □ All edge colors are explicitly set (no implicit red/accent)
- □ Dashed edges to external nodes are fanned out with different exitY
- □ Long vertical edges have a waypoint to avoid crossing unrelated nodes
- □ No container label overlaps its own children (startSize ≥ 30, first child at y ≥ 50 from container top)
- □ No long vertical edge passes through any node bounding box or within 20px of any label

If ANY check fails → fix before outputting.

#### RÈGLE 7 — Dimensionnement A4 obligatoire (see RÈGLE 0 above — kept as RÈGLE 0 for priority)

(Merged into RÈGLE 0 at the top of this section.)

#### RÈGLE 8 — Titres de containers (frames/groups)

For every container/swimlane/group node:
- ALWAYS set: swimlaneLine=1, startSize=30, fillColor=none or light
- The label (title) lives INSIDE the top bar of height startSize=30
- Add 20px top padding inside the container so the first child node starts at y = containerY + 50 (not containerY + 30)
- NEVER let a container's border overlap its own label
- Container width must be at least: max(child nodes x + width) + 40px right margin

#### RÈGLE 9 — Flèches longues verticales : routing obligatoire autour des nodes

For any edge that travels vertically across more than one container OR crosses intermediate nodes/labels:
- NEVER route it as a straight vertical line through the diagram center
- Route it OUTSIDE the node columns using a 3-segment L or Z path:
    Segment 1: exit node going RIGHT (exitX=1, exitY=0.5)
    Segment 2: horizontal run to a clear SIDE LANE (x = rightmost node + 60px)
    Segment 3: vertical drop down the clear lane
    Segment 4: enter target node from RIGHT (entryX=1, entryY=0.5)
- OR route it to the LEFT of all nodes (x = leftmost node - 60px)
- Add explicit waypoints (mxPoint) to enforce this path
- NEVER let a long vertical edge pass through any node bounding box or within 20px of any label

#### RÈGLE 10 — Ancrage à l'origine (fix du scroll vide)

The diagram MUST start at coordinates close to the canvas origin:
- First container or top-left node: x=40, y=60 (absolute minimum margin)
- NO node, container, or label may have x < 20 or y < 20
- NO node may start at x > 200 or y > 200 (reserving only left space for Users/VPN nodes that sit outside the main container)
- After generating all nodes, verify: min(x of all nodes) is between 20-200
- If the diagram appears offset, subtract the minimum x/y from all coordinates to re-anchor the whole diagram near the origin

#### RÈGLE 11 — Flèches multiples entrant dans le même node

When multiple edges arrive at the same target node:
- NEVER assign the same (entryX, entryY) to two edges on the same node
- Distribute entry points evenly across the node face:
    2 edges from left → entryX=0, entryY=0.3 and entryY=0.7
    3 edges from left → entryY=0.2, 0.5, 0.8
    2 edges from top  → entryX=0.3 and entryX=0.7, entryY=0
- Same rule applies to exit points on source nodes
- For nodes with 3+ outgoing edges: fan out exits evenly (e.g. exitY=0.25, 0.5, 0.75)
  and route each edge with a waypoint before entering its target

#### RÈGLE 12 — Labels des icônes : concision obligatoire

Node labels follow this format:
  Line 1: Short name only (e.g. "PROD App", "TEST DB", "Nagios")
  Line 2 (optional): ONE key spec in parentheses if critical to understanding.
                     Max 2 values, separated by |
                     e.g. "(192G | 1.2TB)" or "(Oracle 19c)"

Decision rule:
- If the spec helps distinguish this node from a similar one → include it
- If it's visible elsewhere (legend, title) → omit it
- CPU usage % → omit (operational metric, not architectural)
- Core count → omit unless it's the key differentiator
- Storage size → keep only if architecturally significant

#### RÈGLE 13 — Padding interne du label de container

For every container/group/swimlane node:
- The label text starts INSIDE the container, never on or beyond the border
- Set labelPosition=left is FORBIDDEN for containers
- Use: align=left, spacingLeft=10 within the container's top bar
- Container x position must leave enough room so that: containerX + 10 ≥ 50px from the left canvas edge
- The startSize (title bar height) must be ≥ 30px
- Minimum container width = length_of_title_in_chars × 8px + 40px padding
  (e.g. "DC St-Laurent (Prod + Test)" = 28 chars × 8 = 224 + 40 = 264px minimum)
- NEVER let a container be narrower than its own title

#### RÈGLE 14 — Aucun node fantôme / artefact de style sur les nodes de transit

For nodes that serve as edge hubs (e.g. FortiClient VPN connecting to 3+ targets):
- NEVER add a visible border style (strokeColor, fillColor) unless it is explicitly part of the diagram's visual language
- The node must have exactly ONE mxCell definition — no duplicate IDs, no overlapping invisible rectangles
- Verify: for each node ID, it appears EXACTLY ONCE in the XML
- If routing waypoints are needed, use mxPoint inside the edge definition, NEVER create intermediate ghost nodes to bend edges

#### RÈGLE 15 & 16 — UNIVERSAL PHANTOM & CANVAS INTEGRITY RULE

Applies to ALL draw.io diagrams without exception. Replaces the previous Rules 15 and 16.

**PART A — ZERO PHANTOM NODES**

Every mxCell with vertex="1" MUST satisfy at least ONE of:
- Has a non-empty visible label (value != "")
- Is a named architectural component (server, database, service, etc.)
- Is a container/group with visible children inside it

If a node satisfies NONE of the above → it MUST NOT exist in the XML.

This eliminates: background fill rectangles, invisible routing proxy nodes, ghost bounding boxes, "label" rectangles for edge concepts (those belong in edge value="").

**PART B — ROOT CAUSE RULE: LAYOUT RESERVATION FOR LONG EDGES (DEFINITIVE — replaces all previous)**

**PRINCIPLE:** Any edge that must travel outside its source container needs a RESERVED CORRIDOR — a column or row of empty space planned at STEP 0, before placing any node. If this corridor is not reserved at layout time, no edge style or waypoint rule can fix it afterward.

**STEP 0 — MANDATORY (before placing ANY node):**
Identify every long/inter-container edge. For each one, reserve a corridor:

VERTICAL inter-container edge (travels top→bottom):
- Reserve a COLUMN of width=40px to the LEFT of all containers
- corridor_x = first_container_x - 60
- This column must contain NO nodes, NO labels, NO legend

HORIZONTAL inter-container edge (travels left→right):
- Reserve a ROW of height=40px ABOVE all containers
- corridor_y = first_container_y - 60
- This row must contain NO nodes, NO labels, NO legend

Place containers, nodes, and legend AFTER reserving the corridor. The legend MUST be placed to the RIGHT of all containers.

**STEP 1 — EDGE USING THE CORRIDOR:**
```
style="edgeStyle=none;html=1;strokeWidth=2;strokeColor=#666666;dashed=1;dashPattern=10 4;endArrow=block;endFill=0;"
exitX=0, exitY=0.5 (exit LEFT side of source)
entryX=0, entryY=0.5 (enter LEFT side of target)
```
- waypoint 1: x=corridor_x, y=source.y + source.height/2
- waypoint 2: x=corridor_x, y=target.y + target.height/2

Using the LEFT corridor guarantees:
- waypoint x is always LESS than all node x values
- completely isolated from legend, containers, and labels
- no horizontal or vertical inflation possible

**STEP 2 — SET CANVAS LAST:**
After ALL nodes, labels, legend, and waypoints are placed:
- pageWidth = max(all x + width) + 80
- pageHeight = max(all y + height) + 80
- dx = pageWidth, dy = pageHeight

**SHORT EDGES (< 150px, same container):**
→ edgeStyle=orthogonalEdgeStyle remains safe for these.

**ABSOLUTE PROHIBITIONS — PERMANENT:**
- NEVER place a long-edge corridor on the RIGHT side if a legend or external node exists on the right
- NEVER place any node or label inside a reserved corridor
- NEVER set pageWidth/pageHeight before all waypoints are computed
- NEVER use exitX=1+entryX=1 — always prefer LEFT corridor (exitX=0+entryX=0)
- NEVER use orthogonalEdgeStyle or elbowEdgeStyle on any edge > 150px or inter-container
- NEVER add a label to a corridor edge without an explicit mxPoint offset anchored to the corridor x coordinate
- NEVER rely on draw.io's automatic label placement (relative="1" without offset) on any non-straight edge

**EDGE LABELS ON CORRIDOR EDGES:**

When a label is added to an edge routed via a side corridor (edgeStyle=none + waypoints), draw.io places the label at the geometric midpoint of the full path. For a U/L-shaped corridor edge, this midpoint falls OUTSIDE the visible canvas, inflating it.

SOLUTION — ALWAYS use explicit label offset on corridor edges:
```xml
<mxGeometry x="0" y="0" relative="1" as="geometry">
  <mxPoint x="[corridor_x + 5]" y="[midY]" as="offset"/>
</mxGeometry>
```
Where:
- corridor_x = the x value of your waypoints
- midY = (waypoint1.y + waypoint2.y) / 2
- x offset = corridor_x + 5 (just to the right of the lane)

This pins the label to a specific absolute position beside the corridor, not at the geometric midpoint.

After adding any label, re-verify:
- label offset x > 20 AND label offset x < pageWidth - 80
- label offset y > 20 AND label offset y < pageHeight - 40

**PART C — CANVAS SIZE = CONTENT SIZE**

The mxGraphModel page dimensions MUST match actual content:
- pageWidth = max(all node x + width) + 80
- pageHeight = max(all node y + height) + 80
- dx and dy attributes MUST equal pageWidth and pageHeight respectively
- NEVER set pageWidth/pageHeight to a fixed value without verifying it matches the actual content bounding box

**PART D — MANDATORY PRE-OUTPUT AUDIT**

Before outputting ANY draw.io XML, run this audit line by line:
- □ Every vertex mxCell has a purpose (label OR named component OR container)
- □ No vertex has width ≥ pageWidth or height ≥ pageHeight
- □ No vertex has value="" AND strokeColor=none
- □ Every edge has explicit exitX,exitY,entryX,entryY
- □ Every edge routing path stays within (20, 20, pageWidth-20, pageHeight-20)
- □ No mxPoint waypoint exceeds canvas bounds
- □ pageWidth and pageHeight = actual content bounds + 80px
- □ No node label contains edge-concept words used as a routing proxy (e.g. "Data Guard Lane", "Backup Path") → those words belong only in edge value="" attributes

If ANY check fails → fix before output. Do not output partial XML.

#### RÈGLE 17 — Interdiction des edgeLabel enfants

NEVER create a child mxCell with style="edgeLabel" attached to an edge.

This pattern is FORBIDDEN in agent-generated XML:
```
<mxCell style="edgeLabel;..." parent="edgeId" vertex="1" connectable="0">
```

Edge labels belong ONLY in the edge's own value="" attribute:
```
<mxCell id="e10" value="Data Guard" ... edge="1">
```

AUDIT: Scan all mxCell elements — any one with connectable="0" AND parent pointing to an edge id → DELETE it unconditionally.

#### GENERATION PROCESS (MANDATORY SEQUENCE)

**STEP 0**: Define the canvas (MANDATORY FIRST STEP) — Before planning the grid, set the canvas constraints:
- Total usable area: 970px wide x 600px tall
- This represents an A4 landscape page with margins (max format)
- It also comfortably fills the top half of an A4 portrait page (min format)
- ALL nodes, edges, labels, and external elements MUST fit inside this area
- Adjust grid cell size and spacing to fit — never exceed the canvas boundary
- Typical node size within this canvas: 140px wide x 80px tall max
- If the diagram has more than 8 nodes, reduce cell spacing to 60px and node size to 120x70px

**STEP 0b**: Anchor verification — After computing all coordinates, verify:
- Minimum x across all elements: must be 20–200px
- Minimum y across all elements: must be 20–150px
- If not: shift all coordinates by (-minX + 40, -minY + 60)
- This ensures the diagram is immediately visible on canvas open, without any scrolling

**STEP 1**: Plan the grid — define every node with: name | grid(col,row) | abs(x,y) | size(w,h). Output plan before writing XML. **IMPORTANT**: Reserve one column (the rightmost or leftmost) as a SIDE LANE exclusively for long vertical edges. No nodes may be placed in this lane. When multiple edges share the same source or target node, list them explicitly: "3 edges exit VPN → assign exitY=0.25, 0.5, 0.75". Do this BEFORE writing any edge XML. For each container, compute minimum width: minWidth = max(title_char_count × 8 + 40, widest_row_of_children + 80). Use whichever is larger. Document this in the grid plan.

**STEP 2**: Assign edge routes — for each edge: source→target | exitX,exitY | entryX,entryY | waypoints if needed. Two edges from same node must differ by ≥0.25 in exitY.

**STEP 2b**: Long vertical edges (DR replication, Data Guard) — Identify every edge that must travel vertically more than 200px. For each one:
- Plan a SIDE LANE: a vertical corridor at least 60px to the right of all nodes (or 60px to the left)
- Define 2+ waypoints: one at (sideLaneX, sourceY) and one at (sideLaneX, targetY)
- This guarantees the edge never intersects any node or label
- Label this edge with x=15, y=0 offset (beside the edge in the side lane)

**STEP 3**: Assign label offsets — every edge label: geometry x=0,y=-20 for horizontal; x=20,y=0 for vertical. For each node label, apply the 2-line maximum rule: Line 1 = name, Line 2 = one critical spec only (max 2 values in parentheses). Everything else → omit.

**STEP 4**: Set all styles explicitly — no edge may inherit color (always set strokeColor). No edge may use default routing (always set exit/entry points).

**STEP 5**: Validate before output — check every item in the validation checklist. Fix all violations. Then output XML.
- □ Every node has unique non-overlapping (x, y, width, height)
- □ Every edge has explicit exitX/Y and entryX/Y
- □ No two edges share the same exit point on a node
- □ Every edge label has a non-zero geometry offset
- □ No label bounding box overlaps a node bounding box
- □ All edge colors are explicitly set
- □ Long vertical edges routed via side lane with waypoints
- □ Every container width ≥ its title text pixel width + 40px
- □ Every container x ≥ 50px from canvas left edge
- □ No node ID appears more than once in the XML
- □ No invisible/ghost rectangle nodes exist
- □ Hub nodes (VPN, ALB) have exactly one mxCell definition
- □ All nodes anchored: min(x) between 20–200, min(y) between 20–150
- □ For every edge, all mxPoint waypoints are within (minX-60, minY-20, maxX+100, maxY+20) of all nodes combined
- □ No intermediate proxy rectangle exists for edge routing
- □ The DR vertical edge uses ONLY inline mxPoint waypoints, no helper nodes
- □ Canvas bounding box = max(node x+width) x max(node y+height) with no stray waypoints extending beyond it

#### ABSOLUTE PROHIBITIONS

- NEVER place two edges with the same exitX,exitY on the same node
- NEVER output an edge label with geometry x=0,y=0
- NEVER leave strokeColor unset on any edge
- NEVER generate XML without completing Steps 0–5 first
- NEVER place any node, label, or edge waypoint beyond x=1010 or y=640
- NEVER generate a diagram without completing STEP 0 first
- NEVER use a fixed node size without verifying it fits the A4 canvas budget
- NEVER route a vertical edge through the horizontal center of the diagram if any node or label exists along that vertical path
- NEVER place a container label with startSize < 30
- NEVER let the first child node start at less than 50px from the container top
- NEVER generate a node with x > 300 as the leftmost element of the diagram
- NEVER place the first container at y > 150
- NEVER put more than 2 lines in a node label
- NEVER repeat information already present in the diagram title or legend
- NEVER assign the same (entryX, entryY) to two edges arriving at the same node
- NEVER set a container width smaller than its label text width + 40px
- NEVER place a container at x < 50 if it has a left-aligned label
- NEVER create an invisible or borderless rectangle node as a waypoint proxy
- NEVER duplicate a node ID in the XML
- NEVER create a vertex mxCell that has no label AND no architectural purpose AND no children
- NEVER set pageWidth/pageHeight larger than content bounding box + 80px
- NEVER use entryX=1 on a target node geometrically below the source without verifying sideLane < pageWidth - 40
- NEVER output draw.io XML without running the Part D pre-output audit
- NEVER create a child mxCell with style="edgeLabel" or connectable="0" attached to an edge
- NEVER use exitX=0.5,exitY=1 + entryX=0.5,entryY=0 for inter-container edges without explicit waypoints

### Edge Enumeration (Flow Numbering) — MANDATORY

Every edge MUST include the `enumerate` property to display a circled sequence number on the arrow, showing the order of the data/request flow.

**Required style properties on all edges:**
```
enumerate=1;enumerateValue=N;
```

Where `N` is the step number in the logical flow.

**Numbering assignment rules (determine N):**

1. Start at `1` for the first user-initiated interaction (typically User → first service)
2. Increment sequentially following the **primary request path** (left → right in the diagram)
3. **Auth/validation flows** get a number based on WHEN they occur in the request lifecycle — authentication typically happens before the request reaches the backend, so it gets an early number (e.g., 2 or 3)
4. **Async/monitoring flows** (logs, metrics, audit) get higher numbers — they occur AFTER the main request is processed
5. **Optional/dashed flows** (error paths, fallback) get the highest numbers
6. **Config/provisioning flows** (IP sources, Terraform data sources, non-runtime edges) use `enumerate=0;` (no number displayed)

**Example ordering for a typical public API architecture:**

| N | Edge | Rationale |
|---|------|-----------|
| 1 | User → CDN/Edge | First interaction |
| 2 | CDN → WAF | Passes through protection |
| 3 | Auth Provider → API | Token validated before processing |
| 4 | WAF → API | Allowed traffic reaches API |
| 5 | API → Backend/Resolver | Request processed |
| 6 | Backend → Database | Data fetched/stored |
| 7 | API → CloudWatch | Audit logs emitted after response |
| 8 | CloudWatch → Splunk/External | Logs forwarded async |
| 0 | IP Source → WAF | Config/provisioning, not runtime |

**Implementation in edge style:**
```xml
<mxCell id="e1" value="HTTPS" style="edgeStyle=orthogonalEdgeStyle;...enumerate=1;enumerateValue=1;" edge="1" source="users" target="cdn" parent="1">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
<mxCell id="e7" value="OIDC Token" style="edgeStyle=orthogonalEdgeStyle;...enumerate=1;enumerateValue=3;" edge="1" source="entraid" target="appsync" parent="1">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

**Edges with `enumerate=0` (no circle displayed):**
- Non-runtime configuration edges (IP sources, Terraform data flows)
- Edges inside a "config/provisioning" group boundary

**Add to STEP 2 of GENERATION PROCESS:**
After assigning edge routes, assign enumerateValue to every edge following the logical flow order. Document the numbering plan before writing XML.

**Label offset when enumerate is active (prevents overlap):**

When an edge has BOTH a text label (`value="..."`) AND `enumerate=1`, the enumerate circle is placed automatically at the source end of the edge. To prevent overlap with the text label:
- ALWAYS set the label geometry with `x=0.3` to `x=0.4` (pushes label toward 65-70% of the edge, closer to target)
- ALWAYS set `y=-15` (keeps label above the line, away from the circle)

```xml
<mxCell id="e9" value="Subscription" style="...enumerate=1;enumerateValue=8;" edge="1" source="cloudwatch" target="splunk" parent="1">
  <mxGeometry x="0.3" y="-15" relative="1" as="geometry">
    <mxPoint as="offset" />
  </mxGeometry>
</mxCell>
```

For vertical edges (top→bottom), use `x=20` and `y=0.3`:
```xml
<mxGeometry x="20" y="0.3" relative="1" as="geometry">
  <mxPoint as="offset" />
</mxGeometry>
```

For edges WITHOUT a text label (only enumerate circle): use standard `<mxGeometry relative="1" as="geometry" />` — no offset needed.

### Flow Animation on Primary Path

Edges belonging to the **primary request path** (solid, non-dashed, `enumerateValue` ≥ 1) MUST include:
```
flowAnimation=1;
```

This makes the primary flow visually animated (moving dashes along the arrow) when the diagram is viewed in draw.io or exported as SVG/HTML.

**Rules:**
- `flowAnimation=1;` → edges with `enumerateValue` ≥ 1 AND `dashed=0` (or no dashed property)
- `flowAnimation=0;` (or omit) → dashed edges, config/provisioning edges (enumerate=0), error paths

**Rationale:** The animation highlights the critical request path at a glance, making it immediately distinguishable from secondary/config flows.

**Add to Validation checklist:**
- □ Every edge has `enumerate=1;enumerateValue=N;` or `enumerate=0;`
- □ enumerateValue follows logical request flow order (no gaps in the primary path)
- □ Auth edges numbered BEFORE the main processing they protect
- □ Monitoring/async edges numbered AFTER the main flow
- □ Config/provisioning edges use enumerate=0
- □ Every edge with BOTH label AND enumerate has geometry x=0.3-0.4 (horizontal) or y=0.3 (vertical) to avoid circle/label overlap
- □ Primary path edges (solid, enumerateValue ≥ 1) have `flowAnimation=1;`
- □ Secondary/dashed/config edges do NOT have flowAnimation
