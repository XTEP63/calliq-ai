from collections.abc import Iterable, Mapping

from src.core.models import Analysis


def visible_analyses(saved: Iterable[Analysis], session: Mapping[str, Analysis]) -> list[Analysis]:
    """Overlay this visitor's analyses on bundled or locally saved calls."""
    by_id = {call.call_id: call for call in saved}
    by_id.update({call.call_id: call for call in session.values()})
    return sorted(by_id.values(), key=lambda call: call.created_at, reverse=True)
