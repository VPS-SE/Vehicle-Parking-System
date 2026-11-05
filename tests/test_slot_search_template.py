
from django.template.loader import render_to_string


def test_slot_search_template_renders_form_fields():
    rendered = render_to_string(
        "slots/search.html",
        {
            "lots": [],
            "vehicles": [],
            "selected_lot": "",
            "selected_vehicle": "",
            "for_driver": True,
            "start": "",
            "end": "",
            "slot_count": None,
            "search_error": "",
            "search_url": "",
        },
    )

    assert "Find Available Parking" in rendered
    assert 'name="lot"' in rendered
    assert 'name="vehicle"' in rendered
    assert 'name="start"' in rendered
    assert 'name="end"' in rendered
    assert "Search available slots" in rendered


def test_slot_search_template_offers_vehicle_type_to_staff():
    rendered = render_to_string(
        "slots/search.html",
        {"lots": [], "for_driver": False, "vehicle_types": [("", "Any vehicle type")]},
    )
    assert 'name="vehicle_type"' in rendered
    assert 'name="vehicle"' not in rendered
