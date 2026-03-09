"""
Application configuration — loads from environment variables.
All secrets encrypted at rest; never logged.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "clinical-ai-platform"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Database (Supabase PostgreSQL — HIPAA compliant, encrypted at rest)
    database_url: str = "postgresql://user:pass@localhost:5432/clinical_ai"
    database_pool_size: int = 20

    # Redis (session cache, FHIR token cache)
    redis_url: str = "redis://localhost:6379/0"

    # FHIR / EHR Integration (Epic SMART on FHIR)
    fhir_base_url: str = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
    fhir_client_id: str = ""
    fhir_client_secret: str = ""
    fhir_scopes: str = "patient/*.read launch/patient openid fhirUser"

    # LLM Providers
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_reasoning_model: str = "claude-sonnet-4-20250514"

    # Medical ontologies
    umls_api_key: str = ""
    snomed_edition: str = "US1000124"

    # Auth (Clerk)
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""

    # S3 (document storage — encrypted)
    s3_bucket: str = "meridian-clinical-ai-docs"
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # Observability (LangSmith)
    langsmith_api_key: str = ""
    langsmith_project: str = "clinical-ai-platform"

    # HIPAA Compliance
    phi_encryption_key: str = ""
    audit_log_retention_years: int = 6
    session_timeout_minutes: int = 30
    max_failed_login_attempts: int = 5

    # Rate limiting
    rate_limit_per_minute: int = 120

    # CORS
    allowed_origins: list[str] = ["https://dashboard.meridianhealth.com"]

    class Config:
        env_file = ".env"
        case_sensitive = False
