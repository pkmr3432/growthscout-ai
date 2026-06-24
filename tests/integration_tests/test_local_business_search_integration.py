import json
import pytest
from unittest.mock import MagicMock, patch
from servers.local_search_server.server import local_business_search

@pytest.mark.asyncio
async def test_simulated_integration_flow():
    # Set up simulated Client call with mock maps responses
    with patch("googlemaps.Client") as mock_client:
        client_instance = MagicMock()
        mock_client.return_value = client_instance
        
        client_instance.places.return_value = {
            "results": [
                {
                    "place_id": "chIJ1",
                    "name": "Dentist Austin",
                    "formatted_address": "123 Congress Ave, Austin, TX 78701",
                    "rating": 4.2,
                    "user_ratings_total": 15
                }
            ]
        }
        
        client_instance.place.return_value = {
            "result": {
                "name": "Dentist Austin",
                "formatted_address": "123 Congress Ave, Austin, TX 78701",
                "website": "https://dentistaustin.com",
                "rating": 4.2,
                "user_ratings_total": 15
            }
        }
        
        from servers.local_search_server import server
        with patch.object(server, "GOOGLE_MAPS_API_KEY", "dummy_key"):
            response = await local_business_search("dentists Austin")
            data = json.loads(response)
            
            assert len(data["results"]) == 1
            assert data["results"][0]["name"] == "Dentist Austin"
            assert data["results"][0]["website"] == "https://dentistaustin.com"
