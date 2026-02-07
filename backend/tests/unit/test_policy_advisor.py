"""Unit tests for PolicyAdvisor (policy_advisor.py)"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from app.services.policy_advisor import (
    PolicyAdvisor,
    Recommendation,
    RecommendationType,
    RecommendationPriority,
    DomainHealthScore,
)


@pytest.mark.unit
class TestGetDomainStats:
    """Test domain statistics retrieval"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def advisor(self, mock_db):
        return PolicyAdvisor(mock_db)

    def test_get_domain_stats_success(self, advisor, mock_db):
        """Test getting stats for a domain with data"""
        report = Mock()
        report.id = uuid.uuid4()
        report.date_begin = datetime.utcnow() - timedelta(days=5)
        report.date_end = datetime.utcnow() - timedelta(days=4)
        report.p = "quarantine"

        mock_db.query.return_value.filter.return_value.all.return_value = [report]

        stats_row = Mock()
        stats_row.total_emails = 5000
        stats_row.dkim_pass = 4500
        stats_row.spf_pass = 4700
        stats_row.both_pass = 4300
        stats_row.both_fail = 200
        stats_row.unique_sources = 15

        mock_db.query.return_value.filter.return_value.first.return_value = stats_row

        result = advisor.get_domain_stats("example.com", days=30)

        assert result is not None
        assert result['domain'] == "example.com"
        assert result['total_emails'] == 5000
        assert result['current_policy'] == "quarantine"
        assert result['dkim_pass_rate'] == 4500 / 5000
        assert result['spf_pass_rate'] == 4700 / 5000
        assert result['dmarc_pass_rate'] == (5000 - 200) / 5000
        assert result['unique_sources'] == 15

    def test_get_domain_stats_no_reports(self, advisor, mock_db):
        """Test getting stats when no reports exist"""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = advisor.get_domain_stats("unknown.com")

        assert result is None

    def test_get_domain_stats_zero_emails(self, advisor, mock_db):
        """Test getting stats when total emails is zero"""
        report = Mock()
        report.id = uuid.uuid4()
        report.date_begin = datetime.utcnow() - timedelta(days=5)
        report.date_end = datetime.utcnow()
        report.p = "none"

        mock_db.query.return_value.filter.return_value.all.return_value = [report]

        stats_row = Mock()
        stats_row.total_emails = 0
        stats_row.dkim_pass = 0
        stats_row.spf_pass = 0
        stats_row.both_pass = 0
        stats_row.both_fail = 0
        stats_row.unique_sources = 0

        mock_db.query.return_value.filter.return_value.first.return_value = stats_row

        result = advisor.get_domain_stats("empty.com")

        assert result is None


@pytest.mark.unit
class TestDomainHealthScore:
    """Test domain health score calculation"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def advisor(self, mock_db):
        return PolicyAdvisor(mock_db)

    def test_health_score_excellent(self, advisor):
        """Test health score for a well-configured domain"""
        stats = {
            'domain': 'example.com',
            'total_emails': 50000,
            'unique_sources': 20,
            'current_policy': 'reject',
            'dkim_pass_rate': 0.99,
            'spf_pass_rate': 0.99,
            'dmarc_pass_rate': 0.99,
            'both_pass_rate': 0.98,
            'both_fail_rate': 0.01,
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            result = advisor.get_domain_health_score("example.com")

        assert result is not None
        assert result.grade == 'A'
        assert result.overall_score >= 90
        assert result.current_policy == 'reject'
        assert result.recommended_policy == 'reject'

    def test_health_score_poor(self, advisor):
        """Test health score for a poorly configured domain"""
        stats = {
            'domain': 'bad.com',
            'total_emails': 500,
            'unique_sources': 5,
            'current_policy': 'none',
            'dkim_pass_rate': 0.60,
            'spf_pass_rate': 0.70,
            'dmarc_pass_rate': 0.75,
            'both_pass_rate': 0.50,
            'both_fail_rate': 0.25,
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            result = advisor.get_domain_health_score("bad.com")

        assert result is not None
        assert result.overall_score < 70
        assert result.grade in ('D', 'F')
        assert len(result.issues) > 0

    def test_health_score_none_policy(self, advisor):
        """Test health score deducts points for 'none' policy"""
        stats = {
            'domain': 'monitor.com',
            'total_emails': 10000,
            'unique_sources': 10,
            'current_policy': 'none',
            'dkim_pass_rate': 0.99,
            'spf_pass_rate': 0.99,
            'dmarc_pass_rate': 0.99,
            'both_pass_rate': 0.99,
            'both_fail_rate': 0.01,
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            result = advisor.get_domain_health_score("monitor.com")

        assert result.overall_score < 100
        assert any("none" in issue.lower() for issue in result.issues)

    def test_health_score_low_volume(self, advisor):
        """Test health score notes low email volume"""
        stats = {
            'domain': 'small.com',
            'total_emails': 100,
            'unique_sources': 2,
            'current_policy': 'reject',
            'dkim_pass_rate': 1.0,
            'spf_pass_rate': 1.0,
            'dmarc_pass_rate': 1.0,
            'both_pass_rate': 1.0,
            'both_fail_rate': 0.0,
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            result = advisor.get_domain_health_score("small.com")

        assert any("low" in issue.lower() or "volume" in issue.lower() for issue in result.issues)

    def test_health_score_no_data(self, advisor):
        """Test health score returns None when no data available"""
        with patch.object(advisor, 'get_domain_stats', return_value=None):
            result = advisor.get_domain_health_score("nodata.com")

        assert result is None

    def test_health_score_recommends_quarantine_upgrade(self, advisor):
        """Test recommending upgrade from none to quarantine"""
        stats = {
            'domain': 'upgrade.com',
            'total_emails': 50000,
            'unique_sources': 20,
            'current_policy': 'none',
            'dkim_pass_rate': 0.99,
            'spf_pass_rate': 0.99,
            'dmarc_pass_rate': 0.99,
            'both_pass_rate': 0.98,
            'both_fail_rate': 0.01,
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            result = advisor.get_domain_health_score("upgrade.com")

        assert result.recommended_policy == 'quarantine'

    def test_health_score_recommends_reject_upgrade(self, advisor):
        """Test recommending upgrade from quarantine to reject"""
        stats = {
            'domain': 'upgrade2.com',
            'total_emails': 50000,
            'unique_sources': 20,
            'current_policy': 'quarantine',
            'dkim_pass_rate': 0.99,
            'spf_pass_rate': 0.99,
            'dmarc_pass_rate': 0.99,
            'both_pass_rate': 0.98,
            'both_fail_rate': 0.01,
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            result = advisor.get_domain_health_score("upgrade2.com")

        assert result.recommended_policy == 'reject'

    def test_health_score_grade_boundaries(self, advisor):
        """Test grade assignment at boundaries"""
        # Score = 100 (reject, 100% pass, high volume, good alignment)
        stats_a = {
            'domain': 'grade.com',
            'total_emails': 10000,
            'unique_sources': 10,
            'current_policy': 'reject',
            'dkim_pass_rate': 1.0,
            'spf_pass_rate': 1.0,
            'dmarc_pass_rate': 1.0,
            'both_pass_rate': 1.0,
            'both_fail_rate': 0.0,
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats_a):
            result = advisor.get_domain_health_score("grade.com")

        assert result.grade == 'A'
        assert result.overall_score == 100


@pytest.mark.unit
class TestPolicyRecommendation:
    """Test policy recommendation generation"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def advisor(self, mock_db):
        return PolicyAdvisor(mock_db)

    def test_recommend_upgrade_none_to_quarantine(self, advisor):
        """Test recommendation to upgrade from none to quarantine"""
        stats = {
            'dmarc_pass_rate': 0.99,
            'total_emails': 5000,
            'current_policy': 'none',
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            rec = advisor.get_policy_recommendation("example.com")

        assert rec is not None
        assert rec.type == RecommendationType.POLICY_UPGRADE
        assert rec.priority == RecommendationPriority.HIGH
        assert "quarantine" in rec.recommended_action.lower()
        assert rec.confidence == 0.95

    def test_recommend_upgrade_quarantine_to_reject(self, advisor):
        """Test recommendation to upgrade from quarantine to reject"""
        stats = {
            'dmarc_pass_rate': 0.99,
            'total_emails': 5000,
            'current_policy': 'quarantine',
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            rec = advisor.get_policy_recommendation("example.com")

        assert rec is not None
        assert rec.type == RecommendationType.POLICY_UPGRADE
        assert rec.priority == RecommendationPriority.MEDIUM
        assert "reject" in rec.recommended_action.lower()

    def test_recommend_low_volume(self, advisor):
        """Test recommendation for insufficient data"""
        stats = {
            'dmarc_pass_rate': 0.99,
            'total_emails': 500,  # Below MIN_EMAILS_FOR_RECOMMENDATION
            'current_policy': 'none',
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            rec = advisor.get_policy_recommendation("example.com")

        assert rec is not None
        assert rec.type == RecommendationType.LOW_VOLUME
        assert rec.priority == RecommendationPriority.INFO
        assert rec.confidence == 0.3

    def test_recommend_high_failure_critical(self, advisor):
        """Test critical recommendation for high failure rate with strict policy"""
        stats = {
            'dmarc_pass_rate': 0.80,  # Below POLICY_CONCERN_THRESHOLD
            'total_emails': 5000,
            'current_policy': 'reject',
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            rec = advisor.get_policy_recommendation("example.com")

        assert rec is not None
        assert rec.type == RecommendationType.HIGH_FAILURE
        assert rec.priority == RecommendationPriority.CRITICAL

    def test_no_recommendation_none_policy_moderate_pass(self, advisor):
        """Test no strong recommendation for moderate pass rate with none policy"""
        stats = {
            'dmarc_pass_rate': 0.85,  # Below threshold but policy is 'none'
            'total_emails': 5000,
            'current_policy': 'none',
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            rec = advisor.get_policy_recommendation("example.com")

        # With 'none' policy and sub-90% pass rate, no upgrade or critical recommendation
        assert rec is None

    def test_no_recommendation_no_data(self, advisor):
        """Test no recommendation when no stats available"""
        with patch.object(advisor, 'get_domain_stats', return_value=None):
            rec = advisor.get_policy_recommendation("nodata.com")

        assert rec is None

    def test_no_recommendation_already_at_reject_good_rate(self, advisor):
        """Test no recommendation when already at reject with good rate"""
        stats = {
            'dmarc_pass_rate': 0.99,
            'total_emails': 5000,
            'current_policy': 'reject',
        }

        with patch.object(advisor, 'get_domain_stats', return_value=stats):
            rec = advisor.get_policy_recommendation("example.com")

        # Already at reject with 99% pass rate - no further upgrade possible
        # The code only recommends upgrades for 'none' -> quarantine and
        # 'quarantine' -> reject, so reject with good rate returns None
        assert rec is None


@pytest.mark.unit
class TestFailingSenders:
    """Test failing sender detection"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def advisor(self, mock_db):
        return PolicyAdvisor(mock_db)

    def test_get_failing_senders_with_results(self, advisor, mock_db):
        """Test getting failing senders"""
        report_row = Mock()
        report_row.__getitem__ = lambda self, idx: uuid.uuid4()
        mock_db.query.return_value.filter.return_value.all.return_value = [(uuid.uuid4(),)]

        sender_row = Mock()
        sender_row.source_ip = "192.168.1.100"
        sender_row.total = 500
        sender_row.dkim_pass = 100
        sender_row.spf_pass = 100
        sender_row.both_fail = 300

        mock_db.query.return_value.filter.return_value.group_by.return_value.having.return_value.order_by.return_value.limit.return_value.all.return_value = [sender_row]

        result = advisor.get_failing_senders("example.com", days=30)

        assert len(result) == 1
        assert result[0]['source_ip'] == "192.168.1.100"
        assert result[0]['total_emails'] == 500
        assert result[0]['failure_rate'] == 300 / 500

    def test_get_failing_senders_no_reports(self, advisor, mock_db):
        """Test getting failing senders with no reports"""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = advisor.get_failing_senders("unknown.com")

        assert result == []

    def test_get_failing_senders_filters_low_failure(self, advisor, mock_db):
        """Test that senders with < 10% failure rate are excluded"""
        mock_db.query.return_value.filter.return_value.all.return_value = [(uuid.uuid4(),)]

        # Sender with very low failure rate
        sender_row = Mock()
        sender_row.source_ip = "10.0.0.1"
        sender_row.total = 1000
        sender_row.dkim_pass = 950
        sender_row.spf_pass = 980
        sender_row.both_fail = 10  # 1% failure rate

        mock_db.query.return_value.filter.return_value.group_by.return_value.having.return_value.order_by.return_value.limit.return_value.all.return_value = [sender_row]

        result = advisor.get_failing_senders("example.com")

        # Should be excluded because failure_rate (1%) < 10%
        assert len(result) == 0


@pytest.mark.unit
class TestNewSenderRecommendations:
    """Test new sender recommendation generation"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def advisor(self, mock_db):
        return PolicyAdvisor(mock_db)

    def test_sender_recommendations_alignment_issue(self, advisor):
        """Test recommendation for sender with both SPF and DKIM failing"""
        failing_senders = [{
            'source_ip': '192.168.1.1',
            'total_emails': 5000,
            'dkim_pass': 100,
            'spf_pass': 100,
            'both_fail': 4500,
            'failure_rate': 0.90,
            'dkim_pass_rate': 0.02,
            'spf_pass_rate': 0.02,
        }]

        with patch.object(advisor, 'get_failing_senders', return_value=failing_senders):
            recs = advisor.get_new_sender_recommendations("example.com")

        assert len(recs) == 1
        assert recs[0].type == RecommendationType.ALIGNMENT_ISSUE
        assert recs[0].priority == RecommendationPriority.HIGH  # Alignment issue

    def test_sender_recommendations_dkim_issue(self, advisor):
        """Test recommendation for sender with DKIM failing but SPF passing"""
        failing_senders = [{
            'source_ip': '10.0.0.1',
            'total_emails': 200,
            'dkim_pass': 20,
            'spf_pass': 180,
            'both_fail': 20,
            'failure_rate': 0.10,
            'dkim_pass_rate': 0.10,
            'spf_pass_rate': 0.90,
        }]

        with patch.object(advisor, 'get_failing_senders', return_value=failing_senders):
            recs = advisor.get_new_sender_recommendations("example.com")

        assert len(recs) == 1
        assert recs[0].type == RecommendationType.DKIM_ISSUE

    def test_sender_recommendations_spf_issue(self, advisor):
        """Test recommendation for sender with SPF failing but DKIM passing"""
        failing_senders = [{
            'source_ip': '172.16.0.1',
            'total_emails': 300,
            'dkim_pass': 250,
            'spf_pass': 50,
            'both_fail': 30,
            'failure_rate': 0.10,
            'dkim_pass_rate': 0.83,
            'spf_pass_rate': 0.17,
        }]

        with patch.object(advisor, 'get_failing_senders', return_value=failing_senders):
            recs = advisor.get_new_sender_recommendations("example.com")

        assert len(recs) == 1
        assert recs[0].type == RecommendationType.SPF_ISSUE

    def test_sender_recommendations_empty(self, advisor):
        """Test no recommendations when no failing senders"""
        with patch.object(advisor, 'get_failing_senders', return_value=[]):
            recs = advisor.get_new_sender_recommendations("example.com")

        assert len(recs) == 0

    def test_sender_recommendation_priority_levels(self, advisor):
        """Test priority level assignment based on volume and failure rate"""
        failing_senders = [
            {
                'source_ip': '1.1.1.1',
                'total_emails': 15000,
                'dkim_pass': 100,
                'spf_pass': 100,
                'both_fail': 10000,
                'failure_rate': 0.67,
                'dkim_pass_rate': 0.01,
                'spf_pass_rate': 0.01,
            },
            {
                'source_ip': '2.2.2.2',
                'total_emails': 2000,
                'dkim_pass': 100,
                'spf_pass': 100,
                'both_fail': 1800,
                'failure_rate': 0.90,
                'dkim_pass_rate': 0.05,
                'spf_pass_rate': 0.05,
            },
            {
                'source_ip': '3.3.3.3',
                'total_emails': 150,
                'dkim_pass': 10,
                'spf_pass': 10,
                'both_fail': 100,
                'failure_rate': 0.67,
                'dkim_pass_rate': 0.07,
                'spf_pass_rate': 0.07,
            },
        ]

        with patch.object(advisor, 'get_failing_senders', return_value=failing_senders):
            recs = advisor.get_new_sender_recommendations("example.com")

        assert len(recs) == 3
        # First: 15000 vol, 67% failure -> CRITICAL (vol >= 10000 and failure >= 0.5)
        assert recs[0].priority == RecommendationPriority.CRITICAL
        # Second: 2000 vol, 90% failure -> HIGH (vol >= 1000 or failure >= 0.8)
        assert recs[1].priority == RecommendationPriority.HIGH
        # Third: 150 vol, 67% failure -> MEDIUM (vol >= 100)
        assert recs[2].priority == RecommendationPriority.MEDIUM


@pytest.mark.unit
class TestAllRecommendations:
    """Test aggregated recommendation retrieval"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def advisor(self, mock_db):
        return PolicyAdvisor(mock_db)

    def test_get_all_recommendations(self, advisor, mock_db):
        """Test getting all recommendations across domains"""
        mock_db.query.return_value.distinct.return_value.all.return_value = [
            ("example.com",),
            ("test.com",),
        ]

        policy_rec = Recommendation(
            type=RecommendationType.POLICY_UPGRADE,
            priority=RecommendationPriority.HIGH,
            domain="example.com",
            title="Upgrade example.com",
            description="Ready for upgrade",
            current_state={"policy": "none"},
            recommended_action="Upgrade to quarantine",
            impact="Better protection",
            confidence=0.95,
        )

        sender_rec = Recommendation(
            type=RecommendationType.SPF_ISSUE,
            priority=RecommendationPriority.MEDIUM,
            domain="test.com",
            title="SPF issue on test.com",
            description="SPF failing",
            current_state={"source_ip": "1.2.3.4"},
            recommended_action="Fix SPF",
            impact="Authentication improvement",
            confidence=0.75,
        )

        with patch.object(advisor, 'get_policy_recommendation', side_effect=[policy_rec, None]):
            with patch.object(advisor, 'get_new_sender_recommendations', side_effect=[[], [sender_rec]]):
                recs = advisor.get_all_recommendations(days=30)

        assert len(recs) == 2
        # Should be sorted by priority - HIGH before MEDIUM
        assert recs[0].priority == RecommendationPriority.HIGH
        assert recs[1].priority == RecommendationPriority.MEDIUM

    def test_get_all_recommendations_respects_limit(self, advisor, mock_db):
        """Test that recommendations are limited"""
        mock_db.query.return_value.distinct.return_value.all.return_value = [
            ("a.com",),
        ]

        with patch.object(advisor, 'get_policy_recommendation', return_value=None):
            with patch.object(advisor, 'get_new_sender_recommendations', return_value=[]):
                recs = advisor.get_all_recommendations(days=30, limit=5)

        assert len(recs) <= 5


@pytest.mark.unit
class TestOverallHealth:
    """Test overall health summary"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def advisor(self, mock_db):
        return PolicyAdvisor(mock_db)

    def test_overall_health_no_domains(self, advisor, mock_db):
        """Test overall health when no domains exist"""
        mock_db.query.return_value.distinct.return_value.all.return_value = []

        result = advisor.get_overall_health()

        assert result['total_domains'] == 0
        assert result['overall_score'] == 0
        assert result['grade'] == 'N/A'

    def test_overall_health_with_domains(self, advisor, mock_db):
        """Test overall health with multiple domains"""
        mock_db.query.return_value.distinct.return_value.all.return_value = [
            ("good.com",),
            ("ok.com",),
        ]

        health_good = DomainHealthScore(
            domain="good.com",
            overall_score=95,
            pass_rate=0.99,
            spf_alignment_rate=0.99,
            dkim_alignment_rate=0.99,
            current_policy="reject",
            recommended_policy="reject",
            total_emails=50000,
            total_sources=20,
            issues=[],
            grade="A",
        )

        health_ok = DomainHealthScore(
            domain="ok.com",
            overall_score=75,
            pass_rate=0.92,
            spf_alignment_rate=0.90,
            dkim_alignment_rate=0.88,
            current_policy="quarantine",
            recommended_policy="quarantine",
            total_emails=10000,
            total_sources=10,
            issues=["DMARC pass rate could be improved"],
            grade="C",
        )

        with patch.object(
            advisor, 'get_domain_health_score',
            side_effect=[health_good, health_ok]
        ):
            result = advisor.get_overall_health()

        assert result['total_domains'] == 2
        assert result['analyzed_domains'] == 2
        assert result['overall_score'] == 85.0  # (95 + 75) / 2
        assert result['grade'] == 'B'
        assert result['total_emails'] == 60000
        assert result['total_sources'] == 30
        assert result['policy_breakdown']['reject'] == 1
        assert result['policy_breakdown']['quarantine'] == 1
        assert result['domains_at_reject'] == 1
        assert result['domains_needing_upgrade'] == 1

    def test_overall_health_all_domains_no_data(self, advisor, mock_db):
        """Test overall health when domains exist but have no data"""
        mock_db.query.return_value.distinct.return_value.all.return_value = [
            ("nodata1.com",),
            ("nodata2.com",),
        ]

        with patch.object(advisor, 'get_domain_health_score', return_value=None):
            result = advisor.get_overall_health()

        assert result['total_domains'] == 2
        assert result['analyzed_domains'] == 0
        assert result['overall_score'] == 0
