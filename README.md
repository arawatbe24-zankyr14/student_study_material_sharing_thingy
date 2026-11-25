#~$~# Student Study Material Sharing Platform #~$~#

A cloud-based platform designed to help students upload, organize, access, and share academic resources such as notes, PDFs, presentations, and other study materials.

### Project Overview

The Student Study Material Sharing Platform aims to provide a centralized space where students can share educational resources and access study materials uploaded by others.

The project focuses on integrating cloud computing services for file storage, database management, and application deployment.

### Objectives

- Provide a centralized platform for academic resource sharing.
- Enable students to upload and download study materials.
- Organize resources based on subjects and categories.
- Implement search functionality for easy resource discovery.
- Utilize cloud infrastructure for scalable storage and data management.
- Explore secure access and resource management through AWS.

### Proposed Cloud Architecture

The project uses Amazon Web Services (AWS) as its cloud infrastructure.

| AWS Service | Purpose |
|---|---|
| Amazon EC2 | Application hosting and backend execution |
| Amazon S3 | Cloud storage for uploaded study materials |
| Amazon DynamoDB | Storage of user information and resource metadata |
| AWS IAM | Identity and access management |
| Amazon CloudWatch | Application and infrastructure monitoring (planned) |

### Application Workflow

1. Students access the application through a web browser.
2. The application backend processes user requests.
3. Uploaded documents are stored in Amazon S3.
4. Resource information and metadata are maintained in DynamoDB.
5. Students can search, access, and download available resources.

### Technology Stack

- **Programming Language:** Python
- **Development Environment:** Visual Studio Code
- **Version Control:** Git and GitHub
- **Cloud Platform:** Amazon Web Services (AWS)
- **Cloud Storage:** Amazon S3
- **Database:** Amazon DynamoDB
- **Testing:** Pytest

### Project Structure

```text
student_study_material_sharing_thingy/
│
├── app/
│   └── Application source code
│
├── scripts/
│   └── Utility and setup scripts
│
├── tests/
│   └── Automated test cases
│
├── .env.example
│   └── Example environment configuration
│
├── .gitignore
│   └── Git exclusion rules
│
├── ASSEMBLY_NOTES.md
│   └── Project assembly and implementation notes
│
├── pytest.ini
│   └── Pytest configuration
│
└── requirements.txt
    └── Python dependencies
```

## ⚙️ Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/arawatbe24-zankyr14/student_study_material_sharing_thingy.git
```

### 2. Navigate to the project directory

```bash
cd student_study_material_sharing_thingy
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create a `.env` file using `.env.example` as the template.

Add the required configuration values for the application and AWS services.

**Important:** Never commit `.env` files, AWS credentials, private keys, or other secrets to GitHub.

### 6. Run the application

Refer to the application entry point and execution instructions in the `app/` directory.

### Testing

The project uses Pytest for automated testing.

Run the test suite using:

```bash
pytest
```

### Security Considerations

- Sensitive configuration is maintained through environment variables.
- AWS IAM roles are used where applicable to manage service permissions.
- Cloud resources should follow the principle of least privilege.
- Uploaded resources should be validated before storage.
- Access to private resources should be controlled.

### Future Enhancements

- Automated GitHub Actions deployment pipeline.
- Improved authentication and authorization.
- Admin dashboard for resource moderation.
- Resource download analytics.
- Subject-wise resource recommendations.
- CloudFront integration for faster content delivery.
- Monitoring through Amazon CloudWatch.

### Project Information

**Project:** Student Study Material Sharing Platform

**Course:** Cloud Computing (UCS531)

**Institution:** Thapar Institute of Engineering and Technology

**Version Control:** GitHub

---

*Developed as an academic cloud computing project to explore real-world applications of cloud infrastructure, storage, databases, and deployment.*
