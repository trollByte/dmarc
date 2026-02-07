"""
SAML SSO (Single Sign-On) Service.

Implements SAML 2.0 authentication for enterprise SSO integration.

Features:
- Multiple IdP (Identity Provider) configurations
- SP (Service Provider) metadata generation
- Attribute mapping
- Just-in-time user provisioning
"""

import base64
import logging
import hashlib
import uuid
import zlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlencode, quote

from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SAMLStatus(str, Enum):
    """SAML authentication status"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


class NameIDFormat(str, Enum):
    """SAML NameID formats"""
    EMAIL = "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
    PERSISTENT = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
    TRANSIENT = "urn:oasis:names:tc:SAML:2.0:nameid-format:transient"
    UNSPECIFIED = "urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"


@dataclass
class SAMLAssertion:
    """Parsed SAML assertion"""
    name_id: str
    session_index: Optional[str]
    attributes: Dict[str, Any]
    issuer: str
    not_on_or_after: Optional[datetime]
    authn_instant: Optional[datetime]


@dataclass
class SAMLRequest:
    """SAML authentication request"""
    id: str
    request_xml: str
    encoded_request: str
    relay_state: Optional[str]
    redirect_url: str


class SAMLProvider(Base):
    """SAML Identity Provider configuration"""
    __tablename__ = "saml_providers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    entity_id = Column(String(500), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # IdP endpoints
    sso_url = Column(Text, nullable=False)  # Single Sign-On URL
    slo_url = Column(Text, nullable=True)  # Single Logout URL (optional)

    # IdP certificate
    x509_cert = Column(Text, nullable=False)  # IdP's signing certificate

    # Attribute mapping (SAML attribute -> user field)
    attribute_mapping = Column(JSONB, default={
        "email": ["email", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"],
        "first_name": ["firstName", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"],
        "last_name": ["lastName", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"],
        "groups": ["groups", "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"],
    })

    # Configuration
    name_id_format = Column(String(100), default=NameIDFormat.EMAIL.value, nullable=False)
    sign_requests = Column(Boolean, default=False, nullable=False)
    want_assertions_signed = Column(Boolean, default=True, nullable=False)
    allow_idp_initiated = Column(Boolean, default=False, nullable=False)

    # User provisioning
    auto_provision_users = Column(Boolean, default=True, nullable=False)
    default_role = Column(String(50), default="viewer", nullable=False)
    admin_groups = Column(JSONB, default=[], nullable=False)  # Groups that grant admin

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SAMLProvider(name={self.name}, entity_id={self.entity_id})>"


class SAMLSession(Base):
    """SAML authentication session tracking"""
    __tablename__ = "saml_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String(100), unique=True, nullable=False, index=True)
    provider_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Request state
    relay_state = Column(String(500), nullable=True)
    redirect_url = Column(Text, nullable=True)

    # Response state
    status = Column(String(20), default=SAMLStatus.PENDING.value, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    name_id = Column(String(255), nullable=True)
    session_index = Column(String(255), nullable=True)
    attributes = Column(JSONB, nullable=True)

    # Error tracking
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<SAMLSession(request_id={self.request_id}, status={self.status})>"


class SAMLService:
    """Service for SAML SSO authentication"""

    def __init__(self, db: Session):
        self.db = db
        self.sp_entity_id = f"{settings.frontend_url}/saml/metadata"
        self.acs_url = f"{settings.frontend_url}/api/saml/acs"
        self.slo_url = f"{settings.frontend_url}/api/saml/slo"

    # ==================== Provider Management ====================

    def create_provider(
        self,
        name: str,
        entity_id: str,
        sso_url: str,
        x509_cert: str,
        slo_url: Optional[str] = None,
        attribute_mapping: Optional[Dict] = None,
        name_id_format: str = NameIDFormat.EMAIL.value,
        auto_provision_users: bool = True,
        default_role: str = "viewer",
        admin_groups: Optional[List[str]] = None,
        sign_requests: bool = False,
        want_assertions_signed: bool = True,
        allow_idp_initiated: bool = False,
    ) -> SAMLProvider:
        """Create a new SAML provider"""
        provider = SAMLProvider(
            name=name,
            entity_id=entity_id,
            sso_url=sso_url,
            slo_url=slo_url,
            x509_cert=self._normalize_cert(x509_cert),
            attribute_mapping=attribute_mapping or {},
            name_id_format=name_id_format,
            auto_provision_users=auto_provision_users,
            default_role=default_role,
            admin_groups=admin_groups or [],
            sign_requests=sign_requests,
            want_assertions_signed=want_assertions_signed,
            allow_idp_initiated=allow_idp_initiated,
        )

        self.db.add(provider)
        self.db.commit()
        self.db.refresh(provider)
        return provider

    def update_provider(
        self,
        provider_id: uuid.UUID,
        **updates
    ) -> Optional[SAMLProvider]:
        """Update a SAML provider"""
        provider = self.db.query(SAMLProvider).filter(
            SAMLProvider.id == provider_id
        ).first()

        if not provider:
            return None

        for key, value in updates.items():
            if hasattr(provider, key) and value is not None:
                if key == "x509_cert":
                    value = self._normalize_cert(value)
                setattr(provider, key, value)

        self.db.commit()
        self.db.refresh(provider)
        return provider

    def delete_provider(self, provider_id: uuid.UUID) -> bool:
        """Delete a SAML provider"""
        provider = self.db.query(SAMLProvider).filter(
            SAMLProvider.id == provider_id
        ).first()

        if provider:
            self.db.delete(provider)
            self.db.commit()
            return True
        return False

    def get_providers(self, active_only: bool = True) -> List[SAMLProvider]:
        """Get SAML providers"""
        query = self.db.query(SAMLProvider)
        if active_only:
            query = query.filter(SAMLProvider.is_active == True)
        return query.order_by(SAMLProvider.name).all()

    def get_provider(self, provider_id: uuid.UUID) -> Optional[SAMLProvider]:
        """Get a single provider"""
        return self.db.query(SAMLProvider).filter(
            SAMLProvider.id == provider_id
        ).first()

    def get_provider_by_entity_id(self, entity_id: str) -> Optional[SAMLProvider]:
        """Get provider by entity ID"""
        return self.db.query(SAMLProvider).filter(
            SAMLProvider.entity_id == entity_id,
            SAMLProvider.is_active == True,
        ).first()

    # ==================== Authentication Flow ====================

    def create_auth_request(
        self,
        provider_id: uuid.UUID,
        relay_state: Optional[str] = None,
        redirect_url: Optional[str] = None,
    ) -> Optional[SAMLRequest]:
        """Create SAML authentication request"""
        provider = self.get_provider(provider_id)
        if not provider:
            return None

        # Generate request ID
        request_id = f"_id{uuid.uuid4().hex}"

        # Create request XML
        request_xml = self._create_authn_request(provider, request_id)

        # Encode request
        encoded = self._encode_request(request_xml)

        # Build redirect URL
        params = {"SAMLRequest": encoded}
        if relay_state:
            params["RelayState"] = relay_state

        redirect = f"{provider.sso_url}?{urlencode(params)}"

        # Store session
        session = SAMLSession(
            request_id=request_id,
            provider_id=provider.id,
            relay_state=relay_state,
            redirect_url=redirect_url,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        self.db.add(session)
        self.db.commit()

        return SAMLRequest(
            id=request_id,
            request_xml=request_xml,
            encoded_request=encoded,
            relay_state=relay_state,
            redirect_url=redirect,
        )

    def process_response(
        self,
        saml_response: str,
        relay_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process SAML response from IdP"""
        try:
            # Decode response
            response_xml = self._decode_response(saml_response)

            # Parse response (simplified - production should use proper SAML library)
            assertion = self._parse_response(response_xml)

            if not assertion:
                return {
                    "success": False,
                    "error": "Failed to parse SAML response",
                }

            # Find provider
            provider = self.get_provider_by_entity_id(assertion.issuer)
            if not provider:
                return {
                    "success": False,
                    "error": f"Unknown issuer: {assertion.issuer}",
                }

            # Map attributes
            user_attrs = self._map_attributes(assertion.attributes, provider.attribute_mapping)

            # Handle user provisioning
            user = self._provision_user(user_attrs, provider)

            return {
                "success": True,
                "user_id": str(user.id) if user else None,
                "email": user_attrs.get("email"),
                "name_id": assertion.name_id,
                "attributes": user_attrs,
                "relay_state": relay_state,
            }

        except Exception as e:
            logger.error(f"SAML response processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _create_authn_request(self, provider: SAMLProvider, request_id: str) -> str:
        """Create SAML AuthnRequest XML"""
        issue_instant = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest
    xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
    ID="{request_id}"
    Version="2.0"
    IssueInstant="{issue_instant}"
    Destination="{provider.sso_url}"
    AssertionConsumerServiceURL="{self.acs_url}"
    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{self.sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="{provider.name_id_format}" AllowCreate="true"/>
</samlp:AuthnRequest>"""

    def _encode_request(self, request_xml: str) -> str:
        """Encode and compress SAML request"""
        compressed = zlib.compress(request_xml.encode('utf-8'))[2:-4]  # Remove zlib header/trailer
        encoded = base64.b64encode(compressed).decode('utf-8')
        return quote(encoded)

    def _decode_response(self, saml_response: str) -> str:
        """Decode SAML response"""
        decoded = base64.b64decode(saml_response)
        return decoded.decode('utf-8')

    def _parse_response(self, response_xml: str) -> Optional[SAMLAssertion]:
        """Parse SAML response XML (simplified)"""
        # Note: Production implementation should use proper XML/SAML parsing library
        # like python3-saml or signxml for signature verification

        import re

        # Extract NameID
        name_id_match = re.search(r'<.*?NameID[^>]*>([^<]+)</.*?NameID>', response_xml)
        name_id = name_id_match.group(1) if name_id_match else None

        if not name_id:
            return None

        # Extract Issuer
        issuer_match = re.search(r'<.*?Issuer[^>]*>([^<]+)</.*?Issuer>', response_xml)
        issuer = issuer_match.group(1) if issuer_match else "unknown"

        # Extract attributes (simplified)
        attributes = {}
        attr_pattern = r'<.*?Attribute Name="([^"]+)"[^>]*>.*?<.*?AttributeValue[^>]*>([^<]*)</.*?AttributeValue>'
        for match in re.finditer(attr_pattern, response_xml, re.DOTALL):
            attr_name = match.group(1)
            attr_value = match.group(2)
            if attr_name in attributes:
                if isinstance(attributes[attr_name], list):
                    attributes[attr_name].append(attr_value)
                else:
                    attributes[attr_name] = [attributes[attr_name], attr_value]
            else:
                attributes[attr_name] = attr_value

        return SAMLAssertion(
            name_id=name_id,
            session_index=None,
            attributes=attributes,
            issuer=issuer,
            not_on_or_after=None,
            authn_instant=None,
        )

    def _map_attributes(
        self,
        attributes: Dict[str, Any],
        mapping: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Map SAML attributes to user fields"""
        result = {}

        for user_field, saml_attrs in mapping.items():
            for saml_attr in saml_attrs:
                if saml_attr in attributes:
                    result[user_field] = attributes[saml_attr]
                    break

        return result

    def _provision_user(
        self,
        attributes: Dict[str, Any],
        provider: SAMLProvider,
    ):
        """Provision or update user from SAML attributes"""
        from app.models import User

        email = attributes.get("email")
        if not email:
            return None

        user = self.db.query(User).filter(User.email == email).first()

        if not user and provider.auto_provision_users:
            # Create new user - derive username from email prefix
            username = email.split("@")[0]
            # Ensure unique username by appending suffix if needed
            existing = self.db.query(User).filter(User.username == username).first()
            if existing:
                import secrets
                username = f"{username}_{secrets.token_hex(4)}"
            user = User(
                username=username,
                email=email,
                hashed_password="!saml-sso-user",  # SSO users don't use password auth
                role=provider.default_role,
                is_active=True,
            )
            self.db.add(user)

        if user:
            # Check for admin group membership
            user_groups = attributes.get("groups", [])
            if isinstance(user_groups, str):
                user_groups = [user_groups]

            if any(g in provider.admin_groups for g in user_groups):
                user.role = "admin"

            self.db.commit()
            self.db.refresh(user)

        return user

    def _normalize_cert(self, cert: str) -> str:
        """Normalize X.509 certificate format"""
        cert = cert.strip()
        if "-----BEGIN CERTIFICATE-----" not in cert:
            cert = f"-----BEGIN CERTIFICATE-----\n{cert}\n-----END CERTIFICATE-----"
        return cert

    # ==================== SP Metadata ====================

    def generate_sp_metadata(self) -> str:
        """Generate Service Provider metadata XML"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
    entityID="{self.sp_entity_id}">
    <md:SPSSODescriptor
        AuthnRequestsSigned="false"
        WantAssertionsSigned="true"
        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:NameIDFormat>{NameIDFormat.EMAIL.value}</md:NameIDFormat>
        <md:NameIDFormat>{NameIDFormat.PERSISTENT.value}</md:NameIDFormat>
        <md:AssertionConsumerService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
            Location="{self.acs_url}"
            index="0"
            isDefault="true"/>
        <md:SingleLogoutService
            Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            Location="{self.slo_url}"/>
    </md:SPSSODescriptor>
</md:EntityDescriptor>"""
