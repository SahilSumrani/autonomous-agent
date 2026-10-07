from typing import Tuple
from packages.shared_types.outreach import OutreachChannel


class ChannelLimits:
    LIMITS = {
        OutreachChannel.INSTAGRAM_DM: (50, 700),
        OutreachChannel.REDDIT_REPLY: (80, 1200),
        OutreachChannel.LINKEDIN_MESSAGE: (100, 1000),
        OutreachChannel.EMAIL: (100, 2000),
    }

    @classmethod
    def get_bounds(cls, channel: OutreachChannel) -> Tuple[int, int]:
        return cls.LIMITS.get(channel, (50, 1000))

    @classmethod
    def is_within_bounds(cls, channel: OutreachChannel, text: str) -> bool:
        min_len, max_len = cls.get_bounds(channel)
        return min_len <= len(text.strip()) <= max_len
