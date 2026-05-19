"""Slash command option tree navigation."""
from plugin_module.core import option_reader


def test_get_subcommand():
    event = {"options": [{"name": "create", "type": 1, "options": []}]}
    assert option_reader.get_subcommand(event) == "create"


def test_get_subcommand_without_type_field():
    """Some Discord delivery paths omit type:1 on a subcommand with no params."""
    event = {"options": [{"name": "create"}]}
    assert option_reader.get_subcommand(event) == "create"


def test_get_subcommand_with_nested_options_no_type():
    """Subcommand with nested options but missing the type field."""
    event = {"options": [{"name": "settings", "options": [
        {"name": "campaign_id", "type": 4, "value": 42}
    ]}]}
    assert option_reader.get_subcommand(event) == "settings"


def test_get_subcommand_returns_none_for_value_carrying_option():
    """A regular parameter (has `value`) is NOT a subcommand."""
    event = {"options": [{"name": "arg", "type": 3, "value": "x"}]}
    assert option_reader.get_subcommand(event) is None


def test_get_subcommand_none_when_no_options():
    assert option_reader.get_subcommand({}) is None
    assert option_reader.get_subcommand({"options": []}) is None


def test_get_option_int_works_when_subcommand_missing_type():
    """_subcommand_options must also fall back when type is absent."""
    event = {"options": [{"name": "settings", "options": [
        {"name": "campaign_id", "type": 4, "value": "42"}
    ]}]}
    assert option_reader.get_option_int(event, "campaign_id") == 42


def test_get_option_int_extracts_value():
    event = {"options": [{"name": "info", "type": 1, "options": [
        {"name": "campaign_id", "type": 4, "value": "42"}
    ]}]}
    assert option_reader.get_option_int(event, "campaign_id") == 42


def test_get_option_int_returns_none_for_missing():
    event = {"options": [{"name": "info", "type": 1, "options": []}]}
    assert option_reader.get_option_int(event, "campaign_id") is None


def test_get_option_str():
    event = {"options": [{"name": "list", "type": 1, "options": [
        {"name": "scope", "type": 3, "value": "upcoming"}
    ]}]}
    assert option_reader.get_option_str(event, "scope") == "upcoming"


def test_get_option_user_id():
    event = {"options": [{"name": "add", "type": 1, "options": [
        {"name": "user", "type": 6, "value": "1001"}
    ]}]}
    assert option_reader.get_option_user_id(event, "user") == "1001"


def test_get_modal_value():
    event = {"modal_values": {"summary": "  hello world  "}}
    assert option_reader.get_modal_value(event, "summary") == "hello world"


def test_get_modal_value_missing_returns_empty():
    assert option_reader.get_modal_value({}, "x") == ""


def test_get_invoking_user_id_prefers_member_user():
    event = {"member": {"user": {"id": "1001"}}, "user_id": "2002"}
    assert option_reader.get_invoking_user_id(event) == "1001"


def test_get_invoking_user_id_falls_back_to_user_id():
    event = {"user_id": "2002"}
    assert option_reader.get_invoking_user_id(event) == "2002"
