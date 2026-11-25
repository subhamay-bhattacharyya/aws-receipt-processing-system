# Automated AWS Receipt Processing System

<!-- Row 1: Status - Most Important -->
[![Release](https://img.shields.io/github/v/release/subhamay-bhattacharyya/aws-receipt-processing-system?label=Release)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system/releases)&nbsp;[![Release Workflow](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system/actions/workflows/ci.yaml/badge.svg)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system/actions/workflows/release.yaml)&nbsp;[![Issues](https://img.shields.io/github/issues/subhamay-bhattacharyya/aws-receipt-processing-system)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system/issues)&nbsp;[![Last Commit](https://img.shields.io/github/last-commit/subhamay-bhattacharyya/aws-receipt-processing-system)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system/commits)

<!-- Row 2: Code Quality -->
[![Top Language](https://img.shields.io/badge/Languages-Python%20%7C%20YAML-blue)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system)&nbsp;[![Commits](https://img.shields.io/github/commit-activity/t/subhamay-bhattacharyya/aws-receipt-processing-system)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system/commits)

<!-- Row 3: Tech Stack -->
[![CloudFormation](https://img.shields.io/badge/CloudFormation-IaC-orange?logo=amazonaws&logoColor=white)](https://aws.amazon.com/cloudformation/)&nbsp;[![Built with Claude Code](https://img.shields.io/badge/Built_with-Claude_Code-D97757?logo=anthropic&logoColor=white)](https://claude.ai/)

<!-- Row 4: Repository Info -->
[![Files](https://img.shields.io/github/directory-file-count/subhamay-bhattacharyya/aws-receipt-processing-system)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system)&nbsp;[![Repo Size](https://img.shields.io/github/repo-size/subhamay-bhattacharyya/aws-receipt-processing-system)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system)&nbsp;[![Release Date](https://img.shields.io/github/release-date/subhamay-bhattacharyya/aws-receipt-processing-system)](https://github.com/subhamay-bhattacharyya/aws-receipt-processing-system/releases)

<!-- Row 5: Custom Metrics -->
[![Custom Endpoint](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/bsubhamay/468a63b8b6c664f86c2629edb0f4a282/raw/aws-receipt-processing-system.json)](https://gist.github.com/subhamay-bhattacharyya/468a63b8b6c664f86c2629edb0f4a282)

---

## Overview

An automated receipt processing pipeline that ingests receipt images/PDFs, extracts structured data using ML, and stores results with email notifications. Built entirely with Infrastructure-as-Code using CloudFormation nested stacks for modularity and reusability across environments.

---

## Architecture

``` mermaid
flowchart LR
    User["👤 User"] -->|Uploads receipt| S3

    subgraph AWS["AWS Cloud"]
        S3["📦 Amazon S3"]
        Lambda["⚙️ AWS Lambda"]
        Textract["🔍 Amazon Textract"]
        DynamoDB["💾 Amazon DynamoDB"]
        SES["📧 Amazon SES"]

        S3 -->|"2. Trigger"| Lambda
        Lambda -->|"3. Process"| Textract
        Textract -->|"4. Data"| Lambda
        Lambda -->|"5. Store"| DynamoDB
        Lambda -->|"6. Notify"| SES
    end

    SES -->|Email notification| User

    style User fill:#e1f5ff
    style S3 fill:#fff3e0
    style Lambda fill:#f3e5f5
    style Textract fill:#f3e5f5
    style DynamoDB fill:#e8f5e9
    style SES fill:#fce4ec
```

### Steps

1. The user uploads a receipt to S3.
2. The S3 upload triggers the Lambda function.
3. Lambda invokes Amazon Textract to extract data from the receipt.
4. Textract returns structured data to Lambda.
5. Lambda stores the processed data in the DynamoDB table.
6. Lambda uses Amazon SES to send an email notification to the user.

---

## Features & Status

| Component | Purpose | Status |
| --- | --- | --- |
| **S3 Bucket** | Stores receipt images/PDFs with versioning & encryption | ✅ Complete |
| **DynamoDB Table** | Stores extracted receipt metadata | ✅ Complete |
| **Lambda Function** | Orchestrates receipt processing workflow | ✅ Complete |
| **Textract Integration** | Extracts text/data from receipts | ✅ Complete |
| **SES Notifications** | Sends email with extracted details | ✅ Complete |
| **IAM Roles & Policies** | Cross-service permissions | ✅ Complete |

---

## Project Structure

``` text
.
├── .claude/
│   └── .skills/                     # Custom skills (contribution, github-ci-workflow, package-json, readme-md)
├── .devcontainer/
│   └── devcontainer.json            # Dev container setup
├── .env/
│   └── environments.yaml            # Environment configuration
├── .github/
│   ├── workflows/
│   │   ├── ci.yaml                  # Template validation & deployment
│   │   ├── claude.yaml              # Claude Code integration
│   │   ├── claude-code-review.yaml  # Claude Code review
│   │   ├── create-branch.yaml       # Issue-based branch automation
│   │   ├── deploy.yaml              # CloudFormation stack deployment
│   │   ├── deploy-lambda.yaml       # Lambda build and deployment
│   │   ├── delete.yaml              # CloudFormation stack deletion
│   │   ├── notify.yaml              # Slack notifications
│   │   └── setup-environments.yaml  # AWS environment setup
│   ├── ISSUE_TEMPLATE/              # Bug report and feature request templates
│   ├── CODEOWNERS                   # Repository ownership
│   ├── dependabot.yaml              # Dependency updates
│   └── PULL_REQUEST_TEMPLATE.md     # PR template
├── cloudformation/
│   ├── template.yaml                # Root CloudFormation stack
│   ├── parameters.json              # Stack parameters
│   └── stack-config.json            # Stack configuration
├── lambda/
│   └── receipt-processor/
│       ├── lambda.py                # Lambda handler
│       ├── requirements.txt         # Python dependencies
│       └── structured_logging/      # Structured logging package
├── scripts/
│   └── plugins/                     # Semantic-release plugins
├── .gitattributes                   # Git attribute settings
├── .gitignore                       # Git ignore rules
├── CLAUDE.md                        # Project guidelines
├── CONTRIBUTING.md                  # Contribution guidelines
├── CHANGELOG.md                     # Version history
├── PROGRESS.md                      # Implementation tracking
├── CODE_OF_CONDUCT.md               # Code of conduct
├── LICENSE                          # MIT License
└── README.md                        # This file
```

---

## Key Features

### Infrastructure as Code

- Nested CloudFormation stack pattern for modularity
- Parameter-driven multi-environment configuration
- Deterministic resource naming (ProjectName-Environment-AccountId-Region)

### Security Best Practices

- S3 versioning and public access blocking
- KMS encryption for S3 and DynamoDB
- DynamoDB point-in-time recovery
- IAM least-privilege access patterns

### CI/CD & Automation

- GitHub Actions validation and deployment
- AWS OIDC keyless authentication
- Semantic versioning with conventional commits
- Automated CloudFormation template validation

---

## Next Steps

1. Create Lambda function CloudFormation template
2. Integrate Amazon Textract for OCR
3. Configure SES for email notifications
4. Define IAM roles and cross-service policies
5. Set up DynamoDB Streams to Lambda integration

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT
