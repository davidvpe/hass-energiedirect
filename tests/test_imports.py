"""Smoke tests — verify all modules import without errors."""


def test_import_pricing():
    import custom_components.energiedirect.pricing  # noqa: F401


def test_import_api_client():
    import custom_components.energiedirect.api_client  # noqa: F401


def test_import_const():
    import custom_components.energiedirect.const  # noqa: F401


def test_import_config_flow():
    import custom_components.energiedirect.config_flow  # noqa: F401


def test_import_coordinator():
    import custom_components.energiedirect.coordinator  # noqa: F401


