"""Shared fixtures."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


SAMPLE_MBOX = textwrap.dedent(
    """\
    From alice@example.com Mon Jan  1 09:00:00 2024
    From: Alice <alice@example.com>
    To: Bob <bob@example.com>
    Cc: Carol <carol@example.com>
    Subject: Project kickoff
    Date: Mon, 1 Jan 2024 09:00:00 +0000
    Message-ID: <msg-1@example.com>
    X-GM-THRID: 1000000000000000001
    Content-Type: text/plain; charset=utf-8

    Hi Bob, let's start the project next week. We need to decide on stack.

    From bob@example.com Mon Jan  1 10:00:00 2024
    From: Bob <bob@example.com>
    To: Alice <alice@example.com>
    Cc: Carol <carol@example.com>
    Subject: Re: Project kickoff
    Date: Mon, 1 Jan 2024 10:00:00 +0000
    Message-ID: <msg-2@example.com>
    In-Reply-To: <msg-1@example.com>
    References: <msg-1@example.com>
    X-GM-THRID: 1000000000000000001
    Content-Type: text/plain; charset=utf-8

    Sounds good. I vote Python + FastAPI for the backend.

    From dave@example.com Tue Jan  2 08:00:00 2024
    From: Dave <dave@example.com>
    To: Alice <alice@example.com>
    Subject: Lunch tomorrow?
    Date: Tue, 2 Jan 2024 08:00:00 +0000
    Message-ID: <msg-3@example.com>
    X-GM-THRID: 1000000000000000002
    Content-Type: text/plain; charset=utf-8

    Want to grab lunch tomorrow at the new ramen place?

    """
)


@pytest.fixture
def sample_mbox_path(tmp_path: Path) -> Path:
    """A tiny mbox with two threads (one multi-message, one single)."""
    path = tmp_path / "sample.mbox"
    path.write_text(SAMPLE_MBOX)
    return path
