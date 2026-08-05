"""The deploy-time decision about whether to re-seed the demo neighborhood.

This logic used to be "does the Sunset Park community exist? then skip", which
meant a database seeded once never picked up demo data added later — every
feature that shipped with seeded content had none of it in production, and the
deploy log said "already present — skipping" the whole time.

These tests pin the decision itself. They don't run the seed (that truncates
tables and takes seconds); they check the branch that decides, which is where
the bug was.
"""

import pytest

from app.models import SeedState


@pytest.fixture
def seed_prod(monkeypatch):
    """Import scripts/seed_prod with its sibling directory importable."""
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    sys.modules.pop("seed_prod", None)
    import seed_prod as module

    return module


async def _record_version(version: int) -> None:
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        session.add(SeedState(version=version, label="test"))
        await session.commit()


async def _seed_ran(seed_prod, monkeypatch, *, demo_present, recorded, wanted):
    """Run main() with the world stubbed, and report whether it seeded."""
    ran = {"value": False}

    async def fake_seed():
        ran["value"] = True

    class FakeSeedDemo:
        SEED_VERSION = wanted
        main = staticmethod(fake_seed)

    import sys

    monkeypatch.setitem(sys.modules, "seed_demo", FakeSeedDemo)
    monkeypatch.setenv("SEED_DEMO", "true")

    async def fake_state():
        return demo_present, recorded, 17

    monkeypatch.setattr(seed_prod, "_state", fake_state)
    await seed_prod.main()
    return ran["value"]


# ---- when it must seed -----------------------------------------------------


async def test_seeds_when_the_demo_is_missing(seed_prod, monkeypatch):
    assert await _seed_ran(
        seed_prod, monkeypatch, demo_present=False, recorded=None, wanted=5
    )


async def test_seeds_when_the_demo_exists_but_has_no_recorded_version(
    seed_prod, monkeypatch
):
    """The regression. This is the state of any database seeded before versions
    existed — it is missing everything added to the seed since, and the old code
    skipped it."""
    assert await _seed_ran(
        seed_prod, monkeypatch, demo_present=True, recorded=None, wanted=5
    )


async def test_seeds_when_the_recorded_version_is_older(seed_prod, monkeypatch):
    assert await _seed_ran(
        seed_prod, monkeypatch, demo_present=True, recorded=2, wanted=5
    )


# ---- when it must not -----------------------------------------------------


async def test_does_not_seed_when_the_version_matches(seed_prod, monkeypatch):
    """The common case on every redeploy — a free dyno waking up must not wipe
    the database."""
    assert not await _seed_ran(
        seed_prod, monkeypatch, demo_present=True, recorded=5, wanted=5
    )


async def test_does_not_seed_when_the_database_is_newer_than_the_build(
    seed_prod, monkeypatch
):
    """A rollback to an older image. Destroying newer data to install older data
    is the wrong direction."""
    assert not await _seed_ran(
        seed_prod, monkeypatch, demo_present=True, recorded=9, wanted=5
    )


@pytest.mark.parametrize("value", ["", "false", "no", "0", "off"])
async def test_does_not_seed_when_seed_demo_is_off(seed_prod, monkeypatch, value):
    """A real deployment sets this false, and then nothing here may touch the
    database whatever the versions say."""
    ran = {"value": False}

    async def fake_seed():
        ran["value"] = True

    class FakeSeedDemo:
        SEED_VERSION = 5
        main = staticmethod(fake_seed)

    import sys

    monkeypatch.setitem(sys.modules, "seed_demo", FakeSeedDemo)
    monkeypatch.setenv("SEED_DEMO", value)
    await seed_prod.main()
    assert ran["value"] is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_the_enable_flag_accepts_the_usual_spellings(seed_prod, monkeypatch, value):
    monkeypatch.setenv("SEED_DEMO", value)
    assert seed_prod._enabled() is True


# ---- the version marker itself --------------------------------------------


async def test_the_recorded_version_is_readable(client):
    """`_state` reads the most recent row; two rows must not confuse it."""
    await _record_version(3)
    await _record_version(7)

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    sys.modules.pop("seed_prod", None)
    import seed_prod

    _, version, _ = await seed_prod._state()
    assert version == 7


def test_the_seed_declares_a_version_and_a_label():
    """Both are read by seed_prod and printed on deploy, so neither may vanish."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import seed_demo

    assert isinstance(seed_demo.SEED_VERSION, int)
    assert seed_demo.SEED_VERSION >= 5
    assert seed_demo.SEED_LABEL
