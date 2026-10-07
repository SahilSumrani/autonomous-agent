from typing import Dict, Optional, Set
from packages.shared_types.agent import AgentState


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


VALID_STATE_TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
    AgentState.IDLE: {AgentState.OBSERVING, AgentState.PAUSED, AgentState.FAILED},
    AgentState.OBSERVING: {
        AgentState.RESEARCHING, AgentState.EVALUATING, AgentState.PAUSED,
        AgentState.BLOCKED, AgentState.COMPLETED, AgentState.FAILED
    },
    AgentState.RESEARCHING: {
        AgentState.EVALUATING, AgentState.OBSERVING, AgentState.PAUSED,
        AgentState.BLOCKED, AgentState.FAILED
    },
    AgentState.EVALUATING: {
        AgentState.LEAD_FOUND, AgentState.OBSERVING, AgentState.PAUSED,
        AgentState.BLOCKED, AgentState.FAILED
    },
    AgentState.LEAD_FOUND: {
        AgentState.RESEARCHING_PROFILE, AgentState.GENERATING_ACTION,
        AgentState.PAUSED, AgentState.COMPLETED, AgentState.FAILED
    },
    AgentState.RESEARCHING_PROFILE: {
        AgentState.GENERATING_ACTION, AgentState.COMPLETED,
        AgentState.PAUSED, AgentState.FAILED
    },
    AgentState.GENERATING_ACTION: {
        AgentState.WAITING_FOR_APPROVAL, AgentState.COMPLETED,
        AgentState.PAUSED, AgentState.FAILED
    },
    AgentState.WAITING_FOR_APPROVAL: {
        AgentState.EXECUTING, AgentState.COMPLETED,
        AgentState.PAUSED, AgentState.FAILED
    },
    AgentState.EXECUTING: {
        AgentState.COMPLETED, AgentState.OBSERVING, AgentState.FAILED
    },
    AgentState.PAUSED: {
        AgentState.OBSERVING, AgentState.RESEARCHING, AgentState.EVALUATING,
        AgentState.IDLE, AgentState.COMPLETED, AgentState.FAILED
    },
    AgentState.BLOCKED: {
        AgentState.IDLE, AgentState.OBSERVING, AgentState.PAUSED, AgentState.FAILED
    },
    AgentState.COMPLETED: {AgentState.IDLE},
    AgentState.FAILED: {AgentState.IDLE},
}


class BrowserAgentStateMachine:
    """Manages the operational lifecycle of a user-authorized browser agent session."""

    def __init__(self, initial_state: AgentState = AgentState.IDLE):
        self._current_state: AgentState = initial_state
        self._previous_state: Optional[AgentState] = None

    @property
    def current_state(self) -> AgentState:
        return self._current_state

    @property
    def previous_state(self) -> Optional[AgentState]:
        return self._previous_state

    def can_transition_to(self, target_state: AgentState) -> bool:
        allowed = VALID_STATE_TRANSITIONS.get(self._current_state, set())
        return target_state in allowed

    def transition_to(self, target_state: AgentState) -> AgentState:
        if target_state == self._current_state:
            return self._current_state

        if not self.can_transition_to(target_state):
            raise InvalidStateTransitionError(
                f"Cannot transition from {self._current_state.value} to {target_state.value}. "
                f"Permitted targets: {[s.value for s in VALID_STATE_TRANSITIONS.get(self._current_state, set())]}"
            )

        self._previous_state = self._current_state
        self._current_state = target_state
        return self._current_state

    def pause(self) -> AgentState:
        return self.transition_to(AgentState.PAUSED)

    def resume(self) -> AgentState:
        target = self._previous_state if self._previous_state and self._previous_state != AgentState.PAUSED else AgentState.OBSERVING
        return self.transition_to(target)

    def block(self) -> AgentState:
        return self.transition_to(AgentState.BLOCKED)

    def fail(self) -> AgentState:
        return self.transition_to(AgentState.FAILED)
