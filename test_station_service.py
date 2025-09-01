#!/usr/bin/env python3


import sys
import os
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'app'))

# Enable logging
logging.basicConfig(level=logging.INFO)

from backend.app.services.station_service import StationService

def test_station_service(station_id="BNS0061"):
    
    service = StationService()
    result = service.get_station_prediction(station_id)
    
    print('=== StationService Direct Test ===')
    print('Result Keys:', list(result.keys()))
    
    if 'success' in result and result['success']:
        print('Algorithm Prediction:', result.get('algorithm_prediction_kw', 'N/A'))
        print('Recommended Contract:', result.get('recommended_contract_kw', 'N/A'))
        print('Predicted Peak:', result.get('predicted_peak', 'N/A'))
        print('Current Peak:', result.get('current_peak', 'N/A'))
    else:
        print('Error:', result.get('error', result.get('message', 'Unknown error')))

if __name__ == "__main__":
    test_station_service("BNS0061")