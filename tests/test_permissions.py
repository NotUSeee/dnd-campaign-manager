"""Permission predicates — pure functions on event dicts."""
import pytest

from plugin_module.core import permissions


def _event(*, user_id: str = "1001", roles=None, perms_bits: int = 0):
    return {
        "member": {
            "user": {"id": user_id},
            "roles": list(roles or []),
            "permissions": str(perms_bits),
        },
        "user_id": user_id,
    }


def test_is_server_admin_true_when_administrator_bit_set():
    assert permissions.is_server_admin(_event(perms_bits=0x8)) is True


def test_is_server_admin_false_when_no_bit():
    assert permissions.is_server_admin(_event(perms_bits=0)) is False


def test_is_server_admin_handles_missing_member():
    assert permissions.is_server_admin({}) is False


def test_is_server_admin_handles_garbage_perms():
    assert permissions.is_server_admin({"member": {"permissions": "not-a-number"}}) is False


def test_is_campaign_owner_matches_owner():
    event = _event(user_id="1001")
    assert permissions.is_campaign_owner(event, {"owner_user_id": 1001}) is True


def test_is_campaign_owner_mismatch():
    event = _event(user_id="2002")
    assert permissions.is_campaign_owner(event, {"owner_user_id": 1001}) is False


def test_is_campaign_owner_handles_none_campaign():
    assert permissions.is_campaign_owner(_event(), None) is False


def test_is_dm_role_no_config_returns_false():
    assert permissions.is_dm_role(_event(roles=["1"]), {"dm_role_id": None}) is False


def test_is_dm_role_matches_role():
    assert permissions.is_dm_role(
        _event(roles=["55555"]), {"dm_role_id": 55555}
    ) is True


def test_is_dm_role_when_role_not_held():
    assert permissions.is_dm_role(
        _event(roles=["7777"]), {"dm_role_id": 55555}
    ) is False


def test_is_player_open_when_no_role_configured():
    assert permissions.is_player(_event(), {"player_role_id": None}) is True


def test_is_player_requires_role_when_configured():
    assert permissions.is_player(_event(roles=["7777"]), {"player_role_id": 66666}) is False
    assert permissions.is_player(_event(roles=["66666"]), {"player_role_id": 66666}) is True


def test_can_manage_campaign_via_admin():
    assert permissions.can_manage_campaign(
        _event(perms_bits=0x8), {"owner_user_id": 9}, {}
    ) is True


def test_can_manage_campaign_via_owner():
    assert permissions.can_manage_campaign(
        _event(user_id="1001"), {"owner_user_id": 1001}, {}
    ) is True


def test_can_manage_campaign_via_dm_role():
    assert permissions.can_manage_campaign(
        _event(roles=["55555"]), {"owner_user_id": 9}, {"dm_role_id": 55555}
    ) is True


def test_can_manage_campaign_denies_random_player():
    assert permissions.can_manage_campaign(
        _event(roles=["7777"]), {"owner_user_id": 9}, {"dm_role_id": 55555}
    ) is False


def test_require_can_manage_denies_with_ephemeral_message(ctx):
    event = _event(user_id="2002")
    ok = permissions.require_can_manage(ctx, event, {"owner_user_id": 1001}, {})
    assert ok is False
    assert len(ctx.interaction.responses) == 1
    assert ctx.interaction.responses[0]["ephemeral"] is True
    assert "permission" in ctx.interaction.responses[0]["content"].lower()


def test_require_can_manage_allows_with_no_message(ctx):
    event = _event(perms_bits=0x8)
    ok = permissions.require_can_manage(ctx, event, {"owner_user_id": 9}, {})
    assert ok is True
    assert ctx.interaction.responses == []


def test_require_can_view_dm_notes_denies_player(ctx):
    event = _event(roles=["7777"])
    ok = permissions.require_can_view_dm_notes(ctx, event, {"owner_user_id": 9}, {"dm_role_id": 55555})
    assert ok is False
    assert "DM-only" in ctx.interaction.responses[0]["content"]
