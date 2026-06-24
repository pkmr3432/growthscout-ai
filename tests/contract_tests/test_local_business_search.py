import json
import pytest
from unittest.mock import MagicMock, patch
from servers.local_search_server.server import local_business_search

@pytest.fixture
def mock_gmaps():
    with patch("googlemaps.Client") as mock_client:
        client_instance = MagicMock()
        mock_client.return_value = client_instance
        yield client_instance

@pytest.mark.asyncio
async def test_local_business_search_contract_success(mock_gmaps):
    # Set up mock places call
    mock_gmaps.places.return_value = {
        "results": [
            {
                "place_id": "chIJsVzS85a1RIYRh_9w94oRPA4",
                "name": "Austin Dental Care",
                "formatted_address": "123 Main St, Austin, TX 78701",
                "rating": 4.8,
                "user_ratings_total": 92
            }
        ]
    }
    
    # Set up mock place details call
    mock_gmaps.place.return_value = {
        "result": {
            "name": "Austin Dental Care",
            "formatted_address": "123 Main St, Austin, TX 78701",
            "website": "https://austindentist.com",
            "rating": 4.8,
            "user_ratings_total": 92
        }
    }
    
    # Temporarily mock GOOGLE_MAPS_API_KEY on the server
    from servers.local_search_server import server
    with patch.object(server, "GOOGLE_MAPS_API_KEY", "dummy_key"):
        response = await local_business_search("dentist Austin")
        data = json.loads(response)
        
        # Assert contract requirements
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 1
        
        lead = data["results"][0]
        assert "name" in lead
        assert "formatted_address" in lead
        assert "website" in lead
        assert "rating" in lead
        assert "user_ratings_total" in lead
        
        assert lead["name"] == "Austin Dental Care"
        assert lead["website"] == "https://austindentist.com"
