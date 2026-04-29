import json

from django.core.exceptions import ValidationError
from django.test import Client, TestCase

from .models import KnowledgeBaseVersion, ReturnSourceCaptureSession
from .services import (
    KnowledgeBasePackageService,
    KnowledgeBaseService,
    ReturnPreparationService,
    ReturnSourceCaptureService,
)


class ReturnPreparationServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        version = KnowledgeBasePackageService.import_package()
        KnowledgeBaseService.activate_version(version.id)

    def test_prepare_itr1_uses_document_backed_values_and_is_ready(self) -> None:
        payload = {
            "return_type": "ITR-1",
            "context": {
                "assessment_year": "2026-27",
                "financial_year": "2025-26",
                "basic_exemption_limit": 300000,
            },
            "declared_data": {
                "profile": {
                    "residential_status": "resident_ordinary",
                    "has_foreign_asset": False,
                    "has_foreign_signing_authority": False,
                    "has_foreign_source_income": False,
                    "is_director_in_company": False,
                    "held_unlisted_equity_shares": False,
                },
                "income": {
                    "salary_income": 1200000,
                    "total_income": 1200000,
                    "total_income_before_specified_exemptions_and_chapter_via": 1200000,
                    "house_property_count": 1,
                    "agricultural_income": 0,
                },
                "specified_triggers": {
                    "aggregate_tds_tcs": 45000,
                },
            },
            "documents": [
                {"document_type": "personal_info", "data": {"residential_status": "resident_ordinary"}},
                {
                    "document_type": "form16",
                    "data": {
                        "salary_income": 1200000,
                        "total_income": 1200000,
                        "total_income_before_specified_exemptions_and_chapter_via": 1200000,
                    },
                },
                {"document_type": "ais", "data": {"salary_income": 1200000, "aggregate_tds_tcs": 45000}},
                {"document_type": "form26as", "data": {"aggregate_tds_tcs": 45000}},
            ],
        }

        result = ReturnPreparationService.prepare(payload)

        self.assertTrue(result["ready_for_validation"])
        self.assertEqual(result["validation_payload"]["income"]["salary_income"], 1200000)
        self.assertEqual(result["validation_result"]["recommended_form"], "ITR-1")
        self.assertEqual(result["validation_result"]["filing_obligation"], "required")
        self.assertFalse(any(flag["severity"] == "error" for flag in result["flags"]))

    def test_prepare_itr2_flags_document_mismatch_and_still_builds_payload(self) -> None:
        payload = {
            "return_type": "ITR-2",
            "context": {
                "assessment_year": "2026-27",
                "financial_year": "2025-26",
                "basic_exemption_limit": 300000,
            },
            "declared_data": {
                "profile": {
                    "residential_status": "resident_ordinary",
                },
                "income": {
                    "salary_income": 900000,
                    "total_income": 1100000,
                    "total_income_before_specified_exemptions_and_chapter_via": 1100000,
                    "house_property_count": 1,
                    "short_term_capital_gains": 200000,
                    "other_capital_gains_amount": 0,
                    "ltcg_112a_amount": 0,
                },
            },
            "documents": [
                {"document_type": "personal_info", "data": {"residential_status": "resident_ordinary"}},
                {
                    "document_type": "form16",
                    "data": {
                        "salary_income": 900000,
                        "total_income": 1100000,
                        "total_income_before_specified_exemptions_and_chapter_via": 1100000,
                    },
                },
                {
                    "document_type": "ais",
                    "data": {
                        "salary_income": 900000,
                        "total_income": 1100000,
                        "short_term_capital_gains": 150000,
                        "aggregate_tds_tcs": 31000,
                    },
                },
                {"document_type": "form26as", "data": {"aggregate_tds_tcs": 31000}},
                {
                    "document_type": "capital_gains_statement",
                    "data": {
                        "short_term_capital_gains": 200000,
                        "other_capital_gains_amount": 0,
                        "ltcg_112a_amount": 0,
                    },
                },
            ],
        }

        result = ReturnPreparationService.prepare(payload)

        self.assertFalse(result["ready_for_validation"])
        self.assertEqual(result["validation_payload"]["income"]["short_term_capital_gains"], 200000)
        self.assertTrue(any(flag["code"] == "DOCUMENT_DATA_MISMATCH" for flag in result["flags"]))
        self.assertEqual(result["validation_result"]["recommended_form"], "ITR-2")


class ReturnPreparationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        if not KnowledgeBaseVersion.objects.filter(status=KnowledgeBaseVersion.Status.ACTIVE).exists():
            version = KnowledgeBasePackageService.import_package()
            KnowledgeBaseService.activate_version(version.id)

    def test_prepare_validation_endpoint_returns_prepared_payload(self) -> None:
        client = Client()
        response = client.post(
            "/api/returns/prepare-validation/",
            data=json.dumps(
                {
                    "return_type": "ITR-1",
                    "declared_data": {
                        "profile": {"residential_status": "resident_ordinary"},
                        "income": {
                            "salary_income": 600000,
                            "total_income": 600000,
                            "total_income_before_specified_exemptions_and_chapter_via": 600000,
                            "house_property_count": 1,
                        },
                    },
                    "documents": [
                        {"document_type": "personal_info", "data": {"residential_status": "resident_ordinary"}},
                        {
                            "document_type": "form16",
                            "data": {
                                "salary_income": 600000,
                                "total_income": 600000,
                                "total_income_before_specified_exemptions_and_chapter_via": 600000,
                            },
                        },
                        {"document_type": "ais", "data": {"salary_income": 600000}},
                        {"document_type": "form26as", "data": {"aggregate_tds_tcs": 20000}},
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("validation_payload", body)
        self.assertEqual(body["validation_result"]["recommended_form"], "ITR-1")


class ReturnSourceCaptureServiceTests(TestCase):
    def test_get_source_types_for_itr1_includes_mandatory_and_optional_sources(self) -> None:
        source_types = ReturnSourceCaptureService.get_source_types("ITR-1")

        self.assertEqual(source_types[0]["source_type"], "personal_info")
        self.assertTrue(any(item["source_type"] == "form16" and item["mandatory"] for item in source_types))
        self.assertTrue(any(item["source_type"] == "house_property_schedule" and not item["mandatory"] for item in source_types))

    def test_save_source_data_from_test_record_updates_session_status(self) -> None:
        session = ReturnSourceCaptureService.create_session({"return_type": "ITR-1"})

        for source_type, test_record_id in [
            ("personal_info", "pi_itr1_standard"),
            ("form16", "f16_itr1_salary"),
            ("form26as", "26as_standard"),
            ("ais", "ais_itr1_clean"),
        ]:
            ReturnSourceCaptureService.save_source_data(
                session.id,
                {
                    "source_type": source_type,
                    "test_record_id": test_record_id,
                },
            )

        session.refresh_from_db()
        self.assertEqual(session.status, ReturnSourceCaptureSession.Status.READY)
        self.assertEqual(session.source_records.count(), 4)

    def test_save_source_data_rejects_missing_fields(self) -> None:
        session = ReturnSourceCaptureService.create_session({"return_type": "ITR-1"})

        with self.assertRaisesMessage(ValidationError, "MISSING_SOURCE_FIELD"):
            ReturnSourceCaptureService.save_source_data(
                session.id,
                {
                    "source_type": "personal_info",
                    "source_data": {"pan": "ABCDE1234F"},
                },
            )


class ReturnSourceCaptureApiTests(TestCase):
    def test_source_types_endpoint_returns_itr2_source_catalog(self) -> None:
        client = Client()
        response = client.get("/api/return-sources/types/?return_type=ITR-2")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(any(item["source_type"] == "capital_gains_statement" for item in body["source_types"]))

    def test_session_create_and_save_source_data_flow(self) -> None:
        client = Client()
        create_response = client.post(
            "/api/return-sources/sessions/",
            data=json.dumps({"return_type": "ITR-1", "taxpayer_pan": "ABCDE1234F", "taxpayer_name": "Aarav Sharma"}),
            content_type="application/json",
        )

        self.assertEqual(create_response.status_code, 201)
        session = create_response.json()["session"]

        save_response = client.post(
            f"/api/return-sources/sessions/{session['id']}/records/",
            data=json.dumps({"source_type": "personal_info", "test_record_id": "pi_itr1_standard"}),
            content_type="application/json",
        )

        self.assertEqual(save_response.status_code, 200)
        saved = save_response.json()
        self.assertEqual(saved["saved_record"]["source_type"], "personal_info")
        self.assertEqual(saved["session"]["status"], "draft")

    def test_test_records_endpoint_can_filter_to_source_type(self) -> None:
        client = Client()
        response = client.get("/api/return-sources/test-records/?return_type=ITR-2&source_type=capital_gains_statement")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["test_records"]), 1)
        self.assertEqual(body["test_records"][0]["source_type"], "capital_gains_statement")
