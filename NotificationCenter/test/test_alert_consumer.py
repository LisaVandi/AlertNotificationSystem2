import pytest
from unittest.mock import MagicMock, patch
from NotificationCenter.app.config.settings import ALERT_QUEUE
from NotificationCenter.app.handlers.alert_consumer import AlertConsumer
from NotificationCenter.app.services.rabbitmq_handler import RabbitMQHandler

@pytest.fixture
def mock_rabbitmq_handler():
    return MagicMock(spec=RabbitMQHandler)

@pytest.fixture
def alert_consumer(mock_rabbitmq_handler):
    return AlertConsumer(rabbitmq_handler=mock_rabbitmq_handler)

def test_alert_consumer_initialization(mock_rabbitmq_handler):
    consumer = AlertConsumer(rabbitmq_handler=mock_rabbitmq_handler)
    assert consumer.rabbitmq == mock_rabbitmq_handler

def test_start_consuming(alert_consumer, mock_rabbitmq_handler):
    alert_consumer.start_consuming()
    mock_rabbitmq_handler.consume_messages.assert_called_once_with(
        queue_name=ALERT_QUEUE,
        callback=alert_consumer.process_alert
    )

def test_process_alert_valid(alert_consumer, mock_rabbitmq_handler):
    alert_data = {
        "id": "123",
        "type": "fire",
        "severity": "high",
        "area": "zone1"
    }
    with patch("NotificationCenter.app.handlers.alert_consumer.send_alert_to_map_manager") as mock_map_manager, \
         patch("NotificationCenter.app.handlers.alert_consumer.send_alert_to_user_simulator") as mock_user_simulator, \
         patch("NotificationCenter.app.handlers.alert_consumer.request_positions") as mock_request_positions:
        
        alert_consumer.process_alert(alert_data)
        
        mock_map_manager.assert_called_once_with(mock_rabbitmq_handler, alert_data)
        mock_user_simulator.assert_called_once_with(mock_rabbitmq_handler, alert_data)
        mock_request_positions.assert_called_once_with(mock_rabbitmq_handler, alert_data.get("id"))

def test_process_alert_invalid(alert_consumer):
    invalid_alert_data = {
        "id": "123",
        "type": "fire"
    }
    with pytest.raises(ValueError, match="Invalid alert format"):
        alert_consumer.process_alert(invalid_alert_data)

def test_validate_alert(alert_consumer):
    valid_alert = {
        "id": "123",
        "type": "fire",
        "severity": "high",
        "area": "zone1"
    }
    invalid_alert = {
        "id": "123",
        "type": "fire"
    }
    assert alert_consumer._validate_alert(valid_alert) is True
    assert alert_consumer._validate_alert(invalid_alert) is False