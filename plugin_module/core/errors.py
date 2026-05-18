"""Domain-specific errors. Caught at handler boundary and turned into ephemeral replies."""


class DndPluginError(Exception):
    """Base class for plugin domain errors."""

    user_message: str = "Something went wrong."


class PermissionDenied(DndPluginError):
    user_message = "You don't have permission to do that."


class CampaignNotFound(DndPluginError):
    user_message = "Campaign not found."


class SessionNotFound(DndPluginError):
    user_message = "Session not found."


class QuestNotFound(DndPluginError):
    user_message = "Quest not found."


class NpcNotFound(DndPluginError):
    user_message = "NPC not found."


class NoteNotFound(DndPluginError):
    user_message = "Note not found."


class CampaignNotConfigured(DndPluginError):
    user_message = (
        "This campaign has no announcement channel configured yet. "
        "Run `/campaign settings` first."
    )


class InvalidInput(DndPluginError):
    user_message = "Some of the input was invalid."

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        if message:
            self.user_message = message


class NotAllowed(DndPluginError):
    """Allowed by role but not by current campaign configuration (e.g. maybe disabled)."""

    user_message = "That action is not allowed in this campaign's current settings."

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        if message:
            self.user_message = message
