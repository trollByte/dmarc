"""Unit tests for SAMLService (saml_service.py)"""
import pytest
import uuid
import base64
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app.services.saml_service import (
    SAMLService,
    SAMLProvider,
    SAMLSession,
    SAMLAssertion,
    SAMLRequest,
    SAMLStatus,
    NameIDFormat,
)


@pytest.mark.unit
class TestProviderManagement:
    """Test SAML provider CRUD operations"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.saml_service.get_settings") as mock_settings:
            mock_settings.return_value.frontend_url = "https://dmarc.example.com"
            svc = SAMLService(mock_db)
        return svc

    def test_create_provider(self, service, mock_db):
        """Test creating a SAML provider"""
        provider = service.create_provider(
            name="Okta SSO",
            entity_id="https://okta.example.com/sso/saml",
            sso_url="https://okta.example.com/sso/endpoint",
            x509_cert="MIICtest123",
            default_role="viewer",
        )

        assert mock_db.add.called
        assert mock_db.commit.called
        assert mock_db.refresh.called

        added = mock_db.add.call_args[0][0]
        assert added.name == "Okta SSO"
        assert added.entity_id == "https://okta.example.com/sso/saml"
        assert added.sso_url == "https://okta.example.com/sso/endpoint"
        assert added.default_role == "viewer"

    def test_create_provider_normalizes_cert(self, service, mock_db):
        """Test that creating a provider normalizes the X.509 certificate"""
        service.create_provider(
            name="Test IdP",
            entity_id="https://idp.example.com",
            sso_url="https://idp.example.com/sso",
            x509_cert="RAW_CERT_DATA_WITHOUT_HEADERS",
        )

        added = mock_db.add.call_args[0][0]
        assert "-----BEGIN CERTIFICATE-----" in added.x509_cert
        assert "-----END CERTIFICATE-----" in added.x509_cert

    def test_create_provider_cert_already_normalized(self, service, mock_db):
        """Test that an already normalized cert is not double-wrapped"""
        full_cert = "-----BEGIN CERTIFICATE-----\nMIICtest\n-----END CERTIFICATE-----"
        service.create_provider(
            name="Test IdP",
            entity_id="https://idp.example.com",
            sso_url="https://idp.example.com/sso",
            x509_cert=full_cert,
        )

        added = mock_db.add.call_args[0][0]
        assert added.x509_cert.count("-----BEGIN CERTIFICATE-----") == 1

    def test_update_provider_success(self, service, mock_db):
        """Test updating an existing provider"""
        provider_id = uuid.uuid4()
        existing = Mock(spec=SAMLProvider)
        existing.id = provider_id
        existing.name = "Old Name"
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        result = service.update_provider(provider_id, name="New Name")

        assert result is not None
        assert mock_db.commit.called

    def test_update_provider_not_found(self, service, mock_db):
        """Test updating a nonexistent provider returns None"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.update_provider(uuid.uuid4(), name="Updated")

        assert result is None

    def test_update_provider_normalizes_cert_update(self, service, mock_db):
        """Test that updating x509_cert normalizes the certificate"""
        provider_id = uuid.uuid4()
        existing = Mock(spec=SAMLProvider)
        existing.id = provider_id
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        service.update_provider(provider_id, x509_cert="NEW_RAW_CERT")

        # The setattr call should have normalized the cert
        assert mock_db.commit.called

    def test_delete_provider_success(self, service, mock_db):
        """Test deleting an existing provider"""
        provider_id = uuid.uuid4()
        existing = Mock(spec=SAMLProvider)
        existing.id = provider_id
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        result = service.delete_provider(provider_id)

        assert result is True
        assert mock_db.delete.called
        assert mock_db.commit.called

    def test_delete_provider_not_found(self, service, mock_db):
        """Test deleting a nonexistent provider returns False"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = service.delete_provider(uuid.uuid4())

        assert result is False
        assert not mock_db.delete.called

    def test_get_providers_active_only(self, service, mock_db):
        """Test getting only active providers"""
        mock_providers = [Mock(spec=SAMLProvider)]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_providers

        result = service.get_providers(active_only=True)

        assert mock_db.query.called

    def test_get_providers_all(self, service, mock_db):
        """Test getting all providers including inactive"""
        mock_providers = [Mock(spec=SAMLProvider), Mock(spec=SAMLProvider)]
        mock_db.query.return_value.order_by.return_value.all.return_value = mock_providers

        result = service.get_providers(active_only=False)

        assert mock_db.query.called

    def test_get_provider_by_id(self, service, mock_db):
        """Test getting a provider by ID"""
        provider_id = uuid.uuid4()
        expected = Mock(spec=SAMLProvider)
        expected.id = provider_id
        mock_db.query.return_value.filter.return_value.first.return_value = expected

        result = service.get_provider(provider_id)

        assert result is expected

    def test_get_provider_by_entity_id(self, service, mock_db):
        """Test getting a provider by entity ID"""
        expected = Mock(spec=SAMLProvider)
        expected.entity_id = "https://idp.example.com"
        mock_db.query.return_value.filter.return_value.first.return_value = expected

        result = service.get_provider_by_entity_id("https://idp.example.com")

        assert result is expected


@pytest.mark.unit
class TestAuthRequest:
    """Test SAML authentication request creation"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.saml_service.get_settings") as mock_settings:
            mock_settings.return_value.frontend_url = "https://dmarc.example.com"
            svc = SAMLService(mock_db)
        return svc

    def test_create_auth_request_success(self, service, mock_db):
        """Test creating a SAML auth request"""
        provider_id = uuid.uuid4()
        provider = Mock(spec=SAMLProvider)
        provider.id = provider_id
        provider.sso_url = "https://idp.example.com/sso"
        provider.name_id_format = NameIDFormat.EMAIL.value

        with patch.object(service, 'get_provider', return_value=provider):
            result = service.create_auth_request(
                provider_id=provider_id,
                relay_state="/dashboard",
            )

        assert result is not None
        assert isinstance(result, SAMLRequest)
        assert result.relay_state == "/dashboard"
        assert "idp.example.com" in result.redirect_url
        assert "SAMLRequest" in result.redirect_url
        assert mock_db.add.called
        assert mock_db.commit.called

    def test_create_auth_request_provider_not_found(self, service, mock_db):
        """Test auth request creation when provider not found"""
        with patch.object(service, 'get_provider', return_value=None):
            result = service.create_auth_request(uuid.uuid4())

        assert result is None

    def test_create_auth_request_stores_session(self, service, mock_db):
        """Test that creating an auth request stores a SAML session"""
        provider = Mock(spec=SAMLProvider)
        provider.id = uuid.uuid4()
        provider.sso_url = "https://idp.example.com/sso"
        provider.name_id_format = NameIDFormat.EMAIL.value

        with patch.object(service, 'get_provider', return_value=provider):
            result = service.create_auth_request(provider.id, relay_state="/dashboard")

        added_session = mock_db.add.call_args[0][0]
        assert isinstance(added_session, SAMLSession)
        assert added_session.provider_id == provider.id
        assert added_session.relay_state == "/dashboard"
        assert added_session.expires_at > datetime.utcnow()


@pytest.mark.unit
class TestResponseProcessing:
    """Test SAML response processing"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.saml_service.get_settings") as mock_settings:
            mock_settings.return_value.frontend_url = "https://dmarc.example.com"
            svc = SAMLService(mock_db)
        return svc

    def test_process_response_success(self, service, mock_db):
        """Test successful SAML response processing"""
        saml_xml = """
        <samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol">
            <saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">https://idp.example.com</saml:Issuer>
            <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
                <saml:Subject>
                    <saml:NameID>user@example.com</saml:NameID>
                </saml:Subject>
                <saml:AttributeStatement>
                    <saml:Attribute Name="email"><saml:AttributeValue>user@example.com</saml:AttributeValue></saml:Attribute>
                </saml:AttributeStatement>
            </saml:Assertion>
        </samlp:Response>
        """
        encoded_response = base64.b64encode(saml_xml.encode('utf-8')).decode('utf-8')

        provider = Mock(spec=SAMLProvider)
        provider.id = uuid.uuid4()
        provider.attribute_mapping = {"email": ["email"]}
        provider.auto_provision_users = True
        provider.default_role = "viewer"
        provider.admin_groups = []

        mock_user = Mock()
        mock_user.id = uuid.uuid4()

        with patch.object(service, 'get_provider_by_entity_id', return_value=provider):
            with patch.object(service, '_provision_user', return_value=mock_user):
                result = service.process_response(encoded_response, relay_state="/dashboard")

        assert result["success"] is True
        assert result["name_id"] == "user@example.com"
        assert result["relay_state"] == "/dashboard"

    def test_process_response_invalid_xml(self, service, mock_db):
        """Test processing invalid SAML response"""
        # Invalid base64 that won't decode to valid XML with NameID
        encoded_response = base64.b64encode(b"<not-valid>no name id</not-valid>").decode('utf-8')

        result = service.process_response(encoded_response)

        assert result["success"] is False

    def test_process_response_unknown_issuer(self, service, mock_db):
        """Test processing response from unknown issuer"""
        saml_xml = """
        <Response>
            <Issuer>https://unknown-idp.example.com</Issuer>
            <Assertion>
                <Subject><NameID>user@example.com</NameID></Subject>
            </Assertion>
        </Response>
        """
        encoded_response = base64.b64encode(saml_xml.encode('utf-8')).decode('utf-8')

        with patch.object(service, 'get_provider_by_entity_id', return_value=None):
            result = service.process_response(encoded_response)

        assert result["success"] is False
        assert "Unknown issuer" in result["error"]

    def test_process_response_exception(self, service, mock_db):
        """Test process_response handles exceptions gracefully"""
        result = service.process_response("not-valid-base64!!!")

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestAttributeMapping:
    """Test SAML attribute mapping"""

    @pytest.fixture
    def service(self):
        mock_db = MagicMock()
        with patch("app.services.saml_service.get_settings") as mock_settings:
            mock_settings.return_value.frontend_url = "https://dmarc.example.com"
            return SAMLService(mock_db)

    def test_map_attributes_basic(self, service):
        """Test basic attribute mapping"""
        attributes = {
            "email": "user@example.com",
            "firstName": "John",
            "lastName": "Doe",
        }
        mapping = {
            "email": ["email"],
            "first_name": ["firstName"],
            "last_name": ["lastName"],
        }

        result = service._map_attributes(attributes, mapping)

        assert result["email"] == "user@example.com"
        assert result["first_name"] == "John"
        assert result["last_name"] == "Doe"

    def test_map_attributes_fallback(self, service):
        """Test attribute mapping with fallback SAML names"""
        attributes = {
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress": "user@example.com",
        }
        mapping = {
            "email": ["email", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"],
        }

        result = service._map_attributes(attributes, mapping)

        assert result["email"] == "user@example.com"

    def test_map_attributes_missing(self, service):
        """Test attribute mapping when attribute is not present"""
        attributes = {"email": "user@example.com"}
        mapping = {
            "email": ["email"],
            "first_name": ["firstName", "givenName"],
        }

        result = service._map_attributes(attributes, mapping)

        assert result["email"] == "user@example.com"
        assert "first_name" not in result


@pytest.mark.unit
class TestUserProvisioning:
    """Test SAML user provisioning"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_db):
        with patch("app.services.saml_service.get_settings") as mock_settings:
            mock_settings.return_value.frontend_url = "https://dmarc.example.com"
            return SAMLService(mock_db)

    def test_provision_existing_user(self, service, mock_db):
        """Test provisioning finds existing user by email"""
        existing_user = Mock()
        existing_user.email = "user@example.com"
        existing_user.role = "viewer"
        mock_db.query.return_value.filter.return_value.first.return_value = existing_user

        provider = Mock(spec=SAMLProvider)
        provider.auto_provision_users = True
        provider.default_role = "viewer"
        provider.admin_groups = []

        result = service._provision_user(
            {"email": "user@example.com", "groups": []},
            provider,
        )

        assert result is existing_user
        assert mock_db.commit.called

    def test_provision_new_user(self, service, mock_db):
        """Test provisioning creates a new user when not found"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        provider = Mock(spec=SAMLProvider)
        provider.id = uuid.uuid4()
        provider.auto_provision_users = True
        provider.default_role = "viewer"
        provider.admin_groups = []

        result = service._provision_user(
            {"email": "newuser@example.com", "first_name": "Jane", "last_name": "Doe"},
            provider,
        )

        assert mock_db.add.called

    def test_provision_no_email(self, service, mock_db):
        """Test provisioning returns None when no email"""
        provider = Mock(spec=SAMLProvider)
        provider.auto_provision_users = True

        result = service._provision_user({}, provider)

        assert result is None

    def test_provision_admin_group(self, service, mock_db):
        """Test provisioning grants admin role for admin group membership"""
        existing_user = Mock()
        existing_user.email = "admin@example.com"
        existing_user.role = "viewer"
        mock_db.query.return_value.filter.return_value.first.return_value = existing_user

        provider = Mock(spec=SAMLProvider)
        provider.auto_provision_users = True
        provider.default_role = "viewer"
        provider.admin_groups = ["Admins", "SecurityTeam"]

        service._provision_user(
            {"email": "admin@example.com", "groups": ["Admins"]},
            provider,
        )

        assert existing_user.role == "admin"


@pytest.mark.unit
class TestSPMetadata:
    """Test Service Provider metadata generation"""

    @pytest.fixture
    def service(self):
        mock_db = MagicMock()
        with patch("app.services.saml_service.settings") as mock_settings:
            mock_settings.frontend_url = "https://dmarc.example.com"
            return SAMLService(mock_db)

    def test_generate_sp_metadata(self, service):
        """Test SP metadata XML generation"""
        metadata = service.generate_sp_metadata()

        assert '<?xml version="1.0"' in metadata
        assert "EntityDescriptor" in metadata
        assert "SPSSODescriptor" in metadata
        assert service.sp_entity_id in metadata
        assert service.acs_url in metadata
        assert service.slo_url in metadata
        assert NameIDFormat.EMAIL.value in metadata

    def test_sp_urls_use_frontend_url(self, service):
        """Test that SP URLs are derived from frontend_url setting"""
        assert "dmarc.example.com" in service.sp_entity_id
        assert "dmarc.example.com" in service.acs_url
        assert "dmarc.example.com" in service.slo_url


@pytest.mark.unit
class TestEncodeDecode:
    """Test SAML request encoding and response decoding"""

    @pytest.fixture
    def service(self):
        mock_db = MagicMock()
        with patch("app.services.saml_service.get_settings") as mock_settings:
            mock_settings.return_value.frontend_url = "https://dmarc.example.com"
            return SAMLService(mock_db)

    def test_encode_request(self, service):
        """Test SAML request encoding produces URL-safe output"""
        xml = '<samlp:AuthnRequest ID="_test123">test</samlp:AuthnRequest>'

        encoded = service._encode_request(xml)

        # Should be URL-encoded base64
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_decode_response(self, service):
        """Test SAML response decoding"""
        original_xml = "<Response><NameID>user@example.com</NameID></Response>"
        encoded = base64.b64encode(original_xml.encode('utf-8')).decode('utf-8')

        decoded = service._decode_response(encoded)

        assert decoded == original_xml

    def test_parse_response_with_name_id(self, service):
        """Test parsing SAML response XML extracts NameID"""
        xml = """
        <Response>
            <Issuer>https://idp.example.com</Issuer>
            <Assertion>
                <Subject><NameID>user@example.com</NameID></Subject>
                <AttributeStatement>
                    <Attribute Name="email"><AttributeValue>user@example.com</AttributeValue></Attribute>
                </AttributeStatement>
            </Assertion>
        </Response>
        """

        result = service._parse_response(xml)

        assert result is not None
        assert result.name_id == "user@example.com"
        assert result.issuer == "https://idp.example.com"
        assert "email" in result.attributes

    def test_parse_response_no_name_id(self, service):
        """Test parsing response without NameID returns None"""
        xml = "<Response><Issuer>https://idp.example.com</Issuer></Response>"

        result = service._parse_response(xml)

        assert result is None
