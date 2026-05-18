"""Modal field-set builders."""
from plugin_module.ui import modals


def test_campaign_create_fields_have_five_fields():
    fields = modals.campaign_create_fields()
    assert len(fields) == 5
    assert fields[0].custom_id == "name"
    assert fields[0].required is True


def test_session_schedule_fields_use_campaign_timezone():
    fields = modals.session_schedule_fields(campaign_tz="America/New_York")
    placeholder = fields[1].placeholder  # time_local
    assert "America/New_York" in placeholder


def test_session_schedule_fields_pre_fill_defaults():
    fields = modals.session_schedule_fields(
        campaign_tz="UTC",
        default_date="2026-06-22",
        default_time_local="19:00",
        default_duration=180,
    )
    date_field = next(f for f in fields if f.custom_id == "date")
    time_field = next(f for f in fields if f.custom_id == "time_local")
    duration_field = next(f for f in fields if f.custom_id == "duration_min")
    assert date_field.value == "2026-06-22"
    assert time_field.value == "19:00"
    assert duration_field.value == "180"


def test_recap_fields_have_five_fields():
    fields = modals.recap_fields(default_title="Session 5 recap")
    assert len(fields) == 5
    assert fields[0].value == "Session 5 recap"
    assert any(f.custom_id == "summary" for f in fields)


def test_recap_summary_is_required():
    fields = modals.recap_fields()
    summary = next(f for f in fields if f.custom_id == "summary")
    assert summary.required is True


def test_dmnote_add_fields():
    fields = modals.dmnote_add_fields()
    assert len(fields) == 2
    assert {f.custom_id for f in fields} == {"title", "body"}
    assert all(f.required for f in fields)


def test_settings_channels_fields_pre_fill_from_settings():
    fields = modals.settings_channels_fields({
        "announce_channel_id": 100, "recap_channel_id": 200, "reminder_channel_id": None,
    })
    assert len(fields) == 3
    by_id = {f.custom_id: f for f in fields}
    assert by_id["announce_channel_id"].value == "100"
    assert by_id["recap_channel_id"].value == "200"
    assert by_id["reminder_channel_id"].value == ""
    assert by_id["announce_channel_id"].required is True


def test_settings_roles_fields_optional():
    fields = modals.settings_roles_fields({})
    assert len(fields) == 2
    assert all(f.required is False for f in fields)


def test_settings_reminders_fields_serializes_offsets():
    fields = modals.settings_reminders_fields({"reminder_offsets_minutes": [1440, 120, 15]})
    assert len(fields) == 1
    assert fields[0].value == "1440,120,15"


def test_settings_defaults_fields_renders_existing():
    fields = modals.settings_defaults_fields({
        "default_day_of_week": 2, "default_time_local": "19:00",
    })
    by_id = {f.custom_id: f for f in fields}
    assert by_id["default_day_of_week"].value == "2"
    assert by_id["default_time_local"].value == "19:00"


def test_settings_defaults_fields_handles_none():
    fields = modals.settings_defaults_fields({})
    by_id = {f.custom_id: f for f in fields}
    assert by_id["default_day_of_week"].value == ""
    assert by_id["default_time_local"].value == ""


def test_alt_time_fields():
    fields = modals.alt_time_fields(campaign_tz="UTC")
    assert len(fields) == 3
    by_id = {f.custom_id: f for f in fields}
    assert by_id["date"].required is True
    assert by_id["time_local"].required is True
    assert by_id["reason"].required is False
