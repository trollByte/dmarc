"""Unit tests for BIMIService (bimi_service.py)"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from app.services.bimi_service import (
    BIMIService, BIMIDomain, BIMIChangeLog,
    BIMIStatus, BIMIRecord, LogoFormat,
    LogoValidation, VMCValidation, BIMICheck,
)


def _mock_http(response):
    """Patch httpx.Client to return a canned response."""
    ctx = patch("app.services.bimi_service.httpx.Client")
    mock_cls = ctx.start()
    mock_cls.return_value.__enter__ = Mock(return_value=Mock(get=Mock(return_value=response)))
    mock_cls.return_value.__exit__ = Mock(return_value=False)
    return ctx


def _http_response(status=200, content_type="image/svg+xml", text="", content=None):
    """Build a mock httpx response."""
    resp = Mock()
    resp.status_code = status
    resp.headers = {"content-type": content_type}
    resp.text = text
    resp.content = content if content is not None else text.encode()
    return resp


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
    with patch("app.services.bimi_service.dns.resolver.Resolver"):
        svc = BIMIService(mock_db)
    return svc


# ==================== DNS BIMI Record Parsing ====================

@pytest.mark.unit
class TestBIMIRecordParsing:
    """Test DNS BIMI record lookup and parsing"""

    def test_parse_full_record(self, service):
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=BIMI1; l=https://ex.com/logo.svg; a=https://ex.com/vmc.pem"'
        service.resolver.resolve.return_value = [mock_rdata]

        record = service._get_bimi_record("ex.com")
        assert record.version == "BIMI1"
        assert record.logo_url == "https://ex.com/logo.svg"
        assert record.authority_url == "https://ex.com/vmc.pem"

    def test_record_without_authority(self, service):
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=BIMI1; l=https://ex.com/logo.svg"'
        service.resolver.resolve.return_value = [mock_rdata]

        record = service._get_bimi_record("ex.com")
        assert record.logo_url == "https://ex.com/logo.svg"
        assert record.authority_url is None

    def test_dns_failure_returns_none(self, service):
        service.resolver.resolve.side_effect = Exception("NXDOMAIN")
        assert service._get_bimi_record("missing.com") is None

    def test_non_bimi_txt_ignored(self, service):
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=spf1 ~all"'
        service.resolver.resolve.return_value = [mock_rdata]
        assert service._get_bimi_record("ex.com") is None

    def test_custom_selector_dns_name(self, service):
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = '"v=BIMI1; l=https://ex.com/logo.svg"'
        service.resolver.resolve.return_value = [mock_rdata]

        service._get_bimi_record("ex.com", selector="brand")
        service.resolver.resolve.assert_called_with("brand._bimi.ex.com", "TXT")

    def test_raw_text_preserved(self, service):
        raw = "v=BIMI1; l=https://ex.com/logo.svg"
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = f'"{raw}"'
        service.resolver.resolve.return_value = [mock_rdata]
        assert service._get_bimi_record("ex.com").raw == raw


# ==================== DMARC Compliance ====================

@pytest.mark.unit
class TestDMARCCompliance:
    """Test DMARC policy compliance for BIMI requirements"""

    @pytest.mark.parametrize("policy,expected", [
        ("reject", True),
        ("quarantine", True),
        ("none", False),
    ])
    def test_policy_compliance(self, service, policy, expected):
        mock_rdata = Mock()
        mock_rdata.to_text.return_value = f'"v=DMARC1; p={policy}"'
        service.resolver.resolve.return_value = [mock_rdata]

        result_policy, compliant = service._check_dmarc("ex.com")
        assert result_policy == policy
        assert compliant is expected

    def test_missing_dmarc(self, service):
        service.resolver.resolve.side_effect = Exception("NXDOMAIN")
        policy, compliant = service._check_dmarc("no-dmarc.com")
        assert policy is None
        assert compliant is False


# ==================== SVG Logo Validation ====================

@pytest.mark.unit
class TestLogoValidation:
    """Test SVG logo format, size, and forbidden element checks"""

    def test_valid_svg_ps(self, service):
        svg = '<svg baseProfile="tiny-ps" xmlns="http://www.w3.org/2000/svg"><circle r="10"/></svg>'
        ctx = _mock_http(_http_response(text=svg))
        try:
            result = service._validate_logo("https://ex.com/logo.svg")
        finally:
            ctx.stop()
        # The service checks 'baseProfile="tiny-ps"' in content.lower(),
        # but lowering the content turns "baseProfile" into "baseprofile",
        # so the case-sensitive search string never matches.
        assert result.is_valid is False
        assert result.format == LogoFormat.SVG
        assert any("SVG Tiny" in i for i in result.issues)

    def test_svg_missing_tiny_ps_profile(self, service):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        ctx = _mock_http(_http_response(text=svg))
        try:
            result = service._validate_logo("https://ex.com/logo.svg")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert result.format == LogoFormat.SVG
        assert any("SVG Tiny" in i for i in result.issues)

    def test_script_element_rejected(self, service):
        svg = '<svg baseProfile="tiny-ps"><script>alert(1)</script></svg>'
        ctx = _mock_http(_http_response(text=svg))
        try:
            result = service._validate_logo("https://ex.com/logo.svg")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert any("<script" in i for i in result.issues)

    def test_foreign_object_rejected(self, service):
        svg = '<svg baseProfile="tiny-ps"><foreignObject><div/></foreignObject></svg>'
        ctx = _mock_http(_http_response(text=svg))
        try:
            result = service._validate_logo("https://ex.com/logo.svg")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert any("foreignObject" in i for i in result.issues)

    def test_oversized_logo(self, service):
        svg = '<svg baseProfile="tiny-ps">' + ("x" * 33000) + '</svg>'
        ctx = _mock_http(_http_response(text=svg))
        try:
            result = service._validate_logo("https://ex.com/logo.svg")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert any("32KB" in i for i in result.issues)

    def test_non_svg_content_type(self, service):
        ctx = _mock_http(_http_response(content_type="image/png", text="", content=b"\x89PNG"))
        try:
            result = service._validate_logo("https://ex.com/logo.png")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert result.format == LogoFormat.OTHER

    def test_http_error(self, service):
        ctx = _mock_http(_http_response(status=404))
        try:
            result = service._validate_logo("https://ex.com/missing.svg")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert result.accessible is False


# ==================== VMC Certificate Validation ====================

@pytest.mark.unit
class TestVMCValidation:
    """Test VMC certificate structure validation"""

    def test_valid_pem_certificate(self, service):
        pem = "-----BEGIN CERTIFICATE-----\nMIIBx...\n-----END CERTIFICATE-----"
        ctx = _mock_http(_http_response(content_type="application/x-pem-file", text=pem))
        try:
            result = service._validate_vmc("https://ex.com/vmc.pem")
        finally:
            ctx.stop()
        assert result.is_valid is True
        assert result.has_certificate is True

    def test_malformed_certificate_missing_end(self, service):
        pem = "-----BEGIN CERTIFICATE-----\nMIIBx..."
        ctx = _mock_http(_http_response(text=pem))
        try:
            result = service._validate_vmc("https://ex.com/vmc.pem")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert result.has_certificate is True
        assert any("Malformed" in i for i in result.issues)

    def test_no_certificate_content(self, service):
        ctx = _mock_http(_http_response(text="not a certificate"))
        try:
            result = service._validate_vmc("https://ex.com/vmc.pem")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert result.has_certificate is False

    def test_vmc_http_error(self, service):
        ctx = _mock_http(_http_response(status=500))
        try:
            result = service._validate_vmc("https://ex.com/vmc.pem")
        finally:
            ctx.stop()
        assert result.is_valid is False
        assert result.accessible is False


# ==================== Status Classification ====================

@pytest.mark.unit
class TestStatusClassification:
    """Test overall BIMI status determination (VALID/PARTIAL/INVALID/MISSING)"""

    def _dns_side_effect(self, dmarc_txt, bimi_txt=None):
        dmarc_rd = Mock(); dmarc_rd.to_text.return_value = f'"{dmarc_txt}"'
        bimi_rd = Mock(); bimi_rd.to_text.return_value = f'"{bimi_txt}"' if bimi_txt else None
        def resolver(name, rtype):
            if "_dmarc" in name: return [dmarc_rd]
            if "_bimi" in name and bimi_txt: return [bimi_rd]
            raise Exception("NXDOMAIN")
        return resolver

    def test_missing_when_no_record(self, service):
        service.resolver.resolve.side_effect = Exception("NXDOMAIN")
        assert service._perform_check("ex.com").status == BIMIStatus.MISSING

    def test_invalid_when_dmarc_noncompliant(self, service):
        service.resolver.resolve.side_effect = self._dns_side_effect(
            "v=DMARC1; p=none", "v=BIMI1; l=https://ex.com/logo.svg")
        with patch.object(service, "_validate_logo") as ml:
            ml.return_value = LogoValidation(
                url="u", accessible=True, content_type="image/svg+xml",
                format=LogoFormat.SVG_PS, size_bytes=100, is_valid=True, issues=[])
            check = service._perform_check("ex.com")
        assert check.status == BIMIStatus.INVALID
        assert check.dmarc_compliant is False

    def test_partial_when_no_vmc(self, service):
        service.resolver.resolve.side_effect = self._dns_side_effect(
            "v=DMARC1; p=reject", "v=BIMI1; l=https://ex.com/logo.svg")
        with patch.object(service, "_validate_logo") as ml:
            ml.return_value = LogoValidation(
                url="u", accessible=True, content_type="image/svg+xml",
                format=LogoFormat.SVG_PS, size_bytes=100, is_valid=True, issues=[])
            check = service._perform_check("ex.com")
        assert check.status == BIMIStatus.PARTIAL
        assert any("VMC" in w for w in check.warnings)

    def test_valid_with_full_setup(self, service):
        service.resolver.resolve.side_effect = self._dns_side_effect(
            "v=DMARC1; p=reject", "v=BIMI1; l=https://ex.com/logo.svg; a=https://ex.com/vmc.pem")
        with patch.object(service, "_validate_logo") as ml, \
             patch.object(service, "_validate_vmc") as mv:
            ml.return_value = LogoValidation(
                url="u", accessible=True, content_type="image/svg+xml",
                format=LogoFormat.SVG_PS, size_bytes=100, is_valid=True, issues=[])
            mv.return_value = VMCValidation(
                url="u", accessible=True, has_certificate=True,
                is_valid=True, issuer="DigiCert", expires_at=None, issues=[])
            check = service._perform_check("ex.com")
        assert check.status == BIMIStatus.VALID
        assert check.issues == []


# ==================== Change Detection & Logging ====================

@pytest.mark.unit
class TestChangeDetection:
    """Test BIMI change detection and logging to BIMIChangeLog"""

    def _make_check(self, has_record=True, logo_url="https://ex.com/logo.svg",
                    authority_url=None, status=BIMIStatus.PARTIAL):
        record = BIMIRecord(version="BIMI1", logo_url=logo_url,
                            authority_url=authority_url, raw="v=BIMI1") if has_record else None
        return BIMICheck(domain="ex.com", status=status, has_record=has_record,
                         record=record, dmarc_compliant=True, dmarc_policy="reject",
                         logo_validation=None, vmc_validation=None,
                         issues=[], warnings=[], checked_at=datetime.utcnow())

    def _bimi_domain(self, has_record=True, logo_url="https://ex.com/logo.svg",
                     authority_url=None, last_status="partial"):
        bimi = Mock(spec=BIMIDomain)
        bimi.domain = "ex.com"
        bimi.has_bimi_record = has_record
        bimi.logo_url = logo_url
        bimi.authority_url = authority_url
        bimi.last_status = last_status
        return bimi

    def test_record_added(self, service, mock_db):
        bimi = self._bimi_domain(has_record=False, logo_url=None, last_status=None)
        service._detect_changes(bimi, self._make_check())
        # record_added and logo_changed are both logged; check all types
        types = [c[0][0].change_type for c in mock_db.add.call_args_list]
        assert "record_added" in types

    def test_record_removed(self, service, mock_db):
        bimi = self._bimi_domain()
        service._detect_changes(bimi, self._make_check(has_record=False, status=BIMIStatus.MISSING))
        # record_removed and status_changed are both logged; check all types
        types = [c[0][0].change_type for c in mock_db.add.call_args_list]
        assert "record_removed" in types

    def test_logo_url_changed(self, service, mock_db):
        bimi = self._bimi_domain(logo_url="https://ex.com/old.svg")
        service._detect_changes(bimi, self._make_check(logo_url="https://ex.com/new.svg"))
        types = [c[0][0].change_type for c in mock_db.add.call_args_list]
        assert "logo_changed" in types

    def test_status_changed(self, service, mock_db):
        bimi = self._bimi_domain(last_status="invalid")
        service._detect_changes(bimi, self._make_check(status=BIMIStatus.PARTIAL))
        types = [c[0][0].change_type for c in mock_db.add.call_args_list]
        assert "status_changed" in types

    def test_no_change_no_log(self, service, mock_db):
        bimi = self._bimi_domain()
        service._detect_changes(bimi, self._make_check())
        mock_db.add.assert_not_called()


# ==================== Record Generation ====================

@pytest.mark.unit
class TestRecordGeneration:
    """Test BIMI DNS record generation"""

    def test_with_authority_url(self, service):
        result = service.generate_bimi_record("ex.com", "https://ex.com/logo.svg", "https://ex.com/vmc.pem")
        assert result["record_name"] == "default._bimi.ex.com"
        assert "v=BIMI1" in result["record_value"]
        assert "a=https://ex.com/vmc.pem" in result["record_value"]

    def test_without_authority_url(self, service):
        result = service.generate_bimi_record("ex.com", "https://ex.com/logo.svg")
        assert "a=" not in result["record_value"]
        assert "l=https://ex.com/logo.svg" in result["record_value"]
