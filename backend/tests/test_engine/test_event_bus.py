import pytest
import asyncio

from app.engine.event_bus import EventBus, Event


def test_event_bus_subscribe_and_publish():
    bus = EventBus()
    received = []

    def handler(event: Event):
        received.append(event)

    bus.subscribe("node_started", handler)
    # publish is async so use pytest.mark.asyncio
    import asyncio
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="node_started", task_id="t1", node_id="n1")))

    assert len(received) == 1
    assert received[0].node_id == "n1"


@pytest.mark.asyncio
async def test_event_bus_async_subscriber():
    bus = EventBus()
    received: list[Event] = []

    async def async_handler(event: Event):
        received.append(event)

    bus.subscribe("node_completed", async_handler)
    await bus.publish(Event(type="node_completed", task_id="t1", node_id="n1"))

    assert len(received) == 1


@pytest.mark.asyncio
async def test_event_bus_multiple_subscribers():
    bus = EventBus()
    a: list[Event] = []
    b: list[Event] = []

    bus.subscribe("task_completed", lambda e: a.append(e))
    bus.subscribe("task_completed", lambda e: b.append(e))
    await bus.publish(Event(type="task_completed", task_id="t1"))

    assert len(a) == 1
    assert len(b) == 1


def test_event_bus_history():
    bus = EventBus()
    assert len(bus.get_history()) == 0

    import asyncio
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="a", task_id="t1")))
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="b", task_id="t2")))
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="a", task_id="t1")))

    history = bus.get_history()
    assert len(history) == 3


def test_event_bus_history_filter_by_task_id():
    bus = EventBus()
    import asyncio
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="a", task_id="t1")))
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="b", task_id="t2")))
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="a", task_id="t1")))

    t1_events = bus.get_history(task_id="t1")
    assert len(t1_events) == 2

    t2_events = bus.get_history(task_id="t2")
    assert len(t2_events) == 1


def test_event_bus_get_history_returns_copy():
    bus = EventBus()
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="x", task_id="t1")))

    history1 = bus.get_history()
    history2 = bus.get_history()

    assert history1 is not history2
    assert history1 == history2


def test_event_bus_unsubscribe_not_possible_without_ref():
    """Removing a subscriber requires keeping a reference — this is a known limitation documented here."""
    bus = EventBus()
    results: list[Event] = []

    def handler(e: Event):
        results.append(e)

    bus.subscribe("node_started", handler)
    asyncio.get_event_loop().run_until_complete(bus.publish(Event(type="node_started", task_id="t1", node_id="n1")))
    assert len(results) == 1