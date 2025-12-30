# GNL Process - NotebookLM Automation

Automated workflow for processing AWS solutions and generating NotebookLM content.

## Overview

This project automates the process of:
- Scraping AWS solution pages
- Processing content through NotebookLM
- Managing Chrome browser automation
- Downloading and organizing generated content

## Prerequisites

- Python 3.x
- Chrome browser
- Chrome user data directory setup

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables in `.env`
4. Set up Chrome user data directory: `python -m setup_chrome_user_data_dir`

## Scripts

### Core Scripts

#### `nllm-aws-asl-v2.py`
Main processing script for AWS solutions.
```bash
python nllm-aws-asl-v2.py
```

#### `nllm-aws-asl-add-generate-gnl.py`
Adds and generates content from AWS solution URLs.
```bash
python nllm-aws-asl-add-generate-gnl.py <URL>
```

#### `nllm-aws-asl-download-rename-gnl.py`
Downloads and renames generated content.
```bash
python nllm-aws-asl-download-rename-gnl.py <URL>
```

### Utility Scripts

#### `nllm-aws-asl-clean-gnls.py`
Cleans existing NotebookLM content.
```bash
python nllm-aws-asl-clean-gnls.py
```

#### `nllm-aws-asl-add-gnl.py`
Adds new content to NotebookLM.
```bash
python nllm-aws-asl-add-gnl.py
```

#### `nllm-aws-asl-update-podcast-name-on-gnl.py`
Updates podcast names in NotebookLM.
```bash
python nllm-aws-asl-update-podcast-name-on-gnl.py <URL>
```

#### `run_multiple.py`
Batch processing script.
```bash
python run_multiple.py
```

## Configuration

### Environment Variables (.env)
```
USER_DATA_DIR=/home/nizar/Clone-Chrome-profile/User Data
# Add other environment variables here
```

### Chrome User Data Directory
The `user_data_dir` is configured in `.env` file. You can override it using the `--user_data_dir` flag when running scripts.

## Workflow

1. **Setup**: Initialize Chrome profile and environment
2. **Process**: Run main script with AWS solution URL
3. **Generate**: Create NotebookLM content
4. **Download**: Retrieve generated files
5. **Organize**: Rename and organize output

## Dependencies

- `fire` - CLI interface
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `python-dotenv` - Environment management
- `pyfzf` - Fuzzy finding
- `nova_act` - Browser automation

## Usage Examples

### Complete Workflow
```bash
# 1. Setup Chrome user data directory
python -m setup_chrome_user_data_dir

# 2. Main processing
python nllm-aws-asl-v2.py

# 3. Clean existing content
python nllm-aws-asl-clean-gnls.py

# 4. Add new content
python nllm-aws-asl-add-gnl.py

# 5. Update podcast name
python nllm-aws-asl-update-podcast-name-on-gnl.py https://aws.amazon.com/solutions/guidance/generative-ai-deployments-using-amazon-sagemaker-jumpstart/

# 6. Add and generate content
python nllm-aws-asl-add-generate-gnl.py https://aws.amazon.com/solutions/guidance/generative-ai-deployments-using-amazon-sagemaker-jumpstart/

# 7. Download and rename
python nllm-aws-asl-download-rename-gnl.py https://aws.amazon.com/solutions/guidance/generative-ai-deployments-using-amazon-sagemaker-jumpstart/
```

### Single URL Processing
```bash
python nllm-aws-asl-add-generate-gnl.py https://aws.plainenglish.io/develop-aws-ml-workloads-locally-with-localstack-and-sam-24bdc0de81aa
```

### Batch Processing
```bash
python run_multiple.py
```

## Troubleshooting

### Common Issues

1. **Chrome Profile Issues**: Ensure Chrome user data directory exists and is accessible
2. **Download Path**: Default downloads go to `/home/nizar/Downloads`
3. **Environment Variables**: Check `.env` file configuration

### Error Resolution

- **NovaAct Errors**: Verify Chrome profile setup
- **Download Issues**: Check download directory permissions
- **Network Errors**: Verify internet connection and URL accessibility

## Project Structure

```
gnl-process/
├── .env                                    # Environment configuration
├── README.md                              # Basic usage instructions
├── DOCUMENTATION.md                       # This file
├── nllm-aws-asl-v2.py                    # Main processing script
├── nllm-aws-asl-add-generate-gnl.py      # Content generation
├── nllm-aws-asl-download-rename-gnl.py   # Download management
├── nllm-aws-asl-clean-gnls.py            # Cleanup utility
├── nllm-aws-asl-add-gnl.py               # Content addition
├── nllm-aws-asl-update-podcast-name-on-gnl.py  # Name updates
├── run_multiple.py                        # Batch processing
└── setup_chrome_user_data_dir.py         # Chrome setup
```

## Contributing

1. Follow existing code patterns
2. Update documentation for new features
3. Test with sample AWS solution URLs
4. Maintain environment variable configuration

## License

[Add your license information here]
