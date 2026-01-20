# Mermaid Diagram Templates

Standard dark theme templates for consistent diagram styling across the project.

## Flowchart Template

Use this for architecture diagrams, pipelines, and data flow diagrams.

```mermaid
%%{init: {"theme": "dark", "themeVariables": {"primaryColor": "#4A90A4", "secondaryColor": "#F5A623", "tertiaryColor": "#2d2d2d", "lineColor": "#88CCFF", "primaryTextColor": "#FFFFFF", "secondaryTextColor": "#FFFFFF", "tertiaryTextColor": "#FFFFFF", "nodeTextColor": "#FFFFFF", "edgeLabelBackground": "#333333", "clusterBkg": "#2d2d2d", "clusterBorder": "#555555"}, "flowchart": {"curve": "basis", "nodeSpacing": 60, "rankSpacing": 100}}}%%
flowchart TB
    subgraph Example["Example Subgraph"]
        A["Node A"] --> B["Node B"]
        B --> C["Node C"]
    end

    %% Standard classDef styles - Dark fills with white text
    classDef external fill:#8B6914,stroke:#F5A623,stroke-width:2px,color:#FFFFFF
    classDef lambda fill:#2B5F7C,stroke:#4A90A4,stroke-width:2px,color:#FFFFFF
    classDef storage fill:#3D6B3D,stroke:#7ED321,stroke-width:2px,color:#FFFFFF
    classDef messaging fill:#8B4513,stroke:#D0021B,stroke-width:2px,color:#FFFFFF
    classDef monitoring fill:#4B3D6B,stroke:#9013FE,stroke-width:2px,color:#FFFFFF
    classDef cdn fill:#6B3D5C,stroke:#E91E63,stroke-width:2px,color:#FFFFFF
    classDef frontend fill:#2B6B6B,stroke:#00BCD4,stroke-width:2px,color:#FFFFFF
    classDef auth fill:#8B3D3D,stroke:#FF5252,stroke-width:2px,color:#FFFFFF
    classDef gateway fill:#3D3D6B,stroke:#3F51B5,stroke-width:2px,color:#FFFFFF

    %% Pipeline-specific styles
    classDef buildNode fill:#3D5C3D,stroke:#4a7c4e,stroke-width:2px,color:#FFFFFF
    classDef imageNode fill:#4A3D6B,stroke:#673ab7,stroke-width:2px,color:#FFFFFF
    classDef preprodNode fill:#8B5A00,stroke:#c77800,stroke-width:2px,color:#FFFFFF
    classDef prodNode fill:#6B2020,stroke:#b71c1c,stroke-width:2px,color:#FFFFFF
    classDef gateStyle fill:#8B4500,stroke:#e65100,stroke-width:2px,color:#FFFFFF

    class A lambda
    class B storage
    class C external
```

## Sequence Diagram Template

Use this for interaction flows, API sequences, and authentication flows.

```mermaid
%%{init: {"theme": "dark", "themeVariables": {"primaryColor": "#4A90A4", "lineColor": "#88CCFF", "primaryTextColor": "#FFFFFF", "actorTextColor": "#FFFFFF", "actorBkg": "#2B5F7C", "actorBorder": "#4A90A4", "signalColor": "#88CCFF", "signalTextColor": "#FFFFFF", "noteBkgColor": "#3D3D3D", "noteTextColor": "#FFFFFF", "activationBkgColor": "#2d2d2d"}}}%%
sequenceDiagram
    participant A as Service A
    participant B as Service B
    participant C as Database

    rect rgb(30, 40, 60)
        Note over A,C: Flow Section 1 (blue tint)
        A->>B: Request
        B->>C: Query
        C-->>B: Response
        B-->>A: Result
    end

    rect rgb(60, 40, 30)
        Note over A,C: Flow Section 2 (orange tint)
        A->>C: Direct query
        C-->>A: Data
    end

    rect rgb(30, 50, 30)
        Note over A,C: Flow Section 3 (green tint)
        A->>B: Another request
        B-->>A: Another response
    end
```

## Color Reference

### Node Fill Colors (Dark theme)

| Purpose    | Fill Color | Stroke Color | Usage                    |
| ---------- | ---------- | ------------ | ------------------------ |
| External   | `#8B6914`  | `#F5A623`    | External APIs, services  |
| Lambda     | `#2B5F7C`  | `#4A90A4`    | Lambda functions         |
| Storage    | `#3D6B3D`  | `#7ED321`    | DynamoDB, S3, databases  |
| Messaging  | `#8B4513`  | `#D0021B`    | SNS, SQS, queues         |
| Monitoring | `#4B3D6B`  | `#9013FE`    | CloudWatch, alerts       |
| CDN        | `#6B3D5C`  | `#E91E63`    | CloudFront, edge         |
| Frontend   | `#2B6B6B`  | `#00BCD4`    | S3 static, Amplify       |
| Auth       | `#8B3D3D`  | `#FF5252`    | Cognito, auth services   |
| Gateway    | `#3D3D6B`  | `#3F51B5`    | API Gateway, load balancer|

### Rect Colors for Sequence Diagrams

| Tint   | RGB Value         | Usage              |
| ------ | ----------------- | ------------------ |
| Blue   | `rgb(30, 40, 60)` | Primary flows      |
| Orange | `rgb(60, 40, 30)` | OAuth/auth flows   |
| Green  | `rgb(30, 50, 30)` | Success/data flows |
| Red    | `rgb(50, 30, 35)` | Error/refresh flows|

## mermaid.live URLs

To view diagrams in mermaid.live with full pan/zoom, the URL must be encoded. Use this Python snippet:

```python
import zlib
import base64
import json

def generate_mermaid_url(diagram_code: str) -> str:
    payload = {
        "code": diagram_code,
        "mermaid": {"theme": "dark"},
        "autoSync": True,
        "updateDiagram": True
    }
    json_str = json.dumps(payload)
    compressed = zlib.compress(json_str.encode('utf-8'), 9)
    encoded = base64.urlsafe_b64encode(compressed).decode('utf-8').rstrip('=')
    return f"https://mermaid.live/view#pako:{encoded}"
```
