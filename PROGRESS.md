# AWS Receipt Processing System - Progress

## Project Status

Building an automated receipt processing pipeline using AWS services with infrastructure-as-code (CloudFormation).

**Current Branch:** `feature/CFN-0003-setup-automated-aws-recei`

---

## Root Stack Architecture

### ✅ Implemented Services

| Service | Purpose | Status | Details |
| --- | --- | --- | --- |
| **AWS CloudFormation** | Infrastructure as Code | ✅ Complete | Root + nested S3 bucket, DynamoDB, and IAM role templates with nested stack pattern |
| **Amazon S3** | Stores uploaded receipt images and PDFs | ✅ Complete | Nested stack with versioning, encryption, public access blocking |
| **Amazon DynamoDB** | Stores extracted receipt data | ✅ Complete | Nested stack with on-demand billing, event streams, point-in-time recovery |
| **IAM Roles & Policies** | Secure access control | ✅ Complete | Nested stack with Lambda execution role and inline policies |

### ⏳ Pending Services

| Service | Purpose | Status | Notes |
| --- | --- | --- | --- |
| **AWS Lambda** | Automates processing workflow | 🔲 Pending | Execution role ready; Lambda function creation next |
| **Amazon Textract** | Extracts text from receipts | 🔲 Pending | Policy permissions configured in IAM role |
| **Amazon SES** | Sends email notifications | 🔲 Pending | Policy permissions configured in IAM role |
| **S3 Event Notifications** | Trigger Lambda on file uploads | 🔲 Pending | Will be configured when Lambda template is added |

---

## Implementation Details

### Completed

- **Root CloudFormation Stack** — Invokes nested S3 bucket, DynamoDB, and IAM role templates
- **S3 Bucket Nested Stack** — Versioning, encryption (KMS), public access blocking
- **DynamoDB Table Nested Stack** — On-demand billing, event streams, point-in-time recovery, KMS encryption
- **IAM Role Nested Stack** — Lambda execution role with inline policies for:
  - CloudWatch Logs (Lambda basic execution)
  - S3 read-write access (receipt bucket)
  - DynamoDB read-write access (receipts table)
  - AWS Textract permissions
  - Amazon SES permissions
  - KMS key access
- **Parameter-Driven Configuration** — Environment-specific parameters (dev, staging, prod)
  - Lambda function name computed dynamically: `{ProjectName}-{LambdaBaseName}-{Environment}-{Region}`
  - Separate KMS encryption configuration section
  - Organized parameter groups for S3, DynamoDB, Lambda, and Advanced settings
- **CI/CD Pipeline** — GitHub Actions validation and deployment
- **Git Workflow** — Conventional commits, semantic versioning, branch automation

### Next Steps

1. Create Lambda function CloudFormation template
2. Add S3 event notification configuration
3. Implement Lambda function code for receipt processing
4. Test end-to-end workflow with Textract extraction
5. Deploy to staging environment

---

## Lambda IAM Role Configuration

### Inline Policies Enabled

| Policy | Purpose | Access Level |
| --- | --- | --- |
| Lambda Basic Execution | CloudWatch Logs | Write |
| S3 Read-Write | Receipt bucket operations | Read + Write |
| DynamoDB Read-Write | Receipts table operations | Read + Write |
| Textract | Extract text from images | Execute |
| SES | Send email notifications | Send |
| KMS | Encrypt/decrypt with customer key | Use key |

### Role Details

- **Role Name:** `{ProjectName}-{LambdaRoleName}-{Environment}`
- **Assume Role Principal:** `lambda.amazonaws.com`
- **Nested Stack Template:** `cfn-nested-aws-iam-roles-policies/iam-role-inline-policies/template.yaml`
- **Deployment Region:** Configurable per environment (dev, staging, prod)

---

## Key Artifacts

- `cloudformation/template.yaml` — Root stack with S3, DynamoDB, and IAM role nested stacks
  - **Outputs:** S3 bucket name/ARN, DynamoDB table name/ARN, Lambda role ARN/name, computed Lambda function name
  - **Parameters:** Organized in 6 sections (Nested Stack, KMS, S3, DynamoDB, Lambda, Advanced)
- `cloudformation/parameters.json` — Stack parameters
- `.github/workflows/ci.yaml` — Validation & deployment
- `.github/workflows/setup-environments.yaml` — Environment setup
- `PROGRESS.md` — Project progress tracking
