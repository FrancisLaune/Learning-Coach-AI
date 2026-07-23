from typing import Protocol

from domain.onboarding.events import OnboardingEvent
from domain.onboarding.models import OnboardingRequest, OnboardingResult


class OnboardingRepository(Protocol):
    def complete(
        self, request: OnboardingRequest, result: OnboardingResult, events: tuple[OnboardingEvent, ...]
    ) -> OnboardingResult: ...
    def known_subject_ids(self) -> set[int]: ...


LearnerProfileRepository = OnboardingRepository
JourneyVersionRepository = OnboardingRepository
