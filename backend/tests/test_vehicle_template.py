"""
Tests for resolve_template_variables - {vehicle} and {purchase} template variable logic.
Tests purchase_history resolution, legacy vehicle fallback, and {purchase} alias.
"""
import pytest
import asyncio
import sys
import os

sys.path.insert(0, "/app/backend")

from scheduler import resolve_template_variables


@pytest.mark.anyio
async def test_vehicle_from_purchase_history():
    """resolve {vehicle} using most recent purchase_history title"""
    contact = {
        "first_name": "John",
        "last_name": "Doe",
        "purchase_history": [{"title": "Road Glide", "date": "2024-01-15"}],
        "vehicle": "OldBike"
    }
    message = "Hey {first_name}, how is your {vehicle} treating you?"
    result = await resolve_template_variables(None, message, contact, "user1")
    assert result == "Hey John, how is your Road Glide treating you?", f"Got: {result}"
    print(f"PASS test_vehicle_from_purchase_history: {result}")


@pytest.mark.anyio
async def test_vehicle_fallback_legacy():
    """resolve {vehicle} using legacy vehicle field when purchase_history is empty"""
    contact = {
        "first_name": "Jane",
        "last_name": "Smith",
        "purchase_history": [],
        "vehicle": "Mojave"
    }
    message = "Your {vehicle} is ready!"
    result = await resolve_template_variables(None, message, contact, "user1")
    assert result == "Your Mojave is ready!", f"Got: {result}"
    print(f"PASS test_vehicle_fallback_legacy: {result}")


@pytest.mark.anyio
async def test_purchase_alias_for_vehicle():
    """{purchase} is an alias for {vehicle}"""
    contact = {
        "first_name": "Bob",
        "purchase_history": [{"title": "Iron 883", "date": "2023-06-10"}],
    }
    message = "Your {purchase} service is scheduled."
    result = await resolve_template_variables(None, message, contact, "user1")
    assert result == "Your Iron 883 service is scheduled.", f"Got: {result}"
    print(f"PASS test_purchase_alias_for_vehicle: {result}")


@pytest.mark.anyio
async def test_most_recent_purchase_used():
    """When multiple purchase_history entries, most recent by date is used"""
    contact = {
        "first_name": "Alice",
        "purchase_history": [
            {"title": "Sportster", "date": "2022-03-01"},
            {"title": "Fat Boy", "date": "2024-08-20"},
            {"title": "Street Glide", "date": "2023-11-05"},
        ],
    }
    message = "How's the {vehicle}?"
    result = await resolve_template_variables(None, message, contact, "user1")
    assert result == "How's the Fat Boy?", f"Got: {result}"
    print(f"PASS test_most_recent_purchase_used: {result}")


@pytest.mark.anyio
async def test_vehicle_no_purchase_history_key():
    """Contact dict without purchase_history key falls back to vehicle field"""
    contact = {
        "first_name": "Mike",
        "vehicle": "Mojave",
    }
    message = "Hi {first_name}, {vehicle} maintenance due."
    result = await resolve_template_variables(None, message, contact, "user1")
    assert result == "Hi Mike, Mojave maintenance due.", f"Got: {result}"
    print(f"PASS test_vehicle_no_purchase_history_key: {result}")


@pytest.mark.anyio
async def test_vehicle_empty_string_when_no_data():
    """When no vehicle info at all, {vehicle} resolves to empty string"""
    contact = {"first_name": "Tom"}
    message = "Your {vehicle} is ready."
    result = await resolve_template_variables(None, message, contact, "user1")
    assert result == "Your  is ready.", f"Got: {result}"
    print(f"PASS test_vehicle_empty_string_when_no_data: {result}")


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))
