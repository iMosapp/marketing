"""Preview-only switches must be inert in production even when the Deploy step copied their preview value into the Secrets.
Pure unit test: swaps MONGO_URL between the preview (localhost) and a production-looking URL."""
import os
from unittest import mock

PREVIEW = {"MONGO_URL": "mongodb://localhost:27017"}
PROD = {"MONGO_URL": "mongodb+srv://user:pw@cluster0.mongodb.net/imos"}
LEAKED = {"VOICE_FAKE_PROVIDER_ALLOWED": "1", "BILLING_ALLOW_TEST_MODE": "1", "APPRAISAL_ALLOW_DEV_MARKET": "1",
          "INTEL_FACTS_INGEST": "true", "INTEL_LEGACY_PROJECTION": "true", "INTEL_BACKFILL_EXECUTE": "true", "INTEL_NUDGES": "true",
          "WIDGET_RING_DRY_RUN": "true", "LEAD_SHOP_BUY_NUMBERS": "false", "STRIPE_BILLING_SECRET_KEY": "rk_test_fake"}


def _all_flags():
    from services import voice_controls, billing
    from services.appraisals import workflow
    from services.intelligence import config
    return {"fake_voice": voice_controls.fake_provider_allowed(), "billing_test_mode": billing.conversion_enabled(),
            "dev_market": workflow.development_basis_allowed(), **{f"intel_{k}": v for k, v in config.flags().items()}}


def test_leaked_preview_values_are_inert_in_production():
    with mock.patch.dict(os.environ, {**PROD, **LEAKED}):
        assert all(v is False for v in _all_flags().values()), _all_flags()


def test_same_values_work_in_preview():
    with mock.patch.dict(os.environ, {**PREVIEW, **LEAKED}):
        assert all(v is True for v in _all_flags().values()), _all_flags()


def test_production_opt_in_is_explicit():
    from services.intelligence import config
    from services import billing
    with mock.patch.dict(os.environ, {**PROD, **LEAKED, "INTEL_FACTS_INGEST": "production"}):
        f = config.flags()
        assert f["ingest"] is True and f["legacy_projection"] is False and f["nudges"] is False
        assert billing.conversion_enabled() is False, "a test Stripe key never converts in production"
    with mock.patch.dict(os.environ, {**PROD, **LEAKED, "STRIPE_BILLING_SECRET_KEY": "rk_live_fake"}):
        assert billing.conversion_enabled() is True, "a live key converts regardless of the preview switch"
